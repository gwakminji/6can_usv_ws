"""GUI·수질센서 없이 펌프 동작을 검증하는 대화형 테스트.

조이스틱 버튼과 B1 수질센서를 키보드로 흉내낸다. 가짜 값을 실제 ROS 토픽으로
발행하므로 actuator_driver_node의 로직(수동 60초 우선, auto_mode 토글,
3단계 판정, 히스테리시스, 5초 두절 시 정지)이 그대로 동작한다.

수질은 B1처럼 1초 주기로 계속 발행한다. 한 번만 쏘면 5초 뒤 두절로 판정되어
펌프가 꺼지기 때문이다.
"""

import json
import threading
import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool, ColorRGBA, String

HELP = """
──────────────────────────────────────────────
  a  A버튼 누름      → /actuator/pump_cmd True
  s  A버튼 뗌        → /actuator/pump_cmd False
  b  B버튼           → /actuator/auto_mode 토글

  1  수질 나쁨 25%   (펌프 ON 예상)
  2  수질 보통 50%
  3  수질 좋음 70%
  4  수질 41%        (BAD에서 유지되면 히스테리시스 정상)

  0  수질 발행 중단  (5초 뒤 두절 → 펌프 정지 확인)
  r  수질 발행 재개
  p  현재 상태 보기
  h  도움말
  q  종료
──────────────────────────────────────────────"""


class ManualTest(Node):

    def __init__(self):
        super().__init__('manual_test')

        self.pump_pub = self.create_publisher(Bool, '/actuator/pump_cmd', 10)
        self.auto_pub = self.create_publisher(Bool, '/actuator/auto_mode', 10)
        self.wq_pub = self.create_publisher(String, '/water_quality/data', 10)

        # 노드가 실제로 적용한 값. 이게 검증의 핵심 신호다.
        self.create_subscription(Bool, '/actuator/pump_state', self.on_pump_state, 10)
        self.create_subscription(ColorRGBA, '/actuator/led_state', self.on_led_state, 10)

        self.auto_mode = True          # joy_to_cmd_node의 기본값과 동일
        self.clarity = 70.0
        self.publishing = True
        self.pump_state = None

    def on_pump_state(self, msg: Bool):
        if self.pump_state != msg.data:
            self.pump_state = msg.data
            print(f'\n  >>> 실제 펌프 상태: {"ON  💧" if msg.data else "OFF"}')

    def on_led_state(self, msg: ColorRGBA):
        rgb = (round(msg.r * 255), round(msg.g * 255), round(msg.b * 255))
        print(f'  >>> 실제 LED: {rgb}')

    def publish_wq(self):
        msg = String()
        msg.data = json.dumps({'clarity_pct': self.clarity})
        self.wq_pub.publish(msg)

    def wq_loop(self):
        """B1처럼 1초 주기로 계속 발행한다."""
        while rclpy.ok():
            if self.publishing:
                self.publish_wq()
            time.sleep(1.0)


def main():
    rclpy.init()
    node = ManualTest()

    threading.Thread(target=rclpy.spin, args=(node,), daemon=True).start()
    threading.Thread(target=node.wq_loop, daemon=True).start()
    time.sleep(1.5)

    print(HELP)
    print(f'\n초기 상태: 자동={node.auto_mode}, 수질={node.clarity}%')

    try:
        while True:
            cmd = input('\n> ').strip().lower()

            if cmd == 'a':
                node.pump_pub.publish(Bool(data=True))
                print('  A버튼 누름 → pump_cmd=True (이후 60초간 자동 억제)')
            elif cmd == 's':
                node.pump_pub.publish(Bool(data=False))
                print('  A버튼 뗌 → pump_cmd=False (이후 60초간 자동 억제)')
            elif cmd == 'b':
                node.auto_mode = not node.auto_mode
                node.auto_pub.publish(Bool(data=node.auto_mode))
                print(f'  B버튼 → 자동 제어 {"ON" if node.auto_mode else "OFF"}')
            elif cmd in ('1', '2', '3', '4'):
                node.clarity = {'1': 25.0, '2': 50.0, '3': 70.0, '4': 41.0}[cmd]
                node.publishing = True
                node.publish_wq()
                print(f'  수질 {node.clarity}% 발행 (1초마다 반복)')
            elif cmd == '0':
                node.publishing = False
                print('  수질 발행 중단 — 5초 뒤 두절 판정으로 펌프가 꺼져야 정상')
            elif cmd == 'r':
                node.publishing = True
                print(f'  수질 {node.clarity}% 발행 재개')
            elif cmd == 'p':
                print(f'  자동={node.auto_mode}  수질={node.clarity}%  '
                      f'발행={node.publishing}  실제펌프={node.pump_state}')
            elif cmd == 'h':
                print(HELP)
            elif cmd == 'q':
                break
            elif cmd:
                print('  모르는 명령입니다. h로 도움말.')
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        # 어떻게 끝나든 안전 상태로 되돌린다
        print('\n정리 중...')
        node.pump_pub.publish(Bool(data=False))
        node.auto_pub.publish(Bool(data=True))
        node.clarity = 70.0
        for _ in range(3):
            node.publish_wq()
            time.sleep(0.3)
        time.sleep(0.5)
        node.destroy_node()
        rclpy.shutdown()
        print('종료 — 펌프 OFF, 자동 제어 복구')


main()
