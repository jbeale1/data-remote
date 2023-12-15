#!/usr/bin/python

# Acquire data from ADC using Pyadi-iio
# save data to file on disk
# J.Beale 12/15/2023

import sys         # command-line arguments, if any
import os          # test if directory is writable
import pathlib     # find current working directory
# import datetime    # current date & time
import adi         # Pyadi-iio interface to AD7124 ADC
import numpy as np # array manipulations
from struct import unpack  # extract words from packed binary buffer
import math        # for constant 'e'
import queue         # transfer ADC data between threads
import time          # for time.sleep()
import RPi.GPIO as GPIO   # GPIO input
from datetime import datetime  # for time/date timestamp on output

import signal       # handle control-C

# ----------------------------------------------------
# Configure Program Settings

version = "ADC Record v0.35  (15-Dec-2023)"   # this particular code version number


aqTime = 0.20       # duration of 1 dataset, in seconds
rate = 1000         # readings per second
R = 1               # decimation ratio: points averaged together before saving
totalPoints = 0     # total points recorded so far

# --------------------------------------------

IN1_GPIO = 20    # Signal1 on RPi connector pin 38
IN2_GPIO = 24    # Signal2 on RPi connector pin 18
LED_GPIO = 21    # BR corner of RPi connector, pin 40

# Control-C interrupt handler - program exits from here
def signal_handler(sig, frame):
    GPIO.cleanup()
    sys.exit(0)

# GPIO signal input handler. 'channel' param is GPIO number, eg 20
def button_callback(channel):
    global outState1, outState2
    global outLevel1, outLevel2
    global tDelta1, tDelta2
    global tOld1, tOld2

    tNow = time.time_ns()
    if channel == IN1_GPIO:
        outState1 = True                        # flag indicating change; set low in main loop
        outLevel1 = GPIO.input(IN1_GPIO)        # record current level of this GPIO pin
        tDelta1 = (tNow - tOld1) / 1.0E6 # convert ns to msec
        tOld1 = tNow
    if channel == IN2_GPIO:
        outState2 = True                        # will be set low in main loop        
        outLevel2 = GPIO.input(IN2_GPIO)        # will be set low in main loop        
        tDelta2 = (tNow - tOld2) / 1.0E6 # convert ns to msec
        tOld2 = tNow


# ----------------------------------------------------    
# set up ADC chip through Pyadi-iio system

def initADC(rate, samples, adc1_ip):

  try:
    adc1 = adi.ad7124(uri=adc1_ip)
  except Exception as e:
    print("Attempt to open '%s' had error: " % adc1_ip,end="")
    print(e)
    adc1 = None 
    
  if (adc1 is not None):  
      #phy = adc1.ctx.find_device("ad7124-8")
      ad_channel = 0
      sc = adc1.scale_available
      adc1.channel[ad_channel].scale = sc[-1]  # get highest range
      scale = adc1.channel[ad_channel].scale
      adc1.sample_rate = rate  # sets sample rate for all channels
      adc1.rx_buffer_size = samples
      adc1.rx_enabled_channels = [ad_channel]
      adc1._ctx.set_timeout(1000000)  # in what units is this?
  
  return adc1
  
def signal_handler(sig, frame):
    now = datetime.now()
    timeString = now.strftime('%Y-%m-%d %H:%M:%S')
    print('\nProgram stopped at %s' % timeString)
    fout.write('# Program stopped at %s' % timeString)
    print("Total data points: %d" % totalPoints)
    fout.close()    
    print("Data filename: %s" % datfile)
    sys.exit(0)


# ----------------------------------------------------    
Vref = 2.500 # voltage of ADC reference

avgMean = 0.004136345  # long-term filtered mean
mLPF = 0.01       # low-pass filter constant

def calcVolt(rawADC):  
    V = Vref * rawADC / (2**24)       # ADC as fraction of full-scale
    return V
    
# ----------------------------------------------------    


def runADC():
        global totalPoints     # how many points we've seen
        global outState1, outState2        # flag indicating unhandled GPIO input edge
        global outLevel1, outLevel2
        
        adc1 = initADC(rate, samples, adc1_ip)  # initialize ADC with configuration
        if (adc1 is None):
            print("Error: unable to connect to ADC %s" % adc1_ip)
            close()
            sys.exit()                       # leave entire program
        
        fout.write("mV\n")     # column header, to read as CSV            
        fout.flush()
        
        packets = 0
        int1High = False

        dispLines = 10  # how many packets per line to display on terminal while running
        while ( True ):
          try:
            data_raw = adc1.rx()   # retrieve one buffer of data using Pyadi-iio  	

            fmt = "%dI" % samples
            yr = np.array( list(unpack(fmt, data_raw)) )
            vdat = calcVolt(yr)
            totalPoints += len(vdat)
            mV = vdat * 1000
            np.savetxt(fout, mV, fmt='%0.5f')  # save out readings to disk in mV

            print("%.2f" % mV[0],end=" ", flush=True)
            if outState1:
              if outLevel1:
                fout.write(", ")  # 2nd column: input1 went high
                print("T1H, ",end="")
              else:
                fout.write(",, ") # 3rd column, input1 went low
                print("T1L, ",end="")

              fout.write("%5.1f\n" % tDelta1) # GPIO edge time delta, to file
              # print("%5.1f, " % tDelta1) # GPIO edge time delta from prior, to display
              outState1 = False

            if outState2:
              if outLevel2:
                fout.write(",,, ") # 4th column: input2 went high
                print("T2H, ",end="")
              else:
                fout.write(",,,, ") # 5th column: input2 went low
                print("T2L, ",end="")

              fout.write("%5.1f\n" % tDelta2) # GPIO edge time delta, to file
              # print("%5.1f, " % tDelta2) # GPIO edge time delta from prior, to display
              outState2 = False

            packets += 1
            if (packets % dispLines) == 0:
                avg = np.average(mV)
                std = np.std(mV)
                now = datetime.now()
                time = now.strftime('%H:%M:%S')
                print("Time:%s avg: %.3f std: %.3f" % (time, avg, std))
          except Exception as e:
            print("Had error:")
            print(e)
            break
        

# ---------------------------------------------------------------
# logging.basicConfig(level=logging.DEBUG,format='(%(threadName)-9s) %(message)s',)

if __name__ == "__main__":

    # ----- GPIO pin config ----
    GPIO.setwarnings(False)  # avoid nag about GPIO already in use
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(IN1_GPIO, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)  # external input #1
    GPIO.setup(IN2_GPIO, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)  # external input #2
    GPIO.setup(LED_GPIO, GPIO.OUT)
    GPIO.add_event_detect(IN1_GPIO, GPIO.BOTH,
            callback=button_callback, bouncetime=20)
    GPIO.add_event_detect(IN2_GPIO, GPIO.BOTH,
            callback=button_callback, bouncetime=20)


    signal.signal(signal.SIGINT, signal_handler)  # control-C
    # ------------
    outState1 = False  # if this pin had a state change
    outState2 = False
    outLevel1 = False  # GPIO level after most recent change
    outLevel2 = False

    tOld1 = time.time_ns()  # time since epoch, in nanoseconds
    tOld2 = tOld1
    tDelta1 = 0             # time delta between GPIO input edges
    tDelta2 = 0



    ADC_IP = "analog.local"
    saveDir = "."         # By default, save logged data in current directory
       
    print(version)        # this program version       
    argc = len(sys.argv)
    if (argc < 2):      # with no arguments, just print help message
        print("Usage: %s <IP_address> [<output_directory>] [<msec_aq>] [<sample_rate>]" % sys.argv[0])
        print("  <IP_address> : domain name, eg. 'analog.local' or IP address of host eg. '192.168.1.202'")
        print("  <output_directory> : where to store recorded data, defaults to current directory")
        print("  <msec_aq> : how many milliseconds for each acquisition (default 500 msec)")
        print("  <sample_rate> : how many samples per second (default 1000 samples per second)")
        print()
        
        print("Example:\n   %s analog C:/temp 500 1000\n" % sys.argv[0])
        sys.exit()
        
    if (argc > 1):
        ADC_IP = sys.argv[1]  # takes one argument, the IP address of target device            
        
    adc1_ip = "ip:"+ADC_IP       # local LAN RPi with attached ADC
    print("Using ADC device IP:%s" % ADC_IP)

    if (argc > 4):        
        rate = int(sys.argv[4])
    if (argc > 3):
        msec = int(sys.argv[3])
        aqTime = msec / 1000.0
    if (argc > 2):
        saveDir = sys.argv[2]  # takes one argument, the IP address of target device
        print("Data save directory: %s" % saveDir)
    else:
        thisDir = pathlib.Path().resolve()
        print("Data save directory: %s" % thisDir)
                
    if (not os.access(saveDir, os.W_OK)):
        print("Error: directory '%s' is not writable." % saveDir)
        sys.exit()

    signal.signal(signal.SIGINT, signal_handler)  # handle SIGINT from Control-C
    #signal.pause()

    samples = int(aqTime * rate)    # record this many points at one time
    now = datetime.now()
    timeString = now.strftime('%Y-%m-%d %H:%M:%S')
    fname = now.strftime('%Y%m%d_%H%M%S_log')
    datfile = saveDir +"/" + fname + ("_%d.csv" % rate)       # use this file to save ADC readings       
    print("recording to file: %s  at %d sps, dur %.3f sec"  % (datfile,rate,aqTime))
    print("Type control-C to stop recording")
        
    fout = open(datfile, "w")       # erase pre-existing file if any

    runADC()
