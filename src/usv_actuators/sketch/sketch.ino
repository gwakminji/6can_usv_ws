#include <Arduino_RouterBridge.h>
#include <Servo.h>

const int LEFT_PWM_PIN  = 9;
const int RIGHT_PWM_PIN = 10;

// 분수 펌프 릴레이 (NEROMART RELAY-M1(CH1)-5V)
// Active LOW: IN이 0V일 때 릴레이 ON, HIGH일 때 OFF.
// UNO Q는 3.3V 로직이지만 이 모듈 입력단이 R1+옵토LED+상태LED 직렬(문턱 약 3.2V)이라
// IN=3.3V면 5-3.3=1.7V만 걸려 확실히 OFF된다. 실측으로 확인함.
const int PUMP_PIN = 7;
const bool PUMP_ACTIVE_LOW = true;

const int NEUTRAL_US = 1487;
const unsigned long FAILSAFE_MS = 500;

Servo left_thruster;
Servo right_thruster;

unsigned long last_cmd_ms = 0;

int set_thruster_pwm(int left_us, int right_us) {
  left_us  = constrain(left_us,  1000, 2000);
  right_us = constrain(right_us, 1000, 2000);

  left_thruster.writeMicroseconds(left_us);
  right_thruster.writeMicroseconds(right_us);

  last_cmd_ms = millis();
  return 1;
}

int set_pump(bool on) {
  digitalWrite(PUMP_PIN, (on ^ PUMP_ACTIVE_LOW) ? HIGH : LOW);
  return 1;
}

void setup() {
  // 펌프부터 끈다. ESC 아밍(delay 2000) 전에 확실히 OFF 상태를 만들어,
  // 부팅 중 펌프가 도는 일이 없게 한다.
  pinMode(PUMP_PIN, OUTPUT);
  set_pump(false);

  Bridge.begin();
  Monitor.begin(115200);

  left_thruster.attach(LEFT_PWM_PIN, 1000, 2000);
  right_thruster.attach(RIGHT_PWM_PIN, 1000, 2000);

  left_thruster.writeMicroseconds(NEUTRAL_US);
  right_thruster.writeMicroseconds(NEUTRAL_US);
  delay(2000);

  Bridge.provide("set_thruster_pwm", set_thruster_pwm);
  Bridge.provide("set_pump", set_pump);

  last_cmd_ms = millis();
  Monitor.println("Thruster + pump bridge ready.");
}

void loop() {
  // MCU 측 failsafe: 500ms 이상 명령이 없으면 강제 중립
  if (millis() - last_cmd_ms > FAILSAFE_MS) {
    left_thruster.writeMicroseconds(NEUTRAL_US);
    right_thruster.writeMicroseconds(NEUTRAL_US);
  }
  delay(10);
}
