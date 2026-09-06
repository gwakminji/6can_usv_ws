#!/usr/bin/env python3

import socket
import struct
import time

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist


GATEWAY_ADDR = ("127.0.0.1", 5005)

NEUTRAL_PWM = 1500
MAX_DELTA = 200
INPUT_DEADBAND = 0.05
CMD_TIMEOUT = 0.5

RATE_HZ = 20.0
DT = 1.0 / RATE_HZ


def clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


class ThrusterDriverNode(Node):

    def __init__(self):
        super().__init__("thruster_driver_node")

        self.create_subscription(
            Twist,
            "/cmd_vel",
            self.on_cmd_vel,
            10
        )

        self.sock = socket.socket(
            socket.AF_INET,
            socket.SOCK_DGRAM
        )

        self.target_left = NEUTRAL_PWM
        self.target_right = NEUTRAL_PWM

        self.last_cmd_time = 0.0
        self.timed_out = True

        self.create_timer(
            DT,
            self.control_loop
        )

        self.get_logger().info(
            f"Thruster Driver Node Started "
            f"(UDP Mode -> {GATEWAY_ADDR[0]}:{GATEWAY_ADDR[1]})"
        )

    def on_cmd_vel(self, msg: Twist):

        linear = clamp(msg.linear.x, -1.0, 1.0)
        angular = clamp(msg.angular.z, -1.0, 1.0)

        if abs(linear) < INPUT_DEADBAND:
            linear = 0.0

        if abs(angular) < INPUT_DEADBAND:
            angular = 0.0

        left = linear - angular
        right = linear + angular

        scale = max(
            1.0,
            abs(left),
            abs(right)
        )

        left /= scale
        right /= scale

        left_pwm = int(round(
            NEUTRAL_PWM + left * MAX_DELTA
        ))

        right_pwm = int(round(
            NEUTRAL_PWM + right * MAX_DELTA
        ))

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
            f"CMD linear={linear:.2f} "
            f"angular={angular:.2f} "
            f"-> L={left_pwm}us R={right_pwm}us"
        )

    def control_loop(self):

        now = time.monotonic()

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

            for _ in range(5):
                self.sock.sendto(
                    packet,
                    GATEWAY_ADDR
                )
                time.sleep(0.02)

        except Exception:
            pass


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
