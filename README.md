# 🚤 수질 연동 분수 펌프 · RGB LED 자동 제어

B2 보드(`usv_actuators`)가 B1의 수질 측정값을 직접 구독해서, 분수 펌프와 RGB LED를
**사람 개입 없이** 제어한다. 물이 나빠지면 펌프를 돌려 물을 순환시키고, LED 색으로
현재 수질 단계를 밖에서 바로 알아볼 수 있게 한다.

기존에는 GCS에서 사람이 버튼을 눌러야만 펌프·LED가 움직였다. 이제는 자동이 기본이고,
사람이 누르면 그때만 사람 쪽이 우선한다.

---

## 1. 동작 규칙

### 3단계 판정

`/water_quality/data`의 `clarity_pct`(0~100, 클수록 깨끗)를 세 단계로 나눈다.

| 단계 | 조건 | LED | 분수 펌프 |
|---|---|---|---|
| `GOOD` (좋음) | `clarity_pct >= 60` | 🟢 초록 | OFF |
| `NORMAL` (보통) | `40 <= clarity_pct < 60` | 🟡 노랑 | OFF |
| `BAD` (나쁨) | `clarity_pct < 40` | 🔴 빨강 | **ON** |

B1 스케치가 이미 계산해주는 `clarity_level`(5단계 문자열) 대신 `clarity_pct` 숫자를
쓴다. 문자열을 쓰면 임계값을 조정할 때마다 B1 담당자의 스케치를 고쳐 MCU에 다시
업로드해야 하지만, 숫자를 받아 이쪽에서 판정하면 launch 인자만 바꾸면 된다.

### 히스테리시스 — 펌프가 딸깍거리지 않게

경계에서 측정값이 `39.8 ↔ 40.2`로 미세하게 흔들리면 릴레이가 1초마다 on/off를
반복한다. 그래서 한 번 어떤 단계에 들어가면 경계를 `margin`(기본 3.0)만큼 확실히
넘어야 빠져나온다.

- `BAD`에서 나오려면 `clarity_pct >= 43`
- `GOOD`에서 떨어지려면 `clarity_pct < 57`

### 사람이 버튼을 누르면

GCS에서 수동 명령(`/actuator/pump_cmd`, `/actuator/led_cmd`)이 오면 그 값을 즉시
적용하고, `pump_manual_hold_s` / `led_manual_hold_s`(기본 60초) 동안 자동 판정을
억제한다. 시간이 지나면 자동이 다시 판단한다.

"단계가 바뀔 때만 자동이 개입"하는 방식은 쓰지 않았다. 물이 계속 나쁜 상태로
머무르면 단계 변화가 없어서, 사람이 끄고 잊어버린 펌프가 영영 안 켜지기 때문이다.

펌프와 LED의 억제 타이머는 서로 독립이다. LED 색만 바꿔놓고 펌프는 자동에 맡기는
조작이 가능하다.

### 수질 데이터가 끊기면

1초 주기 타이머가 마지막 수신 시각을 확인해서, `stale_timeout_s`(기본 5초) 이상
`/water_quality/data`가 끊기면 펌프를 끈다. B1이 죽거나 Wi-Fi가 끊겼는데 펌프가
켜진 채 방치되면 배터리만 축나기 때문이다.

단, 수동 억제 중에는 건드리지 않는다. 사람이 방금 켠 펌프를 두절 감지가 꺼버리면
안 된다.

---

## 2. 데이터 흐름

```mermaid
flowchart LR
  WQN["water_quality_node<br/>(B1)"]
  GCS["gui_main_node · joy_to_cmd_node<br/>(GCS)"]
  ACT["actuator_driver_node<br/>(B2)"]
  POL["water_policy.py<br/>판정 규칙"]
  MCU["sketch.ino · STM32<br/>릴레이 · LED 핀"]

  WQN -->|"/water_quality/data (JSON)"| ACT
  GCS -->|"/actuator/pump_cmd"| ACT
  GCS -->|"/actuator/led_cmd"| ACT
  GCS -.->|"/actuator/auto_mode (선택)"| ACT
  ACT <-->|classify / pump_for / color_for| POL
  ACT -->|"set_pump · set_actuator_led (RPC)"| MCU
```

자동 입력(`/water_quality/data`)과 수동 입력(`/actuator/*_cmd`)이 **서로 다른 토픽**
으로 도착하기 때문에, 어느 쪽이 보낸 명령인지 노드가 구분할 수 있다.

---

## 3. 인터페이스 — 다른 파트는 고칠 것이 없다

토픽 이름과 메시지 타입은 기존 계약 그대로다. **B1과 GCS는 아무것도 수정하지 않아도
된다.**

| 토픽 | 타입 | 이 노드의 역할 | 비고 |
|---|---|---|---|
| `/water_quality/data` | `std_msgs/String` (JSON) | 신규 구독 | B1은 발행하던 것을 그대로 발행 |
| `/actuator/pump_cmd` | `std_msgs/Bool` | 구독 (기존) | 수동 우선 |
| `/actuator/led_cmd` | `std_msgs/ColorRGBA` | 구독 (기존) | 수동 우선 |
| `/actuator/auto_mode` | `std_msgs/Bool` | 신규 구독 (선택) | 발행자 없으면 자동=켬 |

`/actuator/auto_mode`는 아직 아무도 발행하지 않는다. 나중에 GCS가 자동/수동 토글을
추가할 때 이 노드를 고치지 않고 바로 붙일 수 있도록 미리 구독해 둔 것이다.

MCU RPC(`set_pump`, `set_actuator_led`)는 **값이 실제로 바뀔 때만** 호출한다. 같은
값을 1초마다 다시 보내 Bridge를 낭비하지 않는다.

---

## 4. 파일 구성

```
src/usv_actuators/
├── usv_actuators/
│   ├── water_policy.py           # 판정 규칙 (ROS 무관 · 순수 함수)
│   └── actuator_driver_node.py   # 구독 · 억제 타이머 · MCU 전달
├── launch/actuators.launch.py    # 임계값을 launch 인자로 노출
└── DESIGN_pump_led.md            # 설계 의도 상세
```

`water_policy.py`에 ROS 의존성을 넣지 않은 이유는, 보드 없이 노트북에서도 판정
규칙을 검증할 수 있게 하기 위해서다.

```python
>>> from usv_actuators import water_policy
>>> water_policy.classify(38.0)
'BAD'
>>> water_policy.classify(41.0, previous='BAD')   # 히스테리시스 — 아직 못 빠져나옴
'BAD'
>>> water_policy.classify(44.0, previous='BAD')
'NORMAL'
```

---

## 5. 실행

```bash
cd usv_ws/src/usv_actuators
./start_actuators.sh
```

임계값은 코드를 고치지 말고 launch 인자로 넘긴다. 실제 수조에서 `clarity_pct`가
어느 범위로 나오는지 보고 조정하면 된다.

```bash
ros2 launch usv_actuators actuators.launch.py bad_below:=35.0 good_above:=55.0
```

| 인자 | 기본값 | 의미 |
|---|---|---|
| `bad_below` | `40.0` | 이 값 미만이면 나쁨 (펌프 ON, LED 빨강) |
| `good_above` | `60.0` | 이 값 이상이면 좋음 (LED 초록) |
| `margin` | `3.0` | 히스테리시스 폭 |
| `pump_manual_hold_s` | `60.0` | 수동 펌프 조작이 자동보다 우선하는 시간(초) |
| `led_manual_hold_s` | `60.0` | 수동 LED 조작이 자동보다 우선하는 시간(초) |
| `stale_timeout_s` | `5.0` | 수질 데이터가 이만큼 끊기면 펌프 정지 |
| `max_pwm` | `255` | 추진기 PWM 최대값 (기존 인자) |

### 하드웨어 없이 확인하기

```bash
# 나쁨 → 펌프 ON, LED 빨강
ros2 topic pub --once /water_quality/data std_msgs/msg/String \
  '{data: "{\"clarity_pct\": 25.0}"}'

# 좋음 → 펌프 OFF, LED 초록
ros2 topic pub --once /water_quality/data std_msgs/msg/String \
  '{data: "{\"clarity_pct\": 80.0}"}'

# 수동 우선 확인 — 이후 60초간 자동 판정이 억제된다
ros2 topic pub --once /actuator/pump_cmd std_msgs/msg/Bool '{data: true}'
```

노드 로그에 `수질 25.0% → BAD`, `수동 펌프 ON (60초간 자동 억제)` 같은 줄이 뜬다.

---

## 6. 아직 안 된 것

- **B2 Arduino 스케치 미작성.** `set_pump`, `set_actuator_led` RPC 핸들러가 MCU 쪽에
  없어서, 컨테이너가 떠도 실제 전기는 흐르지 않는다. ROS 레벨 판정 로직까지는 위
  `ros2 topic pub`으로 전부 검증 가능하다.
- **RPC 이름은 임시.** 실제 릴레이/LED 드라이버 배선을 확정하면서 이름을 맞춰야 한다.
  LED 드라이버가 공통 애노드면 값 반전이 필요할 수 있다.
- **임계값 40 / 60은 가정치.** 실제 수조에서 `clarity_pct`가 어느 범위로 나오는지
  측정한 뒤 launch 인자로 조정할 것.

설계 의도와 대안 검토 과정은 [`src/usv_actuators/DESIGN_pump_led.md`](src/usv_actuators/DESIGN_pump_led.md)에 정리되어 있다.

---

## 7. 논의 필요 ⚠️ — 조이스틱 펌프 조작과 자동 제어가 충돌한다

**이 브랜치를 그대로 머지하면 자동 제어가 동작하지 않는다.** 코드 문제라기보다
브랜치를 딴 뒤 GCS 쪽 설계가 바뀌면서 생긴 전제 불일치라, 어떻게 맞출지 팀 논의가
필요하다.

### 무엇이 어긋났나

`actuator_driver_node`는 이렇게 전제하고 있다.

> `/actuator/pump_cmd` 메시지가 도착 = 사람이 펌프 버튼을 눌렀다
> → 60초간 자동 판정을 억제한다

브랜치를 만들 당시에는 맞는 전제였다. 그때는 GUI 화면의 펌프 버튼만 이 토픽을
발행했고, 사람이 클릭할 때만 메시지가 갔다.

그 뒤 업스트림에 `usv_gcs: move pump control to joystick, GUI shows status only`가
들어오면서 발행 주체가 조이스틱으로 바뀌었다.

```python
# usv_gcs/joy_to_cmd_node.py — joy_callback()
if len(msg.buttons) > self.pump_button:      # "버튼이 눌렸으면"이 아니라 "버튼이 있으면"
    pump_msg.data = bool(msg.buttons[self.pump_button])
    self.pump_pub.publish(pump_msg)          # 안 눌러도 false를 계속 발행
```

조건이 "버튼이 눌렸으면"이 아니라 "버튼이 존재하면"이다. 즉 버튼을 누르지 않아도
`false`가 계속 발행된다. 배를 조종하려고 스틱을 움직이는 동안 `/joy`가 들어올
때마다 `/actuator/pump_cmd: false`가 같이 나간다.

### 증상

`on_pump_cmd`가 메시지마다 `pump_hold_until = now + 60s`로 억제 타이머를 갱신하므로,
타이머가 만료되지 않는다.

| 시각 | 실제 상황 | 노드의 해석 | 억제 타이머 |
|---|---|---|---|
| 0.00초 | 스틱 밀어서 전진 | 사람이 펌프 조작함 | 60초로 리셋 |
| 0.05초 | 계속 전진 중 | 사람이 펌프 조작함 | 60초로 리셋 |
| … | … | … | 영원히 만료 안 됨 |

자동 판정 코드까지 실행이 도달하지 못하므로, **조종하는 내내 수질이 나빠져도 펌프가
켜지지 않는다.** 조종을 멈추고 60초를 기다려야 자동이 돌아온다.

### 제안 — 값이 바뀔 때만 수동으로 친다 (권장)

`false, false, false…`가 반복되는 것은 조작이 아니라 상태 보고다. 값이 실제로 바뀐
순간만 사람의 조작으로 해석하면 된다. `actuator_driver_node`만 고치면 되고 GCS와 B1은
건드리지 않는다.

```python
# __init__
self.last_manual_pump = None

def on_pump_cmd(self, msg: Bool):
    want = bool(msg.data)
    if want == self.last_manual_pump:   # 같은 값 반복 = 조작 아님
        return
    self.last_manual_pump = want

    hold = self.get_parameter('pump_manual_hold_s').value
    self.pump_hold_until = self.now() + hold
    self.send_pump(want)
```

### 검토한 대안

| 대안 | 장점 | 단점 |
|---|---|---|
| **A. 값 변화 감지** (위 제안) | B2만 수정, 다른 파트 영향 없음 | 조이스틱 버튼을 계속 누르고 있는 조작은 한 번으로 친다 |
| B. `/actuator/auto_mode` 토글로 명시 전환 | 의도가 가장 분명함 | GCS에 토글 UI 추가 필요, 자동↔수동 전환을 사람이 매번 해야 함 |
| C. `joy_to_cmd_node`가 버튼이 눌렸을 때만 발행 | 원인 지점을 고침 | GCS 담당 파트 수정 필요, 버튼을 뗀 시점을 B2가 알 수 없음 |

### 결정해야 할 것

- [ ] A / B / C 중 어느 방향으로 갈지
- [ ] 조이스틱 펌프 버튼을 **누르고 있는 동안만 ON**으로 볼지, **누를 때마다 토글**로 볼지
      (전자라면 대안 A의 단점이 실제 문제가 되므로 C를 같이 검토해야 한다)
- [ ] `pump_manual_hold_s` 기본 60초가 실제 운용에 맞는지
