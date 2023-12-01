#!/usr/bin/env python3          
                                
import signal                   
import sys
import time
import RPi.GPIO as GPIO
import numpy as np
from datetime import datetime  # for time/date timestamp on output
# --------------------------------------------

BUTTON_GPIO = 20 # connector pin 38
LED_GPIO = 21    # BR corner of connector, pin 40

# Control-C interrupt handler
def signal_handler(sig, frame):
    GPIO.cleanup()
    sys.exit(0)

# GPIO signal input handler. 'channel' param is GPIO number, eg 20
def button_callback(channel):
    global outState
    global tDelta
    global tOld
    if channel == BUTTON_GPIO:
        outState = not outState
        tNow = time.time_ns()
        tDelta = tNow - tOld
        tOld = tNow

# =====================================================================
#if __name__ == '__main__':
print("GPIO python interrupt test start v0.1 01-Dec-2023 JPB")

GPIO.setmode(GPIO.BCM)    
GPIO.setup(BUTTON_GPIO, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(LED_GPIO, GPIO.OUT)   
GPIO.add_event_detect(BUTTON_GPIO, GPIO.RISING, 
            callback=button_callback, bouncetime=20)
signal.signal(signal.SIGINT, signal_handler)

while True:
    gChannel = 0
    outState = False
    tOld = time.time_ns()  # time since epoch, in nanoseconds
    tDelta = 0
    warm = False    # true when code is synced to input pulse
    count = 0    # how many pulses received
    dIdx = 0     # index into data array
    maxSamples = 20  # how many data points to record

    dat = np.zeros(maxSamples, dtype=float, order='C')

    oldState = True
    dStart = datetime.now()   # date/time at start

    while dIdx < maxSamples:
        if outState:
            GPIO.output(LED_GPIO, GPIO.HIGH)
        else:
            GPIO.output(LED_GPIO, GPIO.LOW)

        if (oldState != outState):
            tSec = tDelta / 1.0E9
            tDif = int((1.0 - tSec)*1.0E6) # microseconds of jitter
            # print("%d, %d, %d, %5.6f, %d" % (count, dIdx, outState, tSec, tDif))
            if warm:
                dat[dIdx] = tDif
                dIdx += 1
            else:
                if (count == 2):
                    warm = True

            oldState = outState
            count += 1

        time.sleep(0.02)

    # ----------------------------------------------------
    now = datetime.now()
    print("%s : %s  avg = %5.3f st.dev = %5.3f  min=%5.3f max=%5.3f" % 
        (
         dStart.strftime("%Y-%m-%d %H:%M:%S"),
         now.strftime("%Y-%m-%d %H:%M:%S"),
         np.mean(dat), np.std(dat), np.min(dat), np.max(dat)) )

    # never reached
    # signal.pause()
    # ----------------------------------------------------


GPIO.cleanup()
