"""usv_actuators App Lab 앱의 파이썬 부분.

실제 제어는 도커에서 도는 ROS 노드(actuator_driver_node)가 RouterBridge RPC로
직접 수행한다. 이 파일은 App Lab 앱 프로세스를 살려두는 역할만 한다.

앱이 살아있어야 MCU 스케치의 RPC 핸들러 등록이 유지된다. 파이썬 부분이 없으면
App Lab이 앱을 종료시켜 set_pump 등록이 사라지고, 명령을 보내도 조용히
무시된다(Bridge.notify는 실패해도 예외를 던지지 않는다).
"""

import time

from arduino.app_utils import App

print("usv_actuators app running — MCU RPC handlers registered")


def loop():
    time.sleep(5)


App.run(user_loop=loop)
