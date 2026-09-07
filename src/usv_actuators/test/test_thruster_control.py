"""Control regression tests without ROS/MCU dependencies: python3 -m unittest discover -s src/usv_actuators/test."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

SOURCE = Path(__file__).resolve().parents[1] / 'usv_actuators/thruster_driver_node.py'


class ThrusterControlTest(unittest.TestCase):
    def setUp(self):
        # Load the production control code with explicit ROS and transport doubles.
        tree = ast.parse(SOURCE.read_text())
        tree.body = [n for n in tree.body if not isinstance(n, (ast.Import, ast.ImportFrom))]
        self.clock = Mock(return_value=10.0)
        self.bridge = Mock()
        self.ros = Mock()
        self.ns = dict(__name__='test_subject', Node=object, Twist=object,
                       time=SimpleNamespace(monotonic=self.clock),
                       Bridge=self.bridge, rclpy=self.ros,
                       bounded_integer=lambda v, lo, hi: max(lo, min(hi, int(v))))
        exec(compile(tree, str(SOURCE), 'exec'), self.ns)
        cls = self.ns['ThrusterDriverNode']
        self.node = cls.__new__(cls)
        self.log = Mock()
        self.node.get_logger = lambda: self.log
        self.node.cur_left = self.node.cur_right = 1487
        self.node.target_left = self.node.target_right = 1487
        self.node.last_cmd_time = None
        self.node.timed_out = True
        self.node.hold_until = 0.0
        self.node.linear = self.node.angular = 0.0

    def command(self, linear, angular):
        self.node.on_cmd_vel(SimpleNamespace(linear=SimpleNamespace(x=linear),
                                            angular=SimpleNamespace(z=angular)))

    def test_rotation_targets_and_ramped_send(self):
        self.command(0, 0.5)
        self.assertEqual((self.node.target_left, self.node.target_right), (1252, 1722))
        self.node.control_loop()
        self.bridge.notify.assert_called_with('set_thruster_pwm', 1467, 1507)
        message = self.log.info.call_args.args[0]
        self.assertIn('TARGET L=1252 R=1722', message)
        self.assertIn('SEND L=1467 R=1507', message)

    def test_timeout_overrides_reverse_hold_and_repeats_neutral(self):
        self.command(1, 0)
        self.node.cur_left = self.node.cur_right = 1700
        self.node.hold_until = 99
        self.clock.return_value = 10.5
        self.node.control_loop()
        self.node.control_loop()
        self.assertEqual((self.node.target_left, self.node.target_right), (1487, 1487))
        self.assertEqual(self.node.hold_until, 0)
        self.assertEqual(self.bridge.notify.call_count, 2)
        self.bridge.notify.assert_called_with('set_thruster_pwm', 1487, 1487)
        self.log.warning.assert_called_once()
        self.command(1, 0)
        self.node.control_loop()
        self.bridge.notify.assert_called_with('set_thruster_pwm', 1507, 1507)

    def test_startup_without_command_is_neutral(self):
        self.node.control_loop()
        self.bridge.notify.assert_called_once_with('set_thruster_pwm', 1487, 1487)

    def test_reverse_pauses_then_ramps(self):
        self.node.cur_left = self.node.cur_right = 1600
        self.command(-1, 0)
        self.node.control_loop()
        self.bridge.notify.assert_called_with('set_thruster_pwm', 1487, 1487)
        self.clock.return_value = 10.2
        self.node.control_loop()
        self.bridge.notify.assert_called_with('set_thruster_pwm', 1487, 1487)
        self.clock.return_value = 10.31
        self.node.control_loop()
        self.bridge.notify.assert_called_with('set_thruster_pwm', 1467, 1467)

    def test_shutdown_neutral_and_error_logging(self):
        node = Mock()
        self.ns['ThrusterDriverNode'] = Mock(return_value=node)
        self.ros.spin.side_effect = KeyboardInterrupt
        self.ns['main']()
        self.bridge.notify.assert_called_with('set_thruster_pwm', 1487, 1487)
        node.get_logger().info.assert_called_once()
        node.destroy_node.assert_called_once()
        self.bridge.notify.side_effect = RuntimeError('disconnected')
        self.ns['main']()
        node.get_logger().error.assert_called_once()


if __name__ == '__main__':
    unittest.main()
