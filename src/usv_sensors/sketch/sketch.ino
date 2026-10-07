#include <Arduino.h>
#include <Arduino_RouterBridge.h>
#include <OneWire.h>
#include <SPI.h>
#include <math.h>
#include "adc_accumulator.h"

#define TEMP_PIN 4
#define PH_PIN A1
#define DO_PIN A5
#define TURBIDITY_PIN A0

// B2 보드 usv_actuators 스케치에서 가져온 분수 펌프 릴레이 제어.
// NEROMART RELAY-M1(CH1)-5V, 옵토커플러 입력이라 Active LOW.
const int PUMP_PIN = 7;
const bool PUMP_ACTIVE_LOW = true;

// LED: WS2812B 15개 x 2줄, 두 스트립 DIN 모두 D11(SPI2 MOSI)에 연결.
// NeoPixel 라이브러리는 show() 동안 인터럽트를 꺼서(~0.45ms) Bridge 시리얼
// (lpuart1, DMA/FIFO 없음) 바이트가 유실되고 MCU 전체가 멈췄다.
// SPI 하드웨어로 파형을 만들면 인터럽트를 끌 필요가 없다.
// SPI 2.5MHz(400ns/비트)에서 WS2812 1비트 = SPI 4비트: 1 → 1100, 0 → 1000
// SPI가 인터럽트 방식이라 바이트 사이에 간격이 생기고, 그동안 MOSI는 다음 바이트의
// 첫 비트를 내보낸다. 첫 비트가 1이면 HIGH가 늘어나 0이 1로 읽힘(전부 흰색).
// → 비트열을 1비트 밀어서 바이트가 항상 0으로 시작하고 0으로 끝나게 한다:
//   바이트 = 0 1 a 0 0 1 b 0  (a, b = WS2812 비트 2개). 간격은 LOW만 늘린다.
#define NUMPIXELS 15
#define LED_DATA_PIN 11                // D11 = SPI2 MOSI
const int LED_BRIGHTNESS = 50;
const uint32_t LED_SPI_HZ = 3000000;   // STM32 분주로 실제 2.5MHz가 선택됨
// 앞뒤 0 패딩은 짧게 (4바이트 = 12.8us). 리셋(래치)에 필요한 280us 이상 LOW는
// 전송 후 GPIO LOW 고정 + 프레임 간 최소 간격(LED_LATCH_US)으로 보장한다.
// SPI 전송 시간이 짧을수록 Bridge 시리얼 바이트 유실 위험이 줄어든다.
#define LED_RESET_BYTES 4
#define LED_LATCH_US 300
uint32_t ledLastShowUs = 0;
uint8_t ledSpiBuf[LED_RESET_BYTES + NUMPIXELS * 12 + LED_RESET_BYTES];
uint8_t ledPixels[NUMPIXELS][3];       // WS2812B 와이어 순서: G, R, B

#define ADC_BITS 12
#define ADC_MAX 4095.0
#define ADC_REFERENCE_V 3.3
#define ADC_REFERENCE_MV 3300.0
#define SAMPLE_COUNT 40

#define PH7_BUFFER_VALUE 7.00
#define PH4_BUFFER_VALUE 4.00

#define PH7_VOLTAGE 1.142
#define PH4_VOLTAGE 0.888

#define PH_CALIBRATION_T 25.47

#define DO_CAL_V 1505.0
#define DO_CAL_T 25.4

#define TURBIDITY_DIVIDER_RATIO 1.5

#define CLEAR_WATER_VOLTAGE 4.810
#define VERY_TURBID_VOLTAGE 0.140

OneWire oneWire(TEMP_PIN);

byte temperatureAddress[8];
bool temperatureSensorFound = false;

const uint16_t DO_TABLE[41] = {
  14460, 14220, 13820, 13440, 13090,
  12740, 12420, 12110, 11810, 11530,
  11260, 11010, 10770, 10530, 10300,
  10080,  9860,  9660,  9460,  9270,
   9080,  8900,  8730,  8570,  8410,
   8250,  8110,  7960,  7820,  7690,
   7560,  7430,  7300,  7180,  7070,
   6950,  6840,  6730,  6630,  6530,
   6410
};

// =================================================
// NEO-M8N GPS (UART / NMEA-0183)
// =================================================

String gpsLine = "";
bool gpsFix = false;
bool gpsParserOk = false;
uint8_t gpsSatellites = 0;
double gpsLatitude = NAN;
double gpsLongitude = NAN;
unsigned long gpsBytesReceived = 0;
unsigned long gpsSentencesReceived = 0;
unsigned long gpsChecksumErrors = 0;
unsigned long gpsLastSentenceMs = 0;

#define GPS_FIX_TIMEOUT_MS 5000


String nmeaField(
  const String &line,
  uint8_t fieldIndex
)
{
  int start = 0;
  uint8_t currentField = 0;

  for (int i = 0; i <= line.length(); i++)
  {
    if (i == line.length() || line.charAt(i) == ',')
    {
      if (currentField == fieldIndex)
        return line.substring(start, i);

      start = i + 1;
      currentField++;
    }
  }

  return "";
}


bool isNmeaType(
  const String &line,
  const char *suffix
)
{
  return line.length() >= 6 &&
         line.charAt(0) == '$' &&
         line.substring(3, 6) == suffix;
}


bool hasValidNmeaChecksum(const String &line)
{
  int separator = line.indexOf('*');

  if (line.length() < 7 || line.charAt(0) != '$' ||
      separator < 0 || separator + 2 >= line.length())
    return false;

  uint8_t calculated = 0;
  for (int i = 1; i < separator; i++)
    calculated ^= (uint8_t)line.charAt(i);

  String checksumText = line.substring(separator + 1, separator + 3);
  char *end = nullptr;
  unsigned long received = strtoul(checksumText.c_str(), &end, 16);

  return end != checksumText.c_str() && *end == '\0' &&
         received <= 0xFF && calculated == (uint8_t)received;
}


double nmeaCoordinateToDegrees(
  const String &raw,
  char hemisphere
)
{
  if (raw.length() < 4)
    return NAN;

  double value = raw.toDouble();
  int degrees = (int)(value / 100.0);
  double minutes = value - degrees * 100.0;
  double result = degrees + minutes / 60.0;

  if (hemisphere == 'S' || hemisphere == 'W')
    result = -result;

  return result;
}


void parseNmeaLine(const String &line)
{
  if (!hasValidNmeaChecksum(line))
  {
    gpsChecksumErrors++;
    return;
  }

  gpsLastSentenceMs = millis();

  // Accept GP, GN, and other valid NMEA talker IDs.
  if (isNmeaType(line, "GGA"))
  {
    int fixQuality = nmeaField(line, 6).toInt();
    gpsSatellites = (uint8_t)nmeaField(line, 7).toInt();

    if (fixQuality == 0)
      gpsFix = false;
    else
    {
      String rawLat = nmeaField(line, 2);
      String ns = nmeaField(line, 3);
      String rawLon = nmeaField(line, 4);
      String ew = nmeaField(line, 5);

      gpsLatitude = nmeaCoordinateToDegrees(
        rawLat,
        ns.length() ? ns.charAt(0) : 'N'
      );
      gpsLongitude = nmeaCoordinateToDegrees(
        rawLon,
        ew.length() ? ew.charAt(0) : 'E'
      );
      gpsFix = !isnan(gpsLatitude) && !isnan(gpsLongitude);
    }
  }
  else if (isNmeaType(line, "RMC"))
  {
    gpsFix = nmeaField(line, 2) == "A";

    if (gpsFix)
    {
      String rawLat = nmeaField(line, 3);
      String ns = nmeaField(line, 4);
      String rawLon = nmeaField(line, 5);
      String ew = nmeaField(line, 6);

      gpsLatitude = nmeaCoordinateToDegrees(
        rawLat,
        ns.length() ? ns.charAt(0) : 'N'
      );

      gpsLongitude = nmeaCoordinateToDegrees(
        rawLon,
        ew.length() ? ew.charAt(0) : 'E'
      );
    }
  }
}


void serviceGps()
{
  while (Serial1.available() > 0)
  {
    char c = Serial1.read();
    gpsBytesReceived++;

    if (c == '\n' || c == '\r')
    {
      if (gpsLine.length() > 0)
      {
        if (gpsLine.charAt(0) == '$')
          gpsSentencesReceived++;

        parseNmeaLine(gpsLine);
        gpsLine = "";
      }
    }
    else if (c >= 32 && c <= 126)
    {
      if (gpsLine.length() < 120)
        gpsLine += c;
      else
        gpsLine = "";
    }
  }

  if (gpsLastSentenceMs > 0 &&
      millis() - gpsLastSentenceMs > GPS_FIX_TIMEOUT_MS)
    gpsFix = false;
}


void waitWhileReadingGps(unsigned long durationMs)
{
  unsigned long startedAt = millis();

  while (millis() - startedAt < durationMs)
  {
    serviceGps();
    delay(1);
  }
}


bool runGpsParserSelfTest()
{
  bool savedFix = gpsFix;
  uint8_t savedSatellites = gpsSatellites;
  double savedLatitude = gpsLatitude;
  double savedLongitude = gpsLongitude;
  unsigned long savedLastSentenceMs = gpsLastSentenceMs;
  unsigned long savedChecksumErrors = gpsChecksumErrors;

  parseNmeaLine(
    "$GNGGA,123519,3723.2475,N,12701.2345,E,1,08,0.9,10.0,M,0.0,M,,*55"
  );
  parseNmeaLine(
    "$GNRMC,123519,A,3723.2475,N,12701.2345,E,0.0,0.0,010126,,,A*63"
  );

  bool passed = gpsFix &&
                gpsSatellites == 8 &&
                fabs(gpsLatitude - 37.3874583) < 0.00001 &&
                fabs(gpsLongitude - 127.020575) < 0.00001;

  gpsFix = savedFix;
  gpsSatellites = savedSatellites;
  gpsLatitude = savedLatitude;
  gpsLongitude = savedLongitude;
  gpsLastSentenceMs = savedLastSentenceMs;
  gpsChecksumErrors = savedChecksumErrors;

  return passed;
}


bool findTemperatureSensor()
{
  oneWire.reset_search();

  while (oneWire.search(temperatureAddress))
  {
    if (OneWire::crc8(temperatureAddress, 7)
        != temperatureAddress[7])
      continue;

    if (temperatureAddress[0] == 0x28)
      return true;
  }

  return false;
}


bool startTemperatureConversion()
{
  if (!temperatureSensorFound)
    return false;

  if (!oneWire.reset())
    return false;

  oneWire.select(temperatureAddress);
  oneWire.write(0x44, 1);

  return true;
}


float readTemperatureResult()
{
  byte data[9];

  if (!oneWire.reset())
    return NAN;

  oneWire.select(temperatureAddress);
  oneWire.write(0xBE);

  for (int i = 0; i < 9; i++)
    data[i] = oneWire.read();

  if (OneWire::crc8(data, 8) != data[8])
    return NAN;

  int16_t raw =
    ((int16_t)data[1] << 8) | data[0];

  return raw / 16.0;
}


void addAdcSample(
  AdcAccumulator &accumulator,
  int pin
)
{
  // Discard one reading after changing ADC channels so the multiplexer
  // and sample-and-hold circuit can settle.
  analogRead(pin);
  delayMicroseconds(200);

  int value = analogRead(pin);

  accumulator.sum += value;

  if (value < accumulator.minValue)
    accumulator.minValue = value;

  if (value > accumulator.maxValue)
    accumulator.maxValue = value;
}


double trimmedAdcAverage(
  const AdcAccumulator &accumulator
)
{
  return (
    (double)accumulator.sum -
    accumulator.minValue -
    accumulator.maxValue
  ) / (SAMPLE_COUNT - 2);
}


void readWaterQualityInputs(
  float &temperature,
  double &phADC,
  double &doADC,
  double &turbidityADC
)
{
  AdcAccumulator phSamples;
  AdcAccumulator doSamples;
  AdcAccumulator turbiditySamples;

  unsigned long conversionStartedAt = millis();
  bool temperatureConversionStarted =
    startTemperatureConversion();

  // Collect all three analog channels during the DS18B20 conversion.
  // The channels are interleaved rather than waiting 800 ms per sensor.
  for (int i = 0; i < SAMPLE_COUNT; i++)
  {
    addAdcSample(phSamples, PH_PIN);
    addAdcSample(doSamples, DO_PIN);
    addAdcSample(turbiditySamples, TURBIDITY_PIN);
    waitWhileReadingGps(18);
  }

  unsigned long elapsed = millis() - conversionStartedAt;
  if (temperatureConversionStarted && elapsed < 750)
    waitWhileReadingGps(750 - elapsed);

  temperature = temperatureConversionStarted
    ? readTemperatureResult()
    : NAN;
  phADC = trimmedAdcAverage(phSamples);
  doADC = trimmedAdcAverage(doSamples);
  turbidityADC = trimmedAdcAverage(turbiditySamples);
}


float adcToVoltage(double adcValue)
{
  return adcValue *
         ADC_REFERENCE_V /
         ADC_MAX;
}


float adcToMillivolts(double adcValue)
{
  return adcValue *
         ADC_REFERENCE_MV /
         ADC_MAX;
}


float calculatePH(
  float voltage,
  float temperature
)
{
  if (isnan(temperature))
    return NAN;

  float voltageDifference =
    PH4_VOLTAGE -
    PH7_VOLTAGE;

  if (fabs(voltageDifference) < 0.001)
    return NAN;

  float calibrationSlope =
    (PH4_BUFFER_VALUE -
     PH7_BUFFER_VALUE)
    /
    voltageDifference;

  float temperatureSlope =
    calibrationSlope *
    (
      (PH_CALIBRATION_T + 273.15)
      /
      (temperature + 273.15)
    );

  return
    PH7_BUFFER_VALUE +
    temperatureSlope *
    (voltage - PH7_VOLTAGE);
}


float calculateDO(
  float voltageMv,
  float temperature
)
{
  if (isnan(temperature))
    return NAN;

  int temperatureIndex =
    constrain(
      (int)round(temperature),
      0,
      40
    );

  float saturationVoltage =
    DO_CAL_V +
    35.0 *
    (
      temperatureIndex -
      DO_CAL_T
    );

  if (saturationVoltage <= 0.0)
    return NAN;

  return
    voltageMv *
    DO_TABLE[temperatureIndex]
    /
    saturationVoltage
    /
    1000.0;
}


float calculateCleanliness(
  float voltage
)
{
  float cleanliness =
    (
      voltage -
      VERY_TURBID_VOLTAGE
    )
    /
    (
      CLEAR_WATER_VOLTAGE -
      VERY_TURBID_VOLTAGE
    )
    *
    100.0;

  return constrain(
    cleanliness,
    0.0,
    100.0
  );
}


String getCleanlinessLevel(
  float value
)
{
  if (value >= 80.0)
    return "very_clear";

  if (value >= 60.0)
    return "clear";

  if (value >= 40.0)
    return "normal";

  if (value >= 20.0)
    return "turbid";

  return "very_turbid";
}


String floatToJson(
  float value,
  int digits
)
{
  if (isnan(value))
    return "null";

  return String(
    value,
    digits
  );
}


// =================================================
// Linux/ROS에서 호출할 함수
// =================================================

int set_pump(bool on)
{
  digitalWrite(
    PUMP_PIN,
    (on ^ PUMP_ACTIVE_LOW) ? HIGH : LOW
  );

  return 1;
}


// show()는 색이 바뀔 때만 호출하고, 무지개는 애니메이션 없이
// LED마다 다른 색을 한 번만 칠한다.
bool ledRainbowOn = false;
int ledR = -1, ledG = -1, ledB = -1;

void ledShow()
{
  int k = 0;
  memset(ledSpiBuf, 0, LED_RESET_BYTES);
  k += LED_RESET_BYTES;

  for (int i = 0; i < NUMPIXELS; i++)
  {
    for (int c = 0; c < 3; c++)
    {
      uint8_t v = (ledPixels[i][c] * (LED_BRIGHTNESS + 1)) >> 8;

      for (int j = 7; j >= 0; j -= 2)
      {
        uint8_t a = (v >> j) & 1;
        uint8_t b = (v >> (j - 1)) & 1;
        ledSpiBuf[k++] = 0b01000010 | (a << 5) | (b << 1);
      }
    }
  }

  memset(ledSpiBuf + k, 0, LED_RESET_BYTES);

  while (micros() - ledLastShowUs < LED_LATCH_US)
    delayMicroseconds(10);

  SPI.begin();  // D11을 SPI(MOSI)로 되돌림
  SPI.beginTransaction(SPISettings(LED_SPI_HZ, MSBFIRST, SPI_MODE0));
  SPI.transfer(ledSpiBuf, sizeof(ledSpiBuf));
  SPI.endTransaction();

  // SPI가 꺼지면 MOSI가 LOW로 유지되지 않아 색이 깨졌다.
  // 전송 사이에는 GPIO LOW로 고정 → LED가 리셋(래치)을 확실히 받는다.
  pinMode(LED_DATA_PIN, OUTPUT);
  digitalWrite(LED_DATA_PIN, LOW);
  ledLastShowUs = micros();
}

void ledSetPixel(int i, int r, int g, int b)
{
  ledPixels[i][0] = g;
  ledPixels[i][1] = r;
  ledPixels[i][2] = b;
}

void applyLed(int r, int g, int b)
{
  if (r == ledR && g == ledG && b == ledB)
    return;

  ledR = r;
  ledG = g;
  ledB = b;

  for (int i = 0; i < NUMPIXELS; i++)
    ledSetPixel(i, r, g, b);

  ledShow();
}

int set_actuator_led(int r, int g, int b)
{
  // 무지개 중에는 단색 명령을 무시한다 (끄려면 set_led_rainbow(false)).
  if (ledRainbowOn)
    return 0;

  applyLed(r, g, b);
  return 1;
}

void hueToRgb(float hue, int &r, int &g, int &b)
{
  float h = hue * 6.0;
  int i = (int)h;
  float f = h - i;
  float q = 1.0 - f;
  float fr, fg, fb;

  if      (i == 0) { fr = 1.0; fg = f;   fb = 0.0; }
  else if (i == 1) { fr = q;   fg = 1.0; fb = 0.0; }
  else if (i == 2) { fr = 0.0; fg = 1.0; fb = f;   }
  else if (i == 3) { fr = 0.0; fg = q;   fb = 1.0; }
  else if (i == 4) { fr = f;   fg = 0.0; fb = 1.0; }
  else             { fr = 1.0; fg = 0.0; fb = q;   }

  r = round(fr * 255);
  g = round(fg * 255);
  b = round(fb * 255);
}

int set_led_rainbow(bool on)
{
  if (!on)
  {
    ledRainbowOn = false;
    applyLed(0, 0, 0);
    return 1;
  }

  if (ledRainbowOn)
    return 1;
  ledRainbowOn = true;

  // 스트립 길이만큼 빨강→보라 무지개를 고정으로 칠한다.
  for (int i = 0; i < NUMPIXELS; i++)
  {
    int r, g, b;
    hueToRgb((float)i / NUMPIXELS, r, g, b);
    ledSetPixel(i, r, g, b);
  }

  ledShow();

  ledR = ledG = ledB = -1;  // 다음 단색 명령이 반드시 적용되도록
  return 1;
}


String get_water_quality()
{
  unsigned long measurementStartedAt = millis();
  float temperature;
  double phADC;
  double doADC;
  double turbidityADC;

  readWaterQualityInputs(
    temperature,
    phADC,
    doADC,
    turbidityADC
  );

  float phVoltage =
    adcToVoltage(phADC);

  float ph =
    calculatePH(
      phVoltage,
      temperature
    );

  float doVoltageMv =
    adcToMillivolts(doADC);

  float dissolvedOxygen =
    calculateDO(
      doVoltageMv,
      temperature
    );

  float turbidityA0Voltage =
    adcToVoltage(
      turbidityADC
    );

  float turbidityVoltage =
    turbidityA0Voltage *
    TURBIDITY_DIVIDER_RATIO;

  float clarity =
    calculateCleanliness(
      turbidityVoltage
    );

  String level =
    getCleanlinessLevel(
      clarity
    );


  String json = "{";

  json += "\"ms\":";
  json += String(millis());

  json += ",\"measurement_ms\":";
  json += String(millis() - measurementStartedAt);

  json += ",\"temp_c\":";
  json += floatToJson(
    temperature,
    2
  );

  json += ",\"ph\":";
  json += floatToJson(
    ph,
    2
  );

  json += ",\"do_mg_l\":";
  json += floatToJson(
    dissolvedOxygen,
    2
  );

  json +=
    ",\"turbidity_voltage_v\":";

  json += floatToJson(
    turbidityVoltage,
    3
  );

  json += ",\"clarity_pct\":";

  json += floatToJson(
    clarity,
    1
  );

  json +=
    ",\"clarity_level\":\"";

  json += level;

  json += "\"}";

  return json;
}


String get_gps()
{
  serviceGps();

  String json = "{";

  json += "\"ms\":";
  json += String(millis());

  json += ",\"parser_ok\":";
  json += gpsParserOk ? "true" : "false";

  json += ",\"fix\":";
  json += gpsFix ? "true" : "false";

  json += ",\"satellites\":";
  json += String(gpsSatellites);

  json += ",\"latitude\":";
  if (gpsFix && !isnan(gpsLatitude))
    json += String(gpsLatitude, 7);
  else
    json += "null";

  json += ",\"longitude\":";
  if (gpsFix && !isnan(gpsLongitude))
    json += String(gpsLongitude, 7);
  else
    json += "null";

  json += ",\"bytes\":";
  json += String(gpsBytesReceived);

  json += ",\"sentences\":";
  json += String(gpsSentencesReceived);

  json += ",\"checksum_errors\":";
  json += String(gpsChecksumErrors);

  json += ",\"last_sentence_age_ms\":";
  if (gpsLastSentenceMs > 0)
    json += String(millis() - gpsLastSentenceMs);
  else
    json += "null";

  json += "}";

  return json;
}


void setup()
{
  pinMode(PUMP_PIN, OUTPUT);
  set_pump(false);

  // 부팅 직후 스트립 전체를 초기화해 첫 칸만 켜진 채 남지 않게 한다.
  SPI.begin();
  applyLed(0, 0, 0);

  Serial1.begin(9600);

  analogReadResolution(
    ADC_BITS
  );

  temperatureSensorFound =
    findTemperatureSensor();

  gpsParserOk =
    runGpsParserSelfTest();

  Bridge.begin();

  Bridge.provide(
    "get_water_quality",
    get_water_quality
  );

  Bridge.provide(
    "get_gps",
    get_gps
  );

  Bridge.provide(
    "set_pump",
    set_pump
  );

  // LED는 loop()와 같은 스레드에서 처리 (provide_safe).
  Bridge.provide_safe(
    "set_actuator_led",
    set_actuator_led
  );

  Bridge.provide_safe(
    "set_led_rainbow",
    set_led_rainbow
  );
}


void loop()
{
  serviceGps();
}
