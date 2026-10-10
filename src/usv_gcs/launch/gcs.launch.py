"""조이스틱과 GCS 대시보드를 실행한다.

아래 launch 인자는 실행 시 덮어쓸 수 있다. camera_host가 비어 있으면
config/gcs_params.yaml 값을 사용한다.
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    # ===== 사용자 설정: 실행 시 name:=value로 변경 =====
    http_port_arg = DeclareLaunchArgument(
        'http_port', default_value='8000',
        description='gui_main_node 웹 대시보드 포트',
    )
    linear_axis_arg = DeclareLaunchArgument(
        'linear_axis', default_value='1',
        description='조이스틱 전진/후진 축 번호',
    )
    angular_axis_arg = DeclareLaunchArgument(
        'angular_axis', default_value='0',
        description='조이스틱 좌/우 회전 축 번호',
    )
    linear_scale_arg = DeclareLaunchArgument('linear_scale', default_value='1.0')
    angular_scale_arg = DeclareLaunchArgument('angular_scale', default_value='-1.0')
    # 램프 속도와 데드존은 joy_to_cmd_node.py의 기본 파라미터에서 변경한다.
    pump_button_arg = DeclareLaunchArgument(
        'pump_button', default_value='0',
        description='펌프/워터캐논 작동 버튼 번호',
    )
    auto_button_arg = DeclareLaunchArgument(
        'auto_button', default_value='1',
        description='자동/수동 제어 토글 버튼 번호',
    )
    camera_host_arg = DeclareLaunchArgument(
        'camera_host', default_value='',
        description='B1 카메라 보드 IP (비우면 gcs_params.yaml 사용)',
    )

    return LaunchDescription([
        http_port_arg,
        linear_axis_arg,
        angular_axis_arg,
        linear_scale_arg,
        angular_scale_arg,
        pump_button_arg,
        auto_button_arg,
        camera_host_arg,
        Node(package='joy', executable='joy_node', name='joy_node'),
        Node(
            package='usv_gcs', executable='joy_to_cmd_node', name='joy_to_cmd_node',
            parameters=[{
                'linear_axis': ParameterValue(LaunchConfiguration('linear_axis'), value_type=int),
                'angular_axis': ParameterValue(LaunchConfiguration('angular_axis'), value_type=int),
                'linear_scale': ParameterValue(LaunchConfiguration('linear_scale'), value_type=float),
                'angular_scale': ParameterValue(LaunchConfiguration('angular_scale'), value_type=float),
                'pump_button': ParameterValue(LaunchConfiguration('pump_button'), value_type=int),
                'auto_button': ParameterValue(LaunchConfiguration('auto_button'), value_type=int),
            }],
        ),
        Node(
            package='usv_gcs', executable='gui_main_node', name='gui_main_node',
            parameters=[{
                'http_port': ParameterValue(LaunchConfiguration('http_port'), value_type=int),
                'camera_host': ParameterValue(LaunchConfiguration('camera_host'), value_type=str),
            }],
        ),
    ])
