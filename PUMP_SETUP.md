# 분수 펌프 보드 실행 가이드

펌프만 담당하는 B2 보드(Arduino UNO Q)를 처음부터 돌리는 방법입니다.
추진기는 별도 보드를 쓰므로 이 문서에서 다루지 않습니다.

---

## 1. 한 줄 요약

```bash
~/ArduinoApps/6can_usv_ws/start_pump.sh
```

이 한 줄이 스케치 업로드부터 ROS 노드 실행까지 전부 처리합니다.
**App Lab을 열 필요가 없습니다.**

---

## 2. 사전 준비

### 2-1. 하드웨어 배선

릴레이 모듈: **NEROMART RELAY-M1(CH1)-5V** (Active LOW, 옵토커플러 절연)

```
UNO Q  5V   ──►  릴레이 VCC
UNO Q  GND  ──►  릴레이 GND
UNO Q  D7   ──►  릴레이 IN1

릴레이 출력 터미널 (NC / COM / NO)
  펌프 전원(+) ──►  COM
  NO           ──►  펌프 (+)
  펌프 전원(−) ─────  펌프 (−)
```

**반드시 지킬 것**

- **`NO`를 쓰세요.** 평상시 끊겨 있어서 보드가 꺼져도 펌프가 돌지 않습니다.
  `NC`는 반대로 평상시 돕니다.
- **펌프 전원을 보드 `5V` 핀에서 뽑지 마세요.** 릴레이 코일(약 80mA)까지 보드가
  먹여살리면 부팅 중 전압이 처져 보드가 계속 리셋됩니다. 별도 전원을 쓰세요.
- **수중 펌프는 물 없이 돌리면 파손됩니다.** 배선 확인 단계에서는 펌프 전원선을
  빼두고 릴레이 딸깍 소리만 확인하세요.
- UNO Q는 3.3V 로직인데 이 릴레이는 5V 모듈입니다. 그래도 정상 동작합니다 —
  모듈 입력단이 R1(1kΩ)+옵토LED+상태LED 직렬이라 도통 문턱이 약 3.2V이고,
  IN에 3.3V가 걸리면 5−3.3=1.7V만 남아 확실히 OFF됩니다. 실측으로 확인했습니다.

`D7`은 PWM 핀이 아닙니다. 릴레이는 on/off만 하므로 PWM이 필요 없고,
추진기가 쓰는 D9/D10과도 충돌하지 않습니다.

### 2-2. 네트워크

GCS·B1과 **같은 Wi-Fi**에 붙어야 하고, **`ROS_DOMAIN_ID`가 같아야** 합니다(현재 0).

```bash
nmcli -t -f NAME,DEVICE c show --active | grep wlan
ip -4 -o addr show wlan0 | awk '{print $4}'
```

**멀티캐스트가 막힌 환경**이라 자동 탐색만으로는 서로를 못 찾습니다.
그래서 양쪽에 상대 IP를 알려줘야 합니다.

- 이 보드 → GCS: `start_pump.sh`가 `ROS_STATIC_PEERS`로 처리 (기본값 `192.168.0.5`)
- GCS → 이 보드: **GCS 쪽에서도 이 보드 IP를 넣어줘야 합니다**

```bash
# GCS에서
export ROS_STATIC_PEERS=192.168.0.10   # 이 보드 IP
unset ROS_LOCALHOST_ONLY               # 켜져 있으면 자기 기계 밖과 통신 안 됨
```

IP가 바뀌면 이 값도 바꿔야 합니다. 공유기에서 **고정 IP를 할당**해두면 편합니다.

### 2-3. 레포 위치

App Lab은 `~/ArduinoApps/` 아래를 훑어서 앱을 찾습니다.
**반드시 그 아래에 클론하세요.**

```bash
cd ~/ArduinoApps
git clone <레포 주소>
```

---

## 3. 실행

```bash
~/ArduinoApps/6can_usv_ws/start_pump.sh
```

하는 일:

| 단계 | 내용 |
|---|---|
| [1] | 스케치를 MCU에 업로드하고 App Lab 앱 실행 |
| [2] | Arduino Router 소켓 준비 대기 |
| [3] | 기존 ROS 컨테이너 정리 |
| [4] | ROS 노드 컨테이너 실행 (`pump.launch.py`) |

첫 실행은 도커 이미지 빌드 때문에 10~20분 걸립니다(인터넷 필요).
이후에는 1분 이내입니다.

### 다른 IP를 쓰려면

```bash
USV_ROS_PEERS="192.168.0.5;192.168.0.4" ./start_pump.sh
```

### 임계값을 바꾸려면

코드를 고치지 말고 launch 인자로 넘기세요.

```bash
ros2 launch usv_actuators pump.launch.py bad_below:=35.0 good_above:=55.0
```

---

## 4. 동작 확인

### 4-1. 노드가 떴는지

```bash
docker logs usv_pump_container | tail -5
```

`Actuator driver node started` 가 보이면 정상입니다.

### 4-2. MCU가 명령을 받을 준비가 됐는지 (펌프를 켜지 않음)

```bash
docker exec usv_pump_container bash -c \
  'source /opt/ros/jazzy/setup.bash && source /ros2_ws/install/setup.bash && \
   python3 -c "
from usv_actuators.bridge import Bridge
try:
    Bridge.call(\"set_pump\", False, timeout=6)
    print(\"OK  set_pump 등록됨\")
except Exception as e:
    print(f\"FAIL {e}\")
"'
```

- `OK` → 정상
- `method set_pump not available` → 스케치가 MCU에 없음. `start_pump.sh` 재실행
- `timed out` → MCU가 멈춤. `start_pump.sh` 재실행

**하드웨어를 의심하기 전에 항상 이것부터 확인하세요.**
`Bridge.notify`는 실패해도 예외를 던지지 않아, 겉으로는 "명령은 갔는데
하드웨어가 이상한" 것처럼 보입니다.

### 4-3. GCS·B1과 붙었는지

```bash
docker exec usv_pump_container bash -c \
  'source /opt/ros/jazzy/setup.bash && source /ros2_ws/install/setup.bash && ros2 node list'
```

`/gui_main_node`, `/joy_to_cmd_node`, `/water_quality_node` 가 보이면 정상입니다.

### 4-4. 실제 수질을 받고 판정하는지

```bash
docker logs usv_pump_container | grep -a "수질"
```

`수질 84.6% → GOOD` 같은 줄이 찍히면 정상입니다.

### 4-5. GUI·센서 없이 단독으로 검증하려면

```bash
~/ArduinoApps/6can_usv_ws/src/usv_actuators/test/manual_test.sh
```

키보드로 조이스틱 버튼과 수질값을 흉내내는 대화형 도구입니다.
자세한 사용법은 스크립트 실행 후 `h`를 누르세요.

---

## 5. 제어 규칙

### 수질 3단계

| 단계 | `clarity_pct` | LED | 펌프 |
|---|---|---|---|
| 좋음 | ≥ 60 | 초록 | OFF |
| 보통 | 40 ~ 60 | 노랑 | OFF |
| 나쁨 | < 40 | 빨강 | **ON** |

경계에서 값이 흔들릴 때 릴레이가 딸깍거리지 않도록 **히스테리시스 3%p**가
걸려 있습니다. 한 번 `나쁨`에 들어가면 43% 이상 회복돼야 빠져나옵니다.

### 조이스틱

| 버튼 | 동작 |
|---|---|
| A (0번) | 누르는 동안 펌프 ON, 떼면 OFF |
| B (1번) | 자동/수동 토글 |

**수동 조작은 60초간 자동보다 우선합니다.** 60초가 지나면 자동이 다시 판단합니다.
"단계가 바뀔 때만 개입"으로 하면 물이 계속 나쁠 때 사람이 끄고 잊은 펌프가
영영 안 켜지기 때문입니다.

완전히 자동을 끄려면 B버튼으로 수동 모드로 전환하세요.

### 안전장치

수질 데이터가 **5초 이상 끊기면 펌프를 끕니다.** B1이 죽거나 Wi-Fi가 끊겼을 때
펌프가 켜진 채 방치되어 배터리를 축내는 것을 막습니다.

---

## 6. 자주 막히는 지점

### "명령을 보냈는데 아무 반응이 없다"

**MCU의 RPC 핸들러 등록이 사라진 것**입니다. Arduino Router가 재시작되거나
App Lab 앱이 멈추면 발생합니다. 4-2로 확인하고 `start_pump.sh`를 다시 실행하세요.

### "App Lab에서 Run을 눌렀는데 펌프가 안 된다"

App Lab의 Run은 **스케치와 `python/main.py`만** 실행합니다.
`start_pump.sh`도, 도커도 실행하지 않습니다. 앱 컨테이너에는 도커 CLI도
소켓도 없어서 애초에 불가능합니다.

**실행은 터미널에서 `start_pump.sh`로 하세요.** App Lab은 상태 확인용입니다.

### "스케치 빌드가 `Stat /Data/Local/Tmp` 오류로 실패한다"

`adb shell`은 `TMPDIR`을 안드로이드 경로(`/data/local/tmp`)로 설정합니다.

```bash
TMPDIR=/tmp arduino-app-cli app restart <앱ID>
```

`start_pump.sh`는 이미 처리하고 있습니다. 수동으로 `arduino-app-cli`를 쓸 때만
주의하세요.

### "App Lab에 앱이 안 보인다"

`arduino-app-cli app list --show-broken-apps`로 이유를 확인하세요. 조건 세 가지를
모두 만족해야 앱으로 인식됩니다.

- `app.yaml`의 `icon`이 **이모지 한 개**여야 함 (문자열은 안 됨)
- `python/main.py`가 있어야 함
- `sketch/sketch.ino`와 `sketch/sketch.yaml`이 **둘 다** 있어야 함

### "App Lab에 앱은 보이는데 파일이 비어 있다"

`~/ArduinoApps/` 아래에 **심볼릭 링크로 등록하면** App Lab 파일 브라우저가 링크를
따라가지 못합니다. 링크를 지우세요. App Lab은 하위 폴더를 재귀적으로 찾으므로
레포를 `~/ArduinoApps/` 밑에 클론했다면 링크가 필요 없습니다.

### "보드가 계속 리셋된다 / adb가 offline이 된다"

전원 부족입니다. **릴레이·LED 전원을 보드 `5V` 핀에서 뽑지 마세요.**
보드에는 5V 3A를 공급하고, 부하는 별도 전원을 쓰되 **GND만 공통으로** 묶으세요.

확인 방법:

```bash
cut -d. -f1 /proc/uptime    # 30초 뒤 다시 실행해서 30 이상 늘면 정상
```

### "`sudo poweroff` 후에 보드가 안 깨어난다"

소프트 오프 상태에서 잘 안 깨어납니다. 전원을 **30초 이상 완전히 차단**한 뒤
다시 연결하세요. 종료할 때는 `poweroff` 대신 `sudo sync`만 하고 뽑는 편이
실용적입니다.

### "GCS와 ROS 통신이 안 된다"

순서대로 확인하세요.

1. 같은 네트워크인가 (`ping`)
2. `ROS_DOMAIN_ID`가 양쪽 다 0인가
3. **GCS에 `ROS_LOCALHOST_ONLY`가 켜져 있지 않은가** ← 자주 걸림
4. 양쪽에 `ROS_STATIC_PEERS`로 상대 IP를 넣었는가

3번이 켜져 있으면 GCS는 **자기 기계 안에서만** 통신합니다. 밖으로 아무것도
안 나가고 밖에서 오는 것도 안 받습니다.

### "컨테이너를 따로 띄웠는데 ROS 메시지가 안 온다"

컨테이너가 다르면 `/dev/shm`이 분리되어 FastDDS 공유메모리 전송이 실패하고,
**에러 없이 메시지가 사라집니다.** 토픽 목록에는 멀쩡히 보여서 더 헷갈립니다.

같은 컨테이너 안에서 실행하거나(`docker exec`), 양쪽에 `--ipc=host`를 주세요.

---

## 7. 추진기를 되살리려면

`sketch/sketch.ino`에 추진기 코드가 **주석으로 남아 있습니다.**

공식 `Servo` 라이브러리가 UNO Q의 zephyr 아키텍처를 지원하지 않아 컴파일이
실패해서 비활성화했습니다.

```
error: "This library only supports boards with an AVR, SAM, SAMD,
        NRF52, STM32F4, Renesas or XMC processor."
```

ESC는 50Hz에 1000~2000µs 펄스가 필요한데 UNO Q의 `analogWrite`는 500Hz 고정이라
단순 대체가 안 됩니다. zephyr용 PWM API나 다른 라이브러리를 찾아야 합니다.

해결한 뒤 주석을 풀고, `pump.launch.py` 대신 `actuators.launch.py`를 쓰면 됩니다.
