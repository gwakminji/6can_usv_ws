import time
from arduino.app_utils import App

def loop():
    """This function is called repeatedly by the App framework."""
    time.sleep(10)

App.run(user_loop=loop)
