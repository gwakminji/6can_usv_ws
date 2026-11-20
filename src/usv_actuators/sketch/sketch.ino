#include <Arduino_RouterBridge.h>
#include <SPI.h>

const int PUMP_PIN = 7;
const bool PUMP_ACTIVE_LOW = true;

int set_pump(bool on) {
  digitalWrite(PUMP_PIN, (on ^ PUMP_ACTIVE_LOW) ? HIGH : LOW);
  return 1;
}

// LED: WS2812B 15개 x 2줄, 두 스트립 DIN 모두 D11(SPI2 MOSI)에 연결.
// NeoPixel 라이브러리는 show() 동안 인터럽트를 꺼서(~0.45ms) Bridge 시리얼
// (lpuart1, DMA/FIFO 없음) 바이트가 유실되고 MCU 전체가 멈췄다.
// SPI 하드웨어로 파형을 만들면 인터럽트를 끌 필요가 없다.
// SPI 2.5MHz(400ns/비트)에서 WS2812 1비트 = SPI 3비트: 1 → 110, 0 → 100
#define NUMPIXELS 15
#define LED_DATA_PIN 11                // D11 = SPI2 MOSI
const int LED_BRIGHTNESS = 50;
const uint32_t LED_SPI_HZ = 3000000;   // STM32 분주로 실제 2.5MHz가 선택됨
#define LED_RESET_BYTES 100            // 앞뒤 0 x 100바이트 = 320us low (줄이면 색이 깨짐)
uint8_t ledSpiBuf[LED_RESET_BYTES + NUMPIXELS * 9 + LED_RESET_BYTES];
uint8_t ledPixels[NUMPIXELS][3];       // 이 스트립은 와이어 순서가 R, G, B

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
      uint32_t bits = 0;

      for (int j = 7; j >= 0; j--)
        bits = (bits << 3) | (((v >> j) & 1) ? 0b110 : 0b100);

      ledSpiBuf[k++] = bits >> 16;
      ledSpiBuf[k++] = bits >> 8;
      ledSpiBuf[k++] = bits;
    }
  }

  memset(ledSpiBuf + k, 0, LED_RESET_BYTES);

  SPI.begin();  // D11을 SPI(MOSI)로 되돌림
  SPI.beginTransaction(SPISettings(LED_SPI_HZ, MSBFIRST, SPI_MODE0));
  SPI.transfer(ledSpiBuf, sizeof(ledSpiBuf));
  SPI.endTransaction();

  // SPI가 꺼지면 MOSI가 LOW로 유지되지 않아 색이 깨졌다.
  // 전송 사이에는 GPIO LOW로 고정 → LED가 리셋(래치)을 확실히 받는다.
  pinMode(LED_DATA_PIN, OUTPUT);
  digitalWrite(LED_DATA_PIN, LOW);
}

void ledSetPixel(int i, int r, int g, int b)
{
  ledPixels[i][0] = r;
  ledPixels[i][1] = g;
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

void setup() {
  pinMode(PUMP_PIN, OUTPUT);
  set_pump(false);

  SPI.begin();
  applyLed(0, 0, 0);  // 시작은 꺼진 상태로 대기

  Bridge.begin();
  Monitor.begin(115200);
  Bridge.provide("set_pump", set_pump);
  Bridge.provide_safe("set_actuator_led", set_actuator_led);
  Bridge.provide_safe("set_led_rainbow", set_led_rainbow);
  Monitor.println("Pump + WS2812 LED bridge ready.");
}

void loop() {
}
