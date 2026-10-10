#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from sensor_msgs.msg import Joy
from geometry_msgs.msg import Twist
from std_msgs.msg import Bool
from std_msgs.msg import Header


class JoyToCmdNode(Node):
    def __init__(self):
        super().__init__('joy_to_cmd_node')

        # ===== 사용자 설정: 축·버튼 번호, 속도 제한 =====
        # launch 인자로 전달한 값이 아래 기본값보다 우선한다.
        self.declare_parameter('linear_axis', 1)       # 전진/후진 축
        self.declare_parameter('angular_axis', 0)      # 좌회전/우회전 축
        self.declare_parameter('linear_scale', 1.0)     # m/s
        self.declare_parameter('angular_scale', -1.0)   # rad/s, 조이스틱 축 방향 보정
        self.declare_parameter('deadzone', 0.05)
        self.declare_parameter('linear_ramp_rate', 0.2)  # m/s^2, 속도 변화 제한
        self.declare_parameter('angular_ramp_rate', 0.4)  # rad/s^2
        self.declare_parameter('pump_button', 0)       # Xbox A 버튼
        self.declare_parameter('auto_button', 1)       # Xbox B 버튼
        self.declare_parameter('enable_heartbeat', False)
        self.declare_parameter('heartbeat_period_sec', 0.5)

        self.linear_axis = self.get_parameter('linear_axis').value
        self.angular_axis = self.get_parameter('angular_axis').value
        self.linear_scale = self.get_parameter('linear_scale').value
        self.angular_scale = self.get_parameter('angular_scale').value
        self.deadzone = self.get_parameter('deadzone').value
        self.linear_ramp_rate = self.get_parameter('linear_ramp_rate').value
        self.angular_ramp_rate = self.get_parameter('angular_ramp_rate').value
        self.pump_button = self.get_parameter('pump_button').value
        self.auto_button = self.get_parameter('auto_button').value
        self.enable_heartbeat = self.get_parameter('enable_heartbeat').value
        self.heartbeat_period_sec = self.get_parameter('heartbeat_period_sec').value

        qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
        )

        self.joy_sub = self.create_subscription(Joy, '/joy', self.joy_callback, qos)
        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel', qos)
        self.pump_pub = self.create_publisher(Bool, '/actuator/pump_cmd', qos)
        self.auto_mode_pub = self.create_publisher(Bool, '/actuator/auto_mode', qos)
        # 게임 상태는 펌프·자동 모드에만 적용한다. 배 이동은 항상 허용한다.
        self.create_subscription(Bool, '/gcs/game_active', self.on_game_active, qos)
        self.game_active = False

        self._last_joy_time = None
        self.current_linear = 0.0
        self.current_angular = 0.0

        self.heartbeat_pub = None
        if self.enable_heartbeat:
            self.heartbeat_pub = self.create_publisher(Header, '/gcs/heartbeat', qos)
            self.heartbeat_timer = self.create_timer(
                self.heartbeat_period_sec, self.heartbeat_callback
            )

        self.get_logger().info('joy_to_cmd_node started')
        self.prev_pump_state = False
        self.prev_auto_button_state = False
        self.auto_mode = False

        # 첫 조이스틱 입력 전에도 수동 모드를 전달한다.
        auto_msg = Bool()
        auto_msg.data = self.auto_mode
        self.auto_mode_pub.publish(auto_msg)

    @staticmethod
    def _ramp(current: float, target: float, rate: float, dt: float) -> float:
        """current를 target 방향으로 초당 rate만큼만 움직인다 (급변 방지)."""
        if rate <= 0.0 or dt <= 0.0:
            return target
        max_step = rate * dt
        diff = target - current
        if diff > max_step:
            return current + max_step
        if diff < -max_step:
            return current - max_step
        return target

    def joy_callback(self, msg: Joy):
        now = self.get_clock().now()
        dt = (now - self._last_joy_time).nanoseconds / 1e9 if self._last_joy_time else 0.0
        self._last_joy_time = now

        twist = Twist()
        linear = msg.axes[self.linear_axis] if len(msg.axes) > self.linear_axis else 0.0
        angular = msg.axes[self.angular_axis] if len(msg.axes) > self.angular_axis else 0.0

        if abs(linear) < self.deadzone:
            linear = 0.0
        if abs(angular) < self.deadzone:
            angular = 0.0

        target_linear = linear * self.linear_scale
        target_angular = angular * self.angular_scale
        self.current_linear = self._ramp(self.current_linear, target_linear, self.linear_ramp_rate, dt)
        self.current_angular = self._ramp(self.current_angular, target_angular, self.angular_ramp_rate, dt)

        twist.linear.x = self.current_linear
        twist.angular.z = -self.current_angular  # 추진기로 보내는 회전 방향만 반전

        self.cmd_pub.publish(twist)

        # 버튼 눌림 상태는 항상 추적하고, 명령은 게임 중에만 발행한다.
        if len(msg.buttons) > self.pump_button:
            new_state = bool(msg.buttons[self.pump_button])
            if self.game_active and not self.auto_mode and new_state != self.prev_pump_state:
                pump_msg = Bool()
                pump_msg.data = new_state
                self.pump_pub.publish(pump_msg)
            self.prev_pump_state = new_state

        if len(msg.buttons) > self.auto_button:
            button_pressed = bool(msg.buttons[self.auto_button])
            if self.game_active and button_pressed and not self.prev_auto_button_state:
                self.auto_mode = not self.auto_mode
                auto_msg = Bool()
                auto_msg.data = self.auto_mode
                self.auto_mode_pub.publish(auto_msg)
            self.prev_auto_button_state = button_pressed

    def on_game_active(self, msg: Bool):
        self.game_active = bool(msg.data)

        # 게임 시작과 종료 시 자동 모드를 수동으로 초기화한다.
        if self.auto_mode:
            self.auto_mode = False
            auto_msg = Bool()
            auto_msg.data = False
            self.auto_mode_pub.publish(auto_msg)

    def heartbeat_callback(self):
        header = Header()
        header.stamp = self.get_clock().now().to_msg()
        header.frame_id = 'joy_to_cmd_node'
        self.heartbeat_pub.publish(header)


def main(args=None):
    rclpy.init(args=args)
    node = JoyToCmdNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
