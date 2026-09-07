#!/bin/bash
set -euo pipefail

# 분수 펌프만 담당하는 보드에서 쓰는 실행 스크립트.
#
# start_actuators.sh는 추진기와 펌프가 한 보드에 있던 시절 기준이라
# actuators.launch.py(두 노드 모두)를 띄운다. 보드를 나눈 뒤로는 펌프 보드에서
# 추진기 노드가 쓸데없이 떠서 아무도 받지 않는 주소로 UDP를 계속 쏜다.
#
# 원본은 건드리지 않았다. 추진기 보드는 start_actuators.sh를 그대로 쓰면 된다.

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${USV_PUMP_PROJECT_DIR:-$SCRIPT_DIR}"
CONTAINER_NAME="usv_pump_container"
# 멀티캐스트가 막힌 환경에서 다른 기기를 유니캐스트로 찾기 위한 피어 목록.
# 세미콜론으로 여러 개를 넣을 수 있다 (예: "192.168.0.5;192.168.0.4").
# 상대편(GCS 등)에도 이 보드의 IP를 같은 방식으로 넣어야 양방향으로 붙는다.
ROS_PEERS="${USV_ROS_PEERS:-192.168.0.5}"
IMAGE_NAME="usv_actuators_image"

cd "$PROJECT_DIR"

# App Lab(arduino-app-cli)은 ~/ArduinoApps/ 아래를 재귀적으로 훑어서 app.yaml이
# 있는 폴더를 앱으로 인식한다. 레포를 ~/ArduinoApps/ 밑에 클론했다면 심볼릭 링크
# 없이도 잡히므로 따로 등록하지 않는다. 링크를 만들면 같은 앱이 두 번 뜨고,
# App Lab 파일 브라우저가 링크를 못 따라가 내용이 비어 보인다.

# 앱 ID는 클론 위치에 따라 달라진다(예: user:6can_usv_ws/src/usv_actuators).
# app list에서 실제 ID를 찾아 쓴다.
#
# --format json의 id 필드는 base64로 인코딩되어 있어 그대로 쓰면
# "invalid app path"가 난다. 텍스트 출력의 첫 컬럼이 실제 ID다.
APP_ID="$(arduino-app-cli app list 2>/dev/null \
    | awk '$2 == "usv_actuators" { print $1; exit }' || true)"
APP_ID="${APP_ID:-user:usv_actuators}"

if ! docker image inspect "$IMAGE_NAME" >/dev/null 2>&1; then
    echo "[0] Docker image missing; building it..."
    docker build -t "$IMAGE_NAME" "$PROJECT_DIR"
fi

# "restart"를 쓰는 이유: "start"는 앱이 이미 돌고 있으면 "App Is Running"으로
# 실패한다. 스크립트를 두 번 실행해도 문제없게 하려는 것으로, start_sensors.sh와
# 같은 이유다.
#
# TMPDIR=/tmp: adb shell로 실행하면 TMPDIR이 /data/local/tmp(안드로이드 경로)로
# 잡혀서 스케치 빌드가 "Stat /Data/Local/Tmp: No Such File Or Directory"로 실패한다.
echo "[1] Starting Arduino App ($APP_ID)..."
TMPDIR=/tmp arduino-app-cli app restart "$APP_ID"

echo "[2] Waiting for Arduino Router..."
for _ in $(seq 1 30); do
    if [ -S /var/run/arduino-router.sock ]; then
        echo "Arduino Router ready."
        break
    fi
    sleep 1
done

if [ ! -S /var/run/arduino-router.sock ]; then
    echo "ERROR: Arduino Router socket not ready."
    exit 1
fi

echo "[3] Removing old ROS container..."
docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true

echo "[4] Starting ROS 2 container (pump only)..."
# rm -rf build install log: 이미지에 구워진 예전 install/ 디렉터리가 남아 있으면
# --symlink-install이 새로 추가된 launch 파일을 찾지 못하고 빌드가 실패한다.
docker run -d \
    --name "$CONTAINER_NAME" \
    --network host \
    --restart unless-stopped \
    --privileged \
    -e ROS_DOMAIN_ID=0 \
    -e ROS_STATIC_PEERS="$ROS_PEERS" \
    -v /dev:/dev \
    -v /var/run/arduino-router.sock:/var/run/arduino-router.sock \
    -v "$PROJECT_DIR:/ros2_ws/src/usv_actuators" \
    "$IMAGE_NAME" \
    bash -c '
        source /opt/ros/jazzy/setup.bash
        cd /ros2_ws
        rm -rf build install log
        colcon build --symlink-install --packages-select usv_actuators
        source /ros2_ws/install/setup.bash
        export ROS_DOMAIN_ID=0
        export ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET
        # ROS_STATIC_PEERS는 docker run에서 넘겨받으므로 unset 하지 않는다.
        unset ROS_LOCALHOST_ONLY
        ros2 launch usv_actuators pump.launch.py
    '

echo "[5] Pump node started (actuator_driver_node)."
echo "    ROS_STATIC_PEERS=$ROS_PEERS"
echo
echo "    로그 보기:   docker logs -f $CONTAINER_NAME"
echo "    정지:        docker rm -f $CONTAINER_NAME"
