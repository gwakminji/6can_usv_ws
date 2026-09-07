#!/bin/bash
# 대화형 펌프 테스트. usv_act 컨테이너 안에서 실행한다.
#
# 컨테이너가 다르면 /dev/shm이 분리되어 FastDDS 공유메모리 전송이 실패하고,
# 에러 없이 메시지가 사라진다. 그래서 이미 ROS 노드가 도는 컨테이너 안으로
# 스크립트를 넣어서 실행한다.

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

if ! docker ps --format '{{.Names}}' | grep -q '^usv_act$'; then
    echo "❌ usv_act 컨테이너가 안 돌고 있습니다."
    echo "   먼저 ROS 노드를 띄우세요 (start_actuators.sh 또는 docker run)."
    exit 1
fi

docker cp "$SCRIPT_DIR/manual_test.py" usv_act:/tmp/manual_test.py
docker exec -it usv_act bash -c \
    'source /opt/ros/jazzy/setup.bash && source /ros2_ws/install/setup.bash && python3 /tmp/manual_test.py'
