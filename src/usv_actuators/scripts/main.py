from arduino.app_utils import App
import time

def loop():
    # ROS 2 노드(thruster_driver_node)에서 MCU RPC를 직접 호출하므로
    # main.py는 아두이노 앱 프로세스를 유지해주는 역할만 수행합니다.
    time.sleep(1)

App.run(user_loop=loop)
