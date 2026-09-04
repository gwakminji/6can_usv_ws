#!/usr/bin/env python3
"""thruster_driver_node — usv_actuators

/cmd_vel [geometry_msgs/msg/Twist] 구독
→ 좌/우 스러스터 명령 계산
→ 1500us 기준 PWM으로 변환
→ RouterBridge를 통해 Arduino MCU의 set_thruster_pwm 호출
"""

import time

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist

from .bridge import Bridge


NEUTRAL_PWM = 1500

# 처음 테스트할 때는 출력 범위를 작게 잡는 것이 안전함.
# 최대 전진: 1700us
# 최대 후진: 1300us
MAX_DELTA = 200

# 조이스틱 미세 노이즈 무시
INPUT_DEADBAND = 0.05

# /cmd_vel이 끊기면 중립으로 복귀
CMD_TIMEOUT = 0.5

# 같은 값을 계속 Bridge에 보내지 않도록 함
SEND_INTERVAL = 0.05  # 최대 20Hz


def clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


class ThrusterDriverNode(Node):

    def __init__(self):
        super().__init__('thruster_driver_node')

        self.cmd_sub = self.create_subscription(
            Twist,
            '/cmd_vel',
            self.on_cmd_vel,
            10
        )

        self.target_left = NEUTRAL_PWM
        self.target_right = NEUTRAL_PWM

        self.last_cmd_time = time.monotonic()
        self.last_send_time = 0.0

        self.last_sent_left = None
        self.last_sent_right = None

        self.timer = self.create_timer(
            0.02,
            self.control_loop
        )

        self.get_logger().info(
            'Thruster driver node started '
            '(1500us PWM / RouterBridge mode)'
        )

    def on_cmd_vel(self, msg: Twist):
        linear = clamp(msg.linear.x, -1.0, 1.0)
        angular = clamp(msg.angular.z, -1.0, 1.0)

        # 작은 입력은 0으로 처리
        if abs(linear) < INPUT_DEADBAND:
            linear = 0.0

        if abs(angular) < INPUT_DEADBAND:
            angular = 0.0

        # Differential thrust mixing
        #
        # 전진:
        # linear > 0
        # left/right 모두 +
        #
        # 회전:
        # angular > 0
        # left 감소, right 증가
        left = linear - angular
        right = linear + angular

        # 둘 중 하나가 ±1을 넘으면 비율 유지하며 정규화
        scale = max(
            1.0,
            abs(left),
            abs(right)
        )

        left /= scale
        right /= scale

        # -1.0 ~ +1.0
        #       ↓
        # 1300 ~ 1700us
        left_pwm = int(round(
            NEUTRAL_PWM + left * MAX_DELTA
        ))

        right_pwm = int(round(
            NEUTRAL_PWM + right * MAX_DELTA
        ))

        self.target_left = clamp(
            left_pwm,
            NEUTRAL_PWM - MAX_DELTA,
            NEUTRAL_PWM + MAX_DELTA
        )

        self.target_right = clamp(
            right_pwm,
            NEUTRAL_PWM - MAX_DELTA,
            NEUTRAL_PWM + MAX_DELTA
        )

        self.last_cmd_time = time.monotonic()

        self.get_logger().info(
            f'cmd_vel '
            f'linear={linear:.2f} '
            f'angular={angular:.2f} '
            f'-> L={self.target_left}us '
            f'R={self.target_right}us'
        )

    def control_loop(self):
        now = time.monotonic()

        # /cmd_vel timeout
        if now - self.last_cmd_time > CMD_TIMEOUT:
            left = NEUTRAL_PWM
            right = NEUTRAL_PWM
        else:
            left = self.target_left
            right = self.target_right

        # 너무 빠른 Bridge 호출 방지
        if now - self.last_send_time < SEND_INTERVAL:
            return

        # 값이 안 바뀌었으면 다시 보내지 않음
        if (
            left == self.last_sent_left
            and right == self.last_sent_right
        ):
            return

        try:
            result = Bridge.call(
                'set_thruster_pwm',
                int(left),
                int(right),
                timeout=2
            )

            self.last_sent_left = left
            self.last_sent_right = right
            self.last_send_time = now

            self.get_logger().info(
                f'PWM sent -> '
                f'L={left}us '
                f'R={right}us'
            )

        except Exception as error:
            self.get_logger().warning(
                f'Thruster Bridge error: {error}'
            )

    def send_neutral(self):
        try:
            Bridge.call(
                'set_thruster_pwm',
                NEUTRAL_PWM,
                NEUTRAL_PWM,
                timeout=2
            )

            self.get_logger().info(
                'Neutral command sent'
            )

        except Exception as error:
            self.get_logger().warning(
                f'Failed to send neutral: {error}'
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


if __name__ == '__main__':
    main()
