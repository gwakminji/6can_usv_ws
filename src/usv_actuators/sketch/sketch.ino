/*
 * B2 보드 액추에이터 스케치 — 분수 펌프 + 추진기
 *
 * ⚠️ 추진기 부분은 현재 주석 처리되어 있다.
 *
 *    이유: 공식 Servo 라이브러리가 UNO Q의 zephyr 아키텍처를 지원하지 않아
 *    컴파일이 실패한다.
 *
 *      error: "This library only supports boards with an AVR, SAM, SAMD,
 *              NRF52, STM32F4, Renesas or XMC processor."
 *
 *    ESC는 50Hz에 1000~2000us 펄스가 필요한데 UNO Q의 analogWrite는 500Hz
 *    고정이라 그대로는 대체가 안 된다. zephyr용 PWM API나 다른 라이브러리를
 *    찾아야 한다. 추진기 담당자가 해결한 뒤 아래 주석을 해제하면 된다.
 *
 * 펌프 릴레이: NEROMART RELAY-M1(CH1)-5V (Active LOW)
 *   UNO Q 5V -> VCC, GND -> GND, D7 -> IN1
 *   UNO Q는 3.3V 로직이지만 모듈 입력단이 R1(1k)+옵토LED+상태LED 직렬이라
 *   도통 문턱이 약 3.2V다. IN=3.3V면 1.7V만 걸려 확실히 OFF된다. 실측 확인함.
 */

#include <Arduino_RouterBridge.h>
// #include <Servo.h>          // TODO(추진기): zephyr 미지원

// ── 추진기 (현재 비활성) ──────────────────────────────
// const int LEFT_PWM_PIN  = 9;
// const int RIGHT_PWM_PIN = 10;
// const int NEUTRAL_US = 1487;
// const unsigned long FAILSAFE_MS = 500;
//
// Servo left_thruster;
// Servo right_thruster;
// unsigned long last_cmd_ms = 0;
//
// int set_thruster_pwm(int left_us, int right_us) {
//   left_us  = constrain(left_us,  1000, 2000);
//   right_us = constrain(right_us, 1000, 2000);
//
//   left_thruster.writeMicroseconds(left_us);
//   right_thruster.writeMicroseconds(right_us);
//
//   last_cmd_ms = millis();
//   return 1;
// }
// ──────────────────────────────────────────────────────

// ── 분수 펌프 ─────────────────────────────────────────
const int PUMP_PIN = 7;
const bool PUMP_ACTIVE_LOW = true;

int set_pump(bool on) {
  digitalWrite(PUMP_PIN, (on ^ PUMP_ACTIVE_LOW) ? HIGH : LOW);
  return 1;
}
// ──────────────────────────────────────────────────────

void setup() {
  // 펌프부터 끈다. 추진기 아밍 delay(2000)보다 먼저 두어야
  // 부팅 중 펌프가 도는 일이 없다.
  pinMode(PUMP_PIN, OUTPUT);
  set_pump(false);

  Bridge.begin();
  Monitor.begin(115200);

  // ── 추진기 초기화 (현재 비활성) ──
  // left_thruster.attach(LEFT_PWM_PIN, 1000, 2000);
  // right_thruster.attach(RIGHT_PWM_PIN, 1000, 2000);
  // left_thruster.writeMicroseconds(NEUTRAL_US);
  // right_thruster.writeMicroseconds(NEUTRAL_US);
  // delay(2000);
  // Bridge.provide("set_thruster_pwm", set_thruster_pwm);
  // last_cmd_ms = millis();

  Bridge.provide("set_pump", set_pump);

  Monitor.println("Pump bridge ready. (thruster disabled)");
}

void loop() {
  // ── 추진기 failsafe (현재 비활성) ──
  // 500ms 이상 명령이 없으면 강제 중립
  // if (millis() - last_cmd_ms > FAILSAFE_MS) {
  //   left_thruster.writeMicroseconds(NEUTRAL_US);
  //   right_thruster.writeMicroseconds(NEUTRAL_US);
  // }
  // delay(10);
}
