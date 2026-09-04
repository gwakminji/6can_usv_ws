"""GCS(Raspberry Pi) launch 파일 — joy_node + joy_to_cmd_node + gui_main_node + web_video_server.

조이스틱 축 번호를 확정한 뒤에는 코드를 고치지 말고 인자로 넘기면 된다:

    ros2 launch usv_gcs gcs.launch.py linear_axis:=1 angular_axis:=0

web_video_port를 기본값(8080)에서 바꾸면 usv_gcs/dashboard_html.py의
WEB_VIDEO_PORT 상수도 같이 바꿔야 한다 (웹 페이지는 브라우저에서 JS로 직접 접속하므로
launch 인자가 자동으로 전달되지 않는다).
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    http_port_arg = DeclareLaunchArgument(
        'http_port', default_value='8000',
        description='gui_main_node 웹 대시보드 포트',
    )
    web_video_port_arg = DeclareLaunchArgument(
        'web_video_port', default_value='8080',
        description='web_video_server 포트',
    )
    linear_axis_arg = DeclareLaunchArgument(
        'linear_axis', default_value='1',
        description='조이스틱 전진/후진 축 번호 (GCS 담당자가 실제 조이스틱 기준으로 확정)',
    )
    angular_axis_arg = DeclareLaunchArgument(
        'angular_axis', default_value='0',
        description='조이스틱 좌/우 회전 축 번호',
    )
    linear_scale_arg = DeclareLaunchArgument('linear_scale', default_value='1.0')
    # 실측: 오른쪽으로 밀면 axes[0]=-1.0 이라서, 우회전 시 angular가 +가 되도록 부호 반전
    angular_scale_arg = DeclareLaunchArgument('angular_scale', default_value='-1.0')
    pump_button_arg = DeclareLaunchArgument(
        'pump_button', default_value='0',
        description='펌프/워터캐논 작동 버튼 번호 (GCS 담당자가 실제 조이스틱 기준으로 확정)',
    )

    return LaunchDescription([
        http_port_arg,
        web_video_port_arg,
        linear_axis_arg,
        angular_axis_arg,
        linear_scale_arg,
        angular_scale_arg,
        pump_button_arg,
        Node(package='joy', executable='joy_node', name='joy_node'),
        Node(
            package='usv_gcs', executable='joy_to_cmd_node', name='joy_to_cmd_node',
            parameters=[{
                'linear_axis': ParameterValue(LaunchConfiguration('linear_axis'), value_type=int),
                'angular_axis': ParameterValue(LaunchConfiguration('angular_axis'), value_type=int),
                'linear_scale': ParameterValue(LaunchConfiguration('linear_scale'), value_type=float),
                'angular_scale': ParameterValue(LaunchConfiguration('angular_scale'), value_type=float),
                'pump_button': ParameterValue(LaunchConfiguration('pump_button'), value_type=int),
            }],
        ),
        Node(
            package='usv_gcs', executable='gui_main_node', name='gui_main_node',
            parameters=[{'http_port': ParameterValue(LaunchConfiguration('http_port'), value_type=int)}],
        ),
        Node(
            package='web_video_server', executable='web_video_server', name='web_video_server',
            parameters=[{'port': ParameterValue(LaunchConfiguration('web_video_port'), value_type=int)}],
        ),
    ])
