"""gui_main_node — usv_gcs 패키지 (Raspberry Pi).

구독:
  /water_quality/data [std_msgs/msg/String]         JSON 파싱해서 표시
  /gps/fix             [sensor_msgs/msg/NavSatFix]
  /gps/has_fix         [std_msgs/msg/Bool]           false면 'GPS 신호 없음' 배너
  /battery/status      [std_msgs/msg/String]         JSON 파싱: thruster1, thruster2,
                                                       pump_ctrl, sensor_board 각각
                                                       {current_a, percentage}
  /cmd_vel             [geometry_msgs/msg/Twist]     조이스틱 인디케이터 표시용
  /actuator/pump_cmd   [std_msgs/msg/Bool]           joy_to_cmd_node가 조이스틱 버튼으로
                                                       발행 - 여기선 상태 표시용으로만 구독
  /actuator/pump_state [std_msgs/msg/Bool]           B2가 발행하는 펌프 실제 상태(명령과
                                                       다를 수 있음) - 상태 표시용으로만 구독
  /actuator/auto_mode  [std_msgs/msg/Bool]           joy_to_cmd_node가 조이스틱 버튼으로
                                                       발행 - 여기선 상태 표시용으로만 구독

조종은 조이스틱 하나로만 하므로(마우스로 GUI 버튼을 누를 사람이 없음) 펌프와 자동/수동
전환은 joy_to_cmd_node가 조이스틱 버튼으로 발행하고, 이 노드는 그 상태를 /api/state로
보여주기만 한다.

듀얼 카메라 MJPEG 스트림은 이 노드가 직접 발행하지 않는다. B1 보드의 camera_streaming
패키지(별도 컨테이너)가 http_video_server로 /camera/surface/image_raw,
/camera/underwater/image_raw 토픽을 B1 자신의 8000번 포트에서 HTTP로 변환해 서빙하고,
이 노드의 웹 대시보드(dashboard_html.py)는 camera_host 파라미터로 그 주소를 알아내
<img> 태그로 그대로 표시한다.

camera_host는 두 가지 방법으로 줄 수 있다: (1) launch 인자로 매번 넘기거나
(2) config/gcs_params.yaml에 한 번 적어두기. launch 인자를 안 넘기면(빈 문자열 기본값)
이 노드가 gcs_params.yaml을 읽어서 대신 쓴다 — launch 인자가 우선이다.

전류 센서 4개(추진기1/2, 펌프 제어부, 센서 보드)는 전부 B1 보드에 물려있어서
usv_sensors의 current_sensor_node가 /battery/status 하나로 통합 발행한다. 예전에
usv_actuators가 따로 발행하던 /battery/thruster, /battery/actuator는 삭제되었다.

배터리 경고 기준(BATTERY_WARNING_PCT)은 구체적인 배터리 사양이 아직 정해지지 않아서 20%로
임시 지정했다. 실제 배터리 사양이 정해지면 이 값을 조정해야 한다.
"""

import json
import os
import threading

import yaml

from ament_index_python.packages import get_package_share_directory

import rclpy
from rclpy.node import Node

from flask import Flask, jsonify

from geometry_msgs.msg import Twist
from sensor_msgs.msg import NavSatFix
from std_msgs.msg import Bool
from std_msgs.msg import String

from .dashboard_html import INDEX_HTML

# TODO(GCS 담당자): 실제 배터리 사양이 정해지면 경고 기준치를 조정할 것.
BATTERY_WARNING_PCT = 20


class GuiMainNode(Node):

    def __init__(self):
        super().__init__('gui_main_node')

        self.declare_parameter('http_port', 8000)
        # 카메라 스트림은 GCS가 아니라 B1 보드 위 camera_streaming 패키지(http_video_server,
        # 고정 포트 8000)가 직접 서빙한다. GCS는 B1의 IP를 알 방법이 없으므로 launch 인자로
        # 받는다. 비워두면(기본값) create_app()이 config/gcs_params.yaml을 대신 읽는다 -
        # 매번 launch 인자로 IP를 안 넘기고 싶으면 그 파일에 한 번만 적어두면 된다.
        self.declare_parameter('camera_host', '')

        self.state_lock = threading.Lock()
        self.state = {
            'water_quality': None,
            'gps_fix': None,
            'gps_has_fix': None,
            'battery_status': None,
            'cmd_vel': None,
            'pump_on': None,
            'pump_state': None,
            # joy_to_cmd_node/actuator_driver_node 둘 다 항상 자동 모드로 시작하므로 기본값을
            # True로 맞춰둔다 - /actuator/auto_mode가 volatile QoS라 joy_to_cmd_node의 시작 시
            # 발행(joy_to_cmd_node.py 참고)을 GCS가 늦게 구독 시작하면 놓칠 수 있어, None으로
            # 두면 실제로는 자동인데도 대시보드에 아무 표시등도 안 켜지는 문제가 있었다.
            'auto_mode': True,
        }

        self.create_subscription(String, '/water_quality/data', self.on_water_quality, 10)
        self.create_subscription(NavSatFix, '/gps/fix', self.on_gps_fix, 10)
        self.create_subscription(Bool, '/gps/has_fix', self.on_gps_has_fix, 10)
        self.create_subscription(String, '/battery/status', self.on_battery_status, 10)
        self.create_subscription(Twist, '/cmd_vel', self.on_cmd_vel, 10)
        self.create_subscription(Bool, '/actuator/pump_cmd', self.on_pump_cmd, 10)
        self.create_subscription(Bool, '/actuator/pump_state', self.on_pump_state, 10)
        self.create_subscription(Bool, '/actuator/auto_mode', self.on_auto_mode, 10)

        self.get_logger().info('GUI main node started')

    def on_water_quality(self, msg: String):
        try:
            data = json.loads(msg.data)
        except (TypeError, ValueError): 
            return
        with self.state_lock:
            self.state['water_quality'] = data

    def on_gps_fix(self, msg: NavSatFix):
        with self.state_lock:
            self.state['gps_fix'] = {'latitude': msg.latitude, 'longitude': msg.longitude}

    def on_gps_has_fix(self, msg: Bool):
        with self.state_lock:
            self.state['gps_has_fix'] = msg.data

    def on_battery_status(self, msg: String):
        try:
            data = json.loads(msg.data)
        except (TypeError, ValueError):
            return
        with self.state_lock:
            self.state['battery_status'] = data

    def on_cmd_vel(self, msg: Twist):
        with self.state_lock:
            self.state['cmd_vel'] = {'linear_x': msg.linear.x, 'angular_z': msg.angular.z}

    def on_pump_cmd(self, msg: Bool):
        with self.state_lock:
            self.state['pump_on'] = msg.data

    def on_pump_state(self, msg: Bool):
        with self.state_lock:
            self.state['pump_state'] = msg.data

    def on_auto_mode(self, msg: Bool):
        with self.state_lock:
            self.state['auto_mode'] = msg.data

    def snapshot(self):
        with self.state_lock:
            return dict(self.state)


def _config_paths() -> list:
    """gcs_params.yaml을 찾을 후보 경로들 (install 우선, 없으면 소스 트리).

    install 쪽을 먼저 보되, config/가 설치되기 전에 빌드된 install 디렉터리가 남아있으면
    (실제로 그랬다) 소스 트리의 config/gcs_params.yaml을 그대로 읽는다. 안 그러면 값을
    적어놨는데도 조용히 빈 문자열이 돼서 카메라가 GCS 자신을 가리키게 된다.
    """
    paths = []
    try:
        paths.append(
            os.path.join(get_package_share_directory('usv_gcs'), 'config', 'gcs_params.yaml')
        )
    except Exception:
        pass
    # .../src/usv_gcs/usv_gcs/gui_main_node.py -> .../src/usv_gcs/config/gcs_params.yaml
    src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    paths.append(os.path.join(src_dir, 'config', 'gcs_params.yaml'))
    return paths


def _camera_host_from_config(node: GuiMainNode) -> str:
    """config/gcs_params.yaml의 camera_host 값을 읽는다 (launch 인자를 안 넘겼을 때 폴백).

    B1 IP가 자주 안 바뀌면 launch 인자로 매번 넘기는 대신 이 파일에 한 번만 적어두는 게
    편하다. 어느 파일을 읽었는지 로그로 남긴다 - 조용히 실패하면 원인을 찾기 어렵다.
    """
    for config_path in _config_paths():
        try:
            with open(config_path) as f:
                data = yaml.safe_load(f) or {}
        except (OSError, yaml.YAMLError):
            continue
        host = str(data.get('camera_host') or '')
        if host:
            node.get_logger().info(f'camera_host={host} ({config_path})')
            return host
    return ''


def create_app(node: GuiMainNode) -> Flask:
    # 대시보드(INDEX_HTML)가 참조하는 배/물고기/쓰레기 이미지 에셋은 web/에 설치되어 있고,
    # static_url_path=''라서 "lake.png" 같은 상대 경로 그대로 루트에서 서빙된다.
    web_dir = get_package_share_directory('usv_gcs') + '/web'
    app = Flask(__name__, static_folder=web_dir, static_url_path='')

    # launch 인자가 우선, 안 넘겼으면(빈 문자열) gcs_params.yaml을 대신 읽는다.
    camera_host = str(node.get_parameter('camera_host').value or '').strip()
    if camera_host:
        node.get_logger().info(f'camera_host={camera_host} (launch 인자)')
    else:
        camera_host = _camera_host_from_config(node)
    if not camera_host:
        node.get_logger().error(
            'camera_host가 비어있다 - 카메라 스트림 주소를 만들 수 없다. '
            'config/gcs_params.yaml에 B1 보드 IP를 적거나 '
            'ros2 launch usv_gcs gcs.launch.py camera_host:=<B1_IP> 로 넘길 것.'
        )
    rendered_index_html = INDEX_HTML.replace('__CAMERA_HOST__', camera_host)

    @app.get('/')
    def index():
        return rendered_index_html

    @app.get('/api/state')
    def api_state():
        state = node.snapshot()
        state['battery_warning_pct'] = BATTERY_WARNING_PCT
        return jsonify(state)

    return app


def main(args=None):
    rclpy.init(args=args)
    node = GuiMainNode()

    http_port = node.get_parameter('http_port').value
    app = create_app(node)
    flask_thread = threading.Thread(
        target=lambda: app.run(host='0.0.0.0', port=http_port, debug=False, use_reloader=False),
        daemon=True,
    )
    flask_thread.start()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
