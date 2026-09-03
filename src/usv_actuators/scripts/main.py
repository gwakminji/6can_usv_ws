from arduino.app_utils import App, Bridge
import os, time

CMD = "/app/python/cmd.txt"
NEUTRAL = 1487
DEADBAND = 35
STALE_SEC = 1.0

STEP_US = 20          # 한 주기(0.05초)당 최대 증가폭. 작을수록 느리게 출발
REVERSE_PAUSE = 0.3   # 방향 전환 시 중립 대기 시간(초)

last_sent = None
was_stale = False

cur_left = NEUTRAL
cur_right = NEUTRAL
hold_until = 0.0

def shape(v):
    v = max(1000, min(2000, int(v)))
    if abs(v - NEUTRAL) <= DEADBAND:
        return NEUTRAL
    return v

def sign(v):
    if v > NEUTRAL: return 1
    if v < NEUTRAL: return -1
    return 0

def ramp(cur, target):
    # 중립 방향(감속·정지)은 즉시 반영
    if abs(target - NEUTRAL) <= abs(cur - NEUTRAL):
        return target
    # 가속 방향만 STEP_US 만큼 제한
    if target > cur:
        return min(target, cur + STEP_US)
    else:
        return max(target, cur - STEP_US)

def loop():
    global last_sent, was_stale, cur_left, cur_right, hold_until

    t_left = t_right = NEUTRAL
    fresh = False

    try:
        if os.path.exists(CMD):
            age = time.time() - os.path.getmtime(CMD)
            if age <= STALE_SEC:
                parts = open(CMD).read().strip().split(",")
                if len(parts) == 2:
                    t_left = shape(parts[0])
                    t_right = shape(parts[1])
                    fresh = True
    except Exception as e:
        print(">>> 파싱 오류:", e, flush=True)

    if not fresh and not was_stale:
        print(">>> 명령 없음 → 중립 유지", flush=True)
    was_stale = not fresh

    now = time.time()

    # 방향 전환 감지 → 중립 경유
    if sign(t_left) * sign(cur_left) < 0 or sign(t_right) * sign(cur_right) < 0:
        if hold_until < now:
            print(">>> 방향 전환 → 중립 경유", flush=True)
            hold_until = now + REVERSE_PAUSE
        cur_left = cur_right = NEUTRAL
    elif hold_until > now:
        cur_left = cur_right = NEUTRAL
    else:
        cur_left = ramp(cur_left, t_left)
        cur_right = ramp(cur_right, t_right)

    cur = (cur_left, cur_right)
    if cur != last_sent:
        print(">>> 전송: %d, %d  (목표 %d, %d)" % (cur_left, cur_right, t_left, t_right), flush=True)
        last_sent = cur

    try:
        Bridge.call('set_thruster_pwm', cur_left, cur_right)
    except Exception as e:
        print(">>> RPC 실패:", e, flush=True)

    time.sleep(0.05)

App.run(user_loop=loop)

