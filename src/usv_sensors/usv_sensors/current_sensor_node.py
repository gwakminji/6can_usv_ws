"""current_sensor_node — usv_sensors 패키지 (B1 보드), 신규.

전류 센서 4개(추진기1, 추진기2, 펌프/액추에이터 제어부, 센서 보드 자체)가 전부 B1
보드에 물리적으로 연결되어 I2C 한 버스로 일괄 수신된다. B2와는 직접 통신하지 않는
단순 모니터링용 노드다.

발행: /battery/status [std_msgs/msg/String] (JSON)
  {
    "thruster1":    {"current_a": ..., "percentage": ...},
    "thruster2":    {"current_a": ..., "percentage": ...},
    "pump_ctrl":    {"current_a": ..., "percentage": ...},
    "sensor_board": {"current_a": ..., "percentage": ...}
  }

TODO(B1 담당자): 실제 전류 센서 칩(예: INA219/INA226 등)과 I2C 주소, 배터리 용량 대비
percentage 환산식이 아직 정해지지 않아서 MCU RPC 메서드 이름(get_battery_status)은
임시로 정한 것이다. Arduino 스케치(sketch/sketch.ino)에 해당 RPC 핸들러와 I2C 읽기
로직을 구현해야 실제로 동작한다 (지금 sketch.yaml에는 I2C 센서 라이브러리가 없음).
"""

import json

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from .bridge import Bridge


class CurrentSensorNode(Node):

    def __init__(self):
        super().__init__('current_sensor_node')

        self.status_pub = self.create_publisher(String, '/battery/status', 10)

        self.timer = self.create_timer(1.0, self.read_battery_status)
        self.get_logger().info('Current sensor node started')

    def read_battery_status(self):
        try:
            # TODO(B1 담당자): 'get_battery_status'는 임시 RPC 이름. 실제 스케치의
            # 핸들러 이름/반환 필드에 맞춰 확인·수정할 것.
            raw = Bridge.call('get_battery_status')
            if isinstance(raw, bytes):
                raw = raw.decode('utf-8')
            data = json.loads(str(raw))
        except Exception as error:
            self.get_logger().warning(f'Battery status Bridge error: {error}')
            return

        msg = String()
        msg.data = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
        self.status_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = CurrentSensorNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
