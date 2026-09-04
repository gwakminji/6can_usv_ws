#include <Arduino.h>
#include <Arduino_RouterBridge.h>
#include <OneWire.h>
#include <math.h>
#include "adc_accumulator.h"

#define TEMP_PIN 4
#define PH_PIN A1
#define DO_PIN A5
#define TURBIDITY_PIN A0

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
}


void loop()
{
  serviceGps();
}
