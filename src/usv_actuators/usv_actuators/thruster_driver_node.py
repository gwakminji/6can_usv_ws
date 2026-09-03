#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
import os

CMD_FILE = "/app_bridge/cmd.txt"

NEUTRAL = 1487
DEADBAND = 35
MAX_DELTA = 400

class ThrusterDriver(Node):
    def __init__(self):
        super().__init__('thruster_driver')
        self.subscription = self.create_subscription(
            Twist,
            '/cmd_vel',
            self.cmd_vel_callback,
            10
        )
        self.get_logger().info('ROS 2 Thruster Driver Started. Target: ' + CMD_FILE)

    def cmd_vel_callback(self, msg):
        linear = msg.linear.x
        angular = msg.angular.z

        left_raw = linear - angular
        right_raw = linear + angular

        left_pwm = self.calc_pwm(left_raw)
        right_pwm = self.calc_pwm(right_raw)

        try:
            tmp = CMD_FILE + ".tmp"
            with open(tmp, 'w') as f:
                f.write(f"{left_pwm},{right_pwm}\n")
            os.replace(tmp, CMD_FILE)
        except Exception as e:
            self.get_logger().error(f"Failed to write cmd.txt: {e}")

    def calc_pwm(self, val):
        if abs(val) < 0.01:
            return NEUTRAL
        
        delta = max(-MAX_DELTA, min(MAX_DELTA, int(val * MAX_DELTA)))
        
        if delta > 0:
            return NEUTRAL + DEADBAND + delta
        elif delta < 0:
            return NEUTRAL - DEADBAND + delta
        else:
            return NEUTRAL

def main(args=None):
    rclpy.init(args=args)
    node = ThrusterDriver()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            with open(CMD_FILE, 'w') as f:
                f.write(f"{NEUTRAL},{NEUTRAL}\n")
        except:
            pass
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
