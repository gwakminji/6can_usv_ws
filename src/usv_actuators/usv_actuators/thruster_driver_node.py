#!/usr/bin/env python3

"""
thruster_driver_node

ROS2 /cmd_vel (geometry_msgs/Twist) 구독
→ 좌/우 스러스터 PWM 계산
→ UDP로 UNO Q 로컬 gateway Python에 전송

구조:
ROS2 Docker
    /cmd_vel
       ↓
thruster_driver_node
       ↓ UDP
192.168.0.72:5005
       ↓
UNO Q gateway Python
       ↓
RouterBridge
       ↓
MCU
       ↓
ESC / Motor
"""

import socket
import struct
import time

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist


# ============================================================
# Network
# ============================================================

GATEWAY_ADDR = ("192.168.0.72", 5005)


# ============================================================
# Thruster PWM settings
# ============================================================

NEUTRAL_PWM = 1500

# 처음 테스트는 안전하게 ±200us만 사용
# 최대 전진: 1700us
# 최대 후진: 1300us
MAX_DELTA = 200

# 조이스틱 미세 입력 무시
INPUT_DEADBAND = 0.05

# /cmd_vel 끊기면 중립으로 복귀
CMD_TIMEOUT = 0.5

# UDP 전송 주기
RATE_HZ = 20.0
DT = 1.0 / RATE_HZ


def clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


class ThrusterDriverNode(Node):

    def __init__(self):
        super().__init__("thruster_driver_node")

        # /cmd_vel subscriber
        self.create_subscription(
            Twist,
            "/cmd_vel",
            self.on_cmd_vel,
            10
        )

        # UDP socket
        self.sock = socket.socket(
            socket.AF_INET,
            socket.SOCK_DGRAM
        )

        # 현재 목표 PWM
        self.target_left = NEUTRAL_PWM
        self.target_right = NEUTRAL_PWM

        # 마지막 /cmd_vel 수신 시각
        self.last_cmd_time = 0.0

        # timeout 로그 중복 방지
        self.timed_out = True

        # 20Hz control loop
        self.create_timer(
            DT,
            self.control_loop
        )

        self.get_logger().info(
            f"Thruster Driver Node Started "
            f"(UDP Mode -> {GATEWAY_ADDR[0]}:{GATEWAY_ADDR[1]})"
        )

    def on_cmd_vel(self, msg: Twist):

        # 입력 제한
        linear = clamp(
            msg.linear.x,
            -1.0,
            1.0
        )

        angular = clamp(
            msg.angular.z,
            -1.0,
            1.0
        )

        # Deadband
        if abs(linear) < INPUT_DEADBAND:
            linear = 0.0

        if abs(angular) < INPUT_DEADBAND:
            angular = 0.0

        # Differential thrust mixing
        #
        # 전진:
        # linear > 0
        #
        # 회전:
        # angular > 0
        #
        left = linear - angular
        right = linear + angular

        # 비율 유지하면서 -1 ~ +1 범위로 정규화
        scale = max(
            1.0,
            abs(left),
            abs(right)
        )

        left /= scale
        right /= scale

        # -1 ~ +1
        # ↓
        # 1500 ± MAX_DELTA
        left_pwm = int(
            round(
                NEUTRAL_PWM +
                left * MAX_DELTA
            )
        )

        right_pwm = int(
            round(
                NEUTRAL_PWM +
                right * MAX_DELTA
            )
        )

        # 안전 범위 제한
        left_pwm = clamp(
            left_pwm,
            NEUTRAL_PWM - MAX_DELTA,
            NEUTRAL_PWM + MAX_DELTA
        )

        right_pwm = clamp(
            right_pwm,
            NEUTRAL_PWM - MAX_DELTA,
            NEUTRAL_PWM + MAX_DELTA
        )

        self.target_left = left_pwm
        self.target_right = right_pwm

        self.last_cmd_time = time.monotonic()
        self.timed_out = False

        self.get_logger().info(
            f"CMD "
            f"linear={linear:.2f} "
            f"angular={angular:.2f} "
            f"-> "
            f"L={left_pwm}us "
            f"R={right_pwm}us"
        )

    def control_loop(self):

        now = time.monotonic()

        # /cmd_vel timeout
        if (
            self.last_cmd_time == 0.0
            or
            now - self.last_cmd_time > CMD_TIMEOUT
        ):
            left = NEUTRAL_PWM
            right = NEUTRAL_PWM

            if not self.timed_out:
                self.get_logger().warning(
                    "/cmd_vel timeout -> neutral"
                )

                self.timed_out = True

        else:
            left = self.target_left
            right = self.target_right

        try:

            # int16 little-endian 2개
            packet = struct.pack(
                "<hh",
                int(left),
                int(right)
            )

            self.sock.sendto(
                packet,
                GATEWAY_ADDR
            )

        except Exception as error:

            self.get_logger().warning(
                f"UDP send error: {error}"
            )

    def send_neutral(self):

        try:

            packet = struct.pack(
                "<hh",
                NEUTRAL_PWM,
                NEUTRAL_PWM
            )

            # 종료 시 여러 번 중립 전송
            for _ in range(5):

                self.sock.sendto(
                    packet,
                    GATEWAY_ADDR
                )

                time.sleep(0.02)

            self.get_logger().info(
                "Neutral PWM sent"
            )

        except Exception as error:

            self.get_logger().warning(
                f"Failed to send neutral: {error}"
            )


def main(args=None):

    rclpy.init(args=args)

    node = ThrusterDriverNode()

    try:

        rclpy.spin(node)

    except KeyboardInterrupt:

        pass

    finally:

        node.send_neutral()

        node.destroy_node()

        rclpy.shutdown()


if __name__ == "__main__":
    main()
