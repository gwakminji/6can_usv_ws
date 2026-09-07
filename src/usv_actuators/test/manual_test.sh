#!/bin/bash
# 대화형 펌프 테스트. usv_act 컨테이너 안에서 실행한다.
# (컨테이너가 다르면 /dev/shm 분리로 DDS 메시지가 조용히 사라진다)
if ! docker ps --format '{{.Names}}' | grep -q '^usv_act$'; then
    echo "❌ usv_act 컨테이너가 안 돌고 있습니다."
    exit 1
fi
docker cp /home/arduino/manual_test.py usv_act:/tmp/manual_test.py
docker exec -it usv_act bash -c \
    'source /opt/ros/jazzy/setup.bash && source /ros2_ws/install/setup.bash && python3 /tmp/manual_test.py'
