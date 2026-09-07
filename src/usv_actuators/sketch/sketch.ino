#include <Arduino_RouterBridge.h>
#include <Servo.h>

const int LEFT_PWM_PIN  = 9;
const int RIGHT_PWM_PIN = 10;

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

void setup() {
  Bridge.begin();
  Monitor.begin(115200);

  left_thruster.attach(LEFT_PWM_PIN, 1000, 2000);
  right_thruster.attach(RIGHT_PWM_PIN, 1000, 2000);

  left_thruster.writeMicroseconds(NEUTRAL_US);
  right_thruster.writeMicroseconds(NEUTRAL_US);
  delay(2000);

  Bridge.provide("set_thruster_pwm", set_thruster_pwm);

  last_cmd_ms = millis();
  Monitor.println("Thruster bridge ready.");
}

void loop() {
  // MCU 측 failsafe: 500ms 이상 명령이 없으면 강제 중립
  if (millis() - last_cmd_ms > FAILSAFE_MS) {
    left_thruster.writeMicroseconds(NEUTRAL_US);
    right_thruster.writeMicroseconds(NEUTRAL_US);
  }
  delay(10);
}
