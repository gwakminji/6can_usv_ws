# ⚠️ 논의 필요 — 조이스틱 펌프 조작과 자동 제어가 충돌한다

> 기능 설명은 [`PUMP_LED.md`](PUMP_LED.md), 설계 의도는 [`DESIGN_pump_led.md`](DESIGN_pump_led.md) 참고.

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
