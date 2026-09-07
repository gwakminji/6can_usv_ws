"""펌프 전용 launch — 분수 펌프만 담당하는 보드에서 쓴다.

추진기와 펌프를 서로 다른 보드에 나눠 싣기로 하면서 만들었다.
actuators.launch.py는 두 노드를 함께 띄우므로, 펌프만 있는 보드에서 쓰면
추진기 노드가 쓸데없이 떠서 아무도 안 받는 곳으로 UDP를 계속 쏜다.

추진기 보드는 기존 actuators.launch.py를 그대로 쓰면 되므로,
이 파일이 생겨도 추진기 쪽 실행 방식은 바뀌지 않는다.

    ros2 launch usv_actuators pump.launch.py

임계값은 실제 수조에서 clarity_pct가 어느 범위로 나오는지 보고
코드 수정 없이 조정한다:

    ros2 launch usv_actuators pump.launch.py bad_below:=35.0 good_above:=55.0
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def _float_arg(name, default, description):
    return DeclareLaunchArgument(name, default_value=default, description=description)


def generate_launch_description():
    args = [
        _float_arg('bad_below', '40.0', 'clarity_pct가 이 값 미만이면 나쁨 (펌프 ON, LED 빨강)'),
        _float_arg('good_above', '60.0', 'clarity_pct가 이 값 이상이면 좋음 (LED 초록)'),
        _float_arg('margin', '3.0', '히스테리시스 폭 — 경계에서 펌프가 떠는 것을 막는다'),
        _float_arg('pump_manual_hold_s', '60.0', 'GCS 수동 펌프 조작이 자동보다 우선하는 시간(초)'),
        _float_arg('led_manual_hold_s', '60.0', 'GCS 수동 LED 조작이 자동보다 우선하는 시간(초)'),
        _float_arg('stale_timeout_s', '5.0', '수질 데이터가 이 시간 이상 끊기면 펌프 정지'),
    ]

    def as_float(name):
        return ParameterValue(LaunchConfiguration(name), value_type=float)

    return LaunchDescription([
        *args,
        Node(
            package='usv_actuators', executable='actuator_driver_node', name='actuator_driver_node',
            parameters=[{
                'bad_below': as_float('bad_below'),
                'good_above': as_float('good_above'),
                'margin': as_float('margin'),
                'pump_manual_hold_s': as_float('pump_manual_hold_s'),
                'led_manual_hold_s': as_float('led_manual_hold_s'),
                'stale_timeout_s': as_float('stale_timeout_s'),
            }],
        ),
    ])
