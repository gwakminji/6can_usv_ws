"""App Lab entry point for the usv_sensors MCU sketch.

Only starts the sketch (water_quality + GPS) and keeps the Router Bridge
alive; the actual ROS 2 nodes run in the sibling Docker container and talk
to the MCU over the same arduino-router.sock (see start_sensors.sh).
"""

import json
import time

from arduino.app_utils import App, Bridge


def decode_reading(value):
    if isinstance(value, bytes):
        value = value.decode('utf-8')
    if isinstance(value, str):
        return json.loads(value)
    return value


def loop():
    try:
        water = decode_reading(Bridge.call('get_water_quality'))
        gps = decode_reading(Bridge.call('get_gps'))
        print('[WATER]', json.dumps(water, ensure_ascii=False), flush=True)
        print('[GPS]  ', json.dumps(gps, ensure_ascii=False), flush=True)
    except Exception as error:
        print(f'[ERROR] {error}', flush=True)
    time.sleep(1)


App.run(user_loop=loop)
