# B2 추진기 원격 설정 명령어

B2 추진기 보드에 원격 접속한 뒤 `thruster_driver_node.py`의 출력 변화량과 PWM 램프를
조정하고, 노드를 재시작·점검하는 절차다. 펌프·LED는 B1의 역할이므로 이 문서는
추진기 설정만 다룬다.

> 주의: 수상정이 물 위에 있거나 사람이 프로펠러 근처에 있을 때에는 값을 바꾸거나
> 노드를 시작하지 않는다. 변경 전에는 현재 값을 반드시 기록하고, 한 번에 하나의
> 값만 작은 폭으로 조정한다.

## 1. 컨테이너 접속과 현재 값 확인

원격 접속한 B2 호스트에서 컨테이너에 들어간다.

```bash
docker exec -it usv_actuators_container bash
source /opt/ros/jazzy/setup.bash
source /ros2_ws/install/setup.bash
cd /ros2_ws/src/usv_actuators/usv_actuators

grep -E "^(STEP_US|MAX_DELTA) =" thruster_driver_node.py
```

현재 저장소 기본값은 `STEP_US = 150`, `MAX_DELTA = 50`이다.

| 설정 | 의미 | 낮추면 | 높이면 |
|---|---|---|---|
| `STEP_US` | 한 제어 주기에서 PWM이 바뀌는 폭(µs) | 가감속이 더 부드럽고 느려짐 | 반응이 빠르고 급해짐 |
| `MAX_DELTA` | 조이스틱 명령에서 허용하는 중립점 기준 최대 PWM 변화량 | 최고 추력이 줄어듦 | 최고 추력이 커짐 |

## 2. 값 변경

아래에서 `새값`만 원하는 숫자로 바꾼다. 현재 값이 무엇이든 해당 상수 행만 교체하므로,
`STEP_US = 20` 또는 `STEP_US = 100`처럼 특정 이전 값에 의존하지 않는다.

```bash
# 예: 램프 폭을 50으로 변경 (더 부드러운 반응)
sed -i 's/^STEP_US = .*/STEP_US = 50/' thruster_driver_node.py
grep "STEP_US" thruster_driver_node.py

# 예: 최대 변화량을 100으로 변경 (출력 범위 확대)
sed -i 's/^MAX_DELTA = .*/MAX_DELTA = 100/' thruster_driver_node.py
grep "MAX_DELTA" thruster_driver_node.py
```

변경 뒤 `exit`로 호스트로 나온다. `start_actuators.sh`는 컨테이너 시작 시
`colcon build --symlink-install`을 수행하므로, 아래 서비스 재시작으로 변경 내용을 적용한다.

## 3. 표준 서비스 재시작

이 저장소의 표준 systemd 유닛은 `usv-actuators.service`다.

```bash
sudo systemctl restart usv-actuators
sudo systemctl status usv-actuators --no-pager
```

현장 장비에 `usv-actuators-app`과 `usv-ros`가 별도로 등록돼 있다면, 존재 여부를 먼저
확인한 후 해당 장비에서만 다음 순서로 사용한다.

```bash
systemctl list-unit-files | grep -E 'usv-(actuators-app|ros)'
sudo systemctl stop usv-ros
sudo systemctl start usv-actuators-app
sudo systemctl start usv-ros
```

## 4. 수동 실행·로그 확인

서비스를 쓰지 않고 컨테이너 안에서 직접 점검할 때는 다음을 사용한다.

```bash
# 실행 중인 추진기 노드 PID 확인
ps aux | grep '[t]hruster_driver_node'

# 일반 종료가 되지 않을 때만 PID를 강제 종료
kill <PID>
kill -9 <PID>

# 추진기 노드 시작
ros2 launch usv_actuators actuators.launch.py
```

PWM RPC 전송 로그만 보려면 다음처럼 실행한다. 이 터미널은 로그 확인용이므로,
이미 서비스가 노드를 실행 중이면 먼저 서비스를 중지해 중복 실행을 피한다.

```bash
ros2 launch usv_actuators actuators.launch.py 2>&1 | grep -E 'SEND|tL|tR'
```

수동 점검을 끝낸 뒤에는 `Ctrl+C`로 종료하고 표준 서비스로 다시 시작한다.

```bash
pkill -f thruster_driver_node
sudo systemctl start usv-actuators
```
