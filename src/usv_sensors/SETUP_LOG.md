# usv_sensors (B1 보드) 실행 기록

`6can_usv_ws` 저장소를 클론한 뒤 `src/usv_sensors`를 이 보드(UNO Q, B1)에서
처음 실행하면서 겪은 과정과 조치 내역 정리.

## 0. 클론

```bash
git clone https://github.com/gwakminji/6can_usv_ws
cd 6can_usv_ws/src/usv_sensors
```

## 1. 최초 실행 시도 — `./start_sensors.sh`

Docker 이미지(`usv_sensors_image`) 빌드는 성공(약 10분, `cv_bridge` 의존성 때문에
apt 패키지가 많음). 이어서 아래 에러로 실패:

```
[1] Starting Arduino App (water_quality + GPS sketch)...
app path is not valid: stat /home/arduino/ArduinoApps/usv_sensors: no such file or directory
```

**원인**: `arduino-app-cli app start`는 App 이름이 아니라 **경로**를 받는데,
클론한 저장소가 App Lab이 앱을 찾는 `~/ArduinoApps/` 아래에 없었음.

**조치**: 심볼릭 링크 생성 (실제 파일은 클론한 저장소에만 존재, 양쪽 어디서 수정해도 동일):

```bash
ln -s /home/arduino/6can_usv_ws/src/usv_sensors /home/arduino/ArduinoApps/usv_sensors
```

## 2. 재실행 — `icon` 에러

```
icon "USV" is not a valid single emoji
```

**원인**: `app.yaml`의 `icon: "USV"`가 텍스트라서 App Lab이 거부.

**조치**: `app.yaml`의 `icon`을 `"🚤"`로 수정.

## 3. 재실행 — `python/main.py` 누락

```
main python file missing from app
```

**원인**: 저장소에 App Lab 필수 진입점인 `python/main.py`가 아예 없었음
(ROS 2 쪽 개발에 집중하느라 빠진 것으로 보임). MCU 스케치는
`get_water_quality`/`get_gps`를 `Bridge.provide`로 이미 노출하고 있음.

**조치**: 선행 프로젝트 `waterqualityros2/python/main.py`와 동일한 패턴으로
`python/main.py` 신규 작성 — `Bridge.call`로 두 값을 읽어 콘솔에 출력만 함
(실제 ROS 2 로직은 Docker 컨테이너가 같은 `arduino-router.sock`으로 직접 통신).

## 4. 재실행 — 스케치 컴파일 에러

```
sketch.ino:346:6: error: variable or field 'addAdcSample' declared void
sketch.ino:346:20: error: 'AdcAccumulator' was not declared in this scope
...
```

**원인**: Arduino 빌더가 함수 프로토타입을 소스 상단(include/define 블록 바로
뒤)에 자동 삽입하는데, `struct AdcAccumulator`가 그보다 한참 아래(346번째 줄
근처)에 정의돼 있어서 프로토타입 삽입 시점엔 타입이 안 보임.

**조치**: 구조체를 별도 헤더로 분리해서 include 블록 안에 넣음 —
`sketch/adc_accumulator.h` 신규 생성 후 `sketch.ino` 상단에 `#include`,
기존 인라인 struct 정의는 삭제.

## 5. 재실행 — 성공

```
✓ App "usv_sensors" started successfully
[5] usv_sensors nodes started (water_quality_node, gps_driver_node, camera_node).
```

확인된 사항:
- App Lab: `user:usv_sensors` → `running`
- `docker ps`: `usv_sensors_container` 정상 기동
- `ros2 topic list` (컨테이너 안):
  `/water_quality/*`, `/gps/*`, `/battery/status`,
  `/camera/surface,underwater/image_raw`(별도 `camera_streaming` 컨테이너),
  `/parameter_events`, `/rosout` 전부 정상 발행

## 6. 값 검증

- **temp_c / do_mg_l**: 실내 상온 기준 그럴듯한 값, 변화도 자연스러움 → 정상.
- **ph (~12.54, 거의 고정)**, **turbidity/clarity (~92%, 거의 고정)**: 강알칼리
  수준이라 비정상적으로 보였으나, 원인은 **pH/탁도 캘리브레이션 미실시** +
  프로브가 버퍼 용액이 아니라 실온 공기/물에 있었기 때문으로 확인.
  `sketch.ino`의 `PH7_VOLTAGE`/`PH4_VOLTAGE`/`PH_CALIBRATION_T`,
  `CLEAR_WATER_VOLTAGE`/`VERY_TURBID_VOLTAGE` 상수가 하드코딩값이라 실제
  버퍼 용액(pH 4/7)으로 캘리브레이션하면 정상 범위로 나올 것.
- **GPS (fix=false, satellites=0)**: 실내라 위성 신호 미수신 — 예상된 정상 동작.
- **camera**: USB 카메라 미연결 상태라 아직 검증 안 함(`camera_streaming` 컨테이너
  자체는 이전부터 떠 있음).
- **current_sensor_node**: `get_battery_status method not available` 경고 지속 —
  README 체크리스트에 이미 "하드웨어 미확정, sketch.ino 반영 필요"로 표시된
  기존 TODO 항목이라 이번 작업에서는 손대지 않음.

## 파일 위치 요약

| 항목 | 경로 |
|---|---|
| 클론 저장소 루트 | `/home/arduino/6can_usv_ws/` |
| usv_sensors 패키지 | `6can_usv_ws/src/usv_sensors/` |
| App Lab 심볼릭 링크 | `/home/arduino/ArduinoApps/usv_sensors` → 위 경로 |
| 수정: `app.yaml` | `icon` 필드 변경 |
| 신규: `python/main.py` | App Lab 진입점 |
| 수정: `sketch/sketch.ino` | `AdcAccumulator` struct 제거 |
| 신규: `sketch/adc_accumulator.h` | `AdcAccumulator` struct 이동 |
| Docker 이미지 | `usv_sensors_image` |
| Docker 컨테이너 | `usv_sensors_container` |
| App Lab 앱 ID | `user:usv_sensors` |

## 실행/확인 명령 모음

```bash
# 시작 (저장소 경로에서)
cd /home/arduino/6can_usv_ws/src/usv_sensors
./start_sensors.sh
./install_autostart.sh          # 선택: 부팅 자동 실행 등록 (아직 미실행)

# App 로그 / 상태 (심볼릭 링크 경로로)
arduino-app-cli app logs    /home/arduino/ArduinoApps/usv_sensors --follow
arduino-app-cli app stop    /home/arduino/ArduinoApps/usv_sensors
arduino-app-cli app restart /home/arduino/ArduinoApps/usv_sensors

# ROS 2 토픽 확인
docker exec usv_sensors_container bash -c \
  "source /opt/ros/jazzy/setup.bash && source /ros2_ws/install/setup.bash && ros2 topic list"

# 컨테이너 로그
docker logs -f usv_sensors_container
```
