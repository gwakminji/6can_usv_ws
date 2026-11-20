#!/bin/bash
set -euo pipefail

# B1 보드에서 usv_actuators의 actuator_driver_node만 Docker 컨테이너로 띄운다.
# start_actuators.sh(B2용)의 복사본에서 B1 사정에 맞게 고쳤다.
#
#  1. Arduino App을 시작하지 않는다.
#     펌프 스케치(set_pump)를 usv_sensors 스케치에 합쳤으므로 B1에서 도는 앱은
#     usv_sensors다. 여기서 app start를 하면 센서 앱을 내리고 다른 스케치를
#     플래시해서 수질·GPS가 죽는다. 앱은 usv-sensors.service가 띄운 것을 쓴다.
#
#  2. 이미지를 새로 빌드하지 않고 usv_sensors_image를 재사용한다.
#     usv_actuators/Dockerfile로 빌드하면 ~2GB가 필요한데 / 여유가 1.6GB뿐이다.
#
#  3. --restart 정책을 주지 않는다 (기본값 no).
#     정책을 주면 부팅 시 도커가 이 컨테이너를 먼저 띄우는데, 그 시점엔 와이파이가
#     아직 안 붙어서 DDS가 잘못된 인터페이스에 바인딩된다. 이어서 이 스크립트가
#     같은 컨테이너를 지우고 다시 만들므로 한 부팅에 두 번 시작되는 셈이다.
#     수명 관리는 usv-pump-b1.service가 단독으로 맡는다.
#
#  4. actuators.launch.py 대신 pump.launch.py를 띄운다.
#     전자는 thruster_driver_node까지 올리는데 B1에 추진기가 없다.

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${USV_ACTUATORS_PROJECT_DIR:-$SCRIPT_DIR}"
CONTAINER_NAME="usv_pump_container"
IMAGE_NAME="usv_sensors_image"

cd "$PROJECT_DIR"

if ! docker image inspect "$IMAGE_NAME" >/dev/null 2>&1; then
    echo "ERROR: $IMAGE_NAME 이미지가 없습니다. 먼저 usv_sensors/start_sensors.sh를 실행하세요."
    exit 1
fi

echo "[1] Waiting for Arduino Router..."
for i in $(seq 1 30); do
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

# DDS는 프로세스 시작 시점의 네트워크 인터페이스에 바인딩된다. 와이파이가 붙기 전에
# 컨테이너가 뜨면 GCS·추진기 보드를 못 찾는다. systemd의 network-online.target을
# 못 미더워서 여기서 한 번 더 확인한다.
echo "[2] Waiting for network..."
for i in $(seq 1 30); do
    if ip -4 addr show wlan0 2>/dev/null | grep -q "inet "; then
        echo "Network ready: $(ip -4 -br addr show wlan0 | awk '{print $3}')"
        break
    fi
    sleep 1
done

echo "[3] Removing old ROS container..."
docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true

echo "[4] Starting ROS 2 container (usv_actuators / pump only)..."
docker run -d \
    --name "$CONTAINER_NAME" \
    --network host \
    --privileged \
    -e ROS_DOMAIN_ID=0 \
    -v /dev:/dev \
    -v /var/run/arduino-router.sock:/var/run/arduino-router.sock \
    -v "$PROJECT_DIR:/ros2_ws/src/usv_actuators" \
    "$IMAGE_NAME" \
    bash -c '
        source /opt/ros/jazzy/setup.bash
        cd /ros2_ws
        colcon build --symlink-install --packages-select usv_actuators
        source /ros2_ws/install/setup.bash
        ros2 launch usv_actuators pump.launch.py
    '

echo "[5] actuator_driver_node started (pump only; thruster/LED 제외)."
