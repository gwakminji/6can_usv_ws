"""ROS 상태를 수집해 웹 대시보드에 제공하는 GCS 노드."""

import json
import os
import threading

import yaml

from ament_index_python.packages import get_package_share_directory

import rclpy
from rclpy.node import Node

from flask import Flask, jsonify, request

from geometry_msgs.msg import Twist
from sensor_msgs.msg import NavSatFix
from std_msgs.msg import Bool
from std_msgs.msg import ColorRGBA
from std_msgs.msg import String

from .dashboard_html import INDEX_HTML

# ===== 사용자 설정 =====
# 테스트할 때만 True로 설정한다. GPS는 웹 미니맵에서만 사용한다.
USE_FIXED_GPS = False
INITIAL_LATITUDE = 37.3898
INITIAL_LONGITUDE = 126.6390


class GuiMainNode(Node):

    def __init__(self):
        super().__init__('gui_main_node')

        self.declare_parameter('http_port', 8000)
        self.use_fixed_gps = USE_FIXED_GPS
        # launch 인자가 비어 있으면 config/gcs_params.yaml의 B1 주소를 사용한다.
        self.declare_parameter('camera_host', '')

        self.state_lock = threading.Lock()
        self.state = {
            'water_quality': None,
            'gps_fix': None,
            'gps_has_fix': None,
            'cmd_vel': None,
            'pump_on': None,
            'pump_state': None,
            # joy_to_cmd_node의 기본 모드와 일치시킨다.
            'auto_mode': False,
            # 실제 LED 상태를 받기 전에는 알 수 없다.
            'led_on': None,
        }

        if self.use_fixed_gps:
            self.state['gps_fix'] = {
                'latitude': INITIAL_LATITUDE,
                'longitude': INITIAL_LONGITUDE,
            }
            self.state['gps_has_fix'] = True

        self.create_subscription(String, '/water_quality/data', self.on_water_quality, 10)
        self.create_subscription(NavSatFix, '/gps/fix', self.on_gps_fix, 10)
        self.create_subscription(Bool, '/gps/has_fix', self.on_gps_has_fix, 10)
        self.create_subscription(Twist, '/cmd_vel', self.on_cmd_vel, 10)
        self.create_subscription(Bool, '/actuator/pump_cmd', self.on_pump_cmd, 10)
        self.create_subscription(Bool, '/actuator/pump_state', self.on_pump_state, 10)
        self.create_subscription(Bool, '/actuator/auto_mode', self.on_auto_mode, 10)
        self.create_subscription(ColorRGBA, '/actuator/led_state', self.on_led_state, 10)
        self.led_cmd_pub = self.create_publisher(ColorRGBA, '/actuator/led_cmd', 10)
        # 게임 상태는 펌프·자동 모드 제어용으로 중계한다.
        self.game_active_pub = self.create_publisher(Bool, '/gcs/game_active', 10)
        self.publish_game_active(False)

        self.get_logger().info('GUI main node started')

    def publish_led_cmd(self, on: bool):
        msg = ColorRGBA()
        msg.r = msg.g = msg.b = 1.0 if on else 0.0
        msg.a = 1.0
        self.led_cmd_pub.publish(msg)

    def publish_game_active(self, active: bool):
        msg = Bool()
        msg.data = active
        self.game_active_pub.publish(msg)

    def on_water_quality(self, msg: String):
        try:
            data = json.loads(msg.data)
        except (TypeError, ValueError):
            return
        with self.state_lock:
            self.state['water_quality'] = data

    def on_gps_fix(self, msg: NavSatFix):
        if self.use_fixed_gps:
            return
        with self.state_lock:
            self.state['gps_fix'] = {'latitude': msg.latitude, 'longitude': msg.longitude}

    def on_gps_has_fix(self, msg: Bool):
        if self.use_fixed_gps:
            return
        with self.state_lock:
            self.state['gps_has_fix'] = msg.data

    def on_cmd_vel(self, msg: Twist):
        with self.state_lock:
            self.state['cmd_vel'] = {
                'linear_x': msg.linear.x,
                'angular_z': -msg.angular.z,  # 웹 조이스틱 표시 방향
            }

    def on_pump_cmd(self, msg: Bool):
        with self.state_lock:
            self.state['pump_on'] = msg.data

    def on_pump_state(self, msg: Bool):
        with self.state_lock:
            self.state['pump_state'] = msg.data

    def on_auto_mode(self, msg: Bool):
        with self.state_lock:
            self.state['auto_mode'] = msg.data

    def on_led_state(self, msg: ColorRGBA):
        with self.state_lock:
            self.state['led_on'] = msg.r > 0.0 or msg.g > 0.0 or msg.b > 0.0

    def snapshot(self):
        with self.state_lock:
            return dict(self.state)


def _config_paths() -> list:
    """설치 경로와 소스 트리의 일반 설정 파일 경로를 반환한다."""
    paths = []
    try:
        paths.append(
            os.path.join(get_package_share_directory('usv_gcs'), 'config', 'gcs_params.yaml')
        )
    except Exception:
        pass
    src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    paths.append(os.path.join(src_dir, 'config', 'gcs_params.yaml'))
    return paths


def _secrets_config_paths() -> list:
    """Git에서 제외한 API 키 설정 파일의 후보 경로를 반환한다."""
    paths = []
    try:
        paths.append(
            os.path.join(get_package_share_directory('usv_gcs'), 'config', 'gcs_secrets.yaml')
        )
    except Exception:
        pass
    src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    paths.append(os.path.join(src_dir, 'config', 'gcs_secrets.yaml'))
    return paths


def _google_maps_api_key_from_config(node: GuiMainNode) -> str:
    """비밀 설정 파일에서 Google Maps API 키를 읽는다."""
    for config_path in _secrets_config_paths():
        try:
            with open(config_path) as f:
                data = yaml.safe_load(f) or {}
        except (OSError, yaml.YAMLError):
            continue
        key = str(data.get('google_maps_api_key') or '')
        if key:
            node.get_logger().info(f'google_maps_api_key 설정됨 ({config_path})')
            return key
    return ''


def _camera_host_from_config(node: GuiMainNode) -> str:
    """launch 인자가 없을 때 일반 설정 파일에서 B1 주소를 읽는다."""
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
    web_dir = get_package_share_directory('usv_gcs') + '/web'
    app = Flask(__name__, static_folder=web_dir, static_url_path='')

    # launch 인자가 설정 파일보다 우선한다.
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
    google_maps_api_key = _google_maps_api_key_from_config(node)

    rendered_index_html = (
        INDEX_HTML
        .replace('__CAMERA_HOST__', camera_host)
        .replace('__GOOGLE_MAPS_API_KEY__', google_maps_api_key)
    )

    @app.get('/')
    def index():
        return rendered_index_html

    @app.get('/api/state')
    def api_state():
        return jsonify(node.snapshot())

    @app.post('/api/led')
    def api_led():
        body = request.get_json(silent=True) or {}
        on = bool(body.get('on'))
        node.publish_led_cmd(on)
        return jsonify({'ok': True, 'on': on})

    # 게임 시작·종료 시 LED를 끄고 게임 상태를 전달한다.
    @app.post('/api/game_active')
    def api_game_active():
        body = request.get_json(silent=True) or {}
        active = bool(body.get('active'))
        node.publish_game_active(active)
        node.publish_led_cmd(False)
        return jsonify({'ok': True, 'active': active})

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
