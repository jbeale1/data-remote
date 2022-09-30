#!/home/john/anaconda3/bin/python3

# Measure voltage with AD7124 ADC chip
# handle data with separate thread using queue structure
# J.Beale 30-Sep-2022

import adi
import numpy as np
from struct import unpack
import sys
import datetime
import queue
import threading

setDur = 0.8      # duration of 1 set in seconds
rate = 10         # readings per second
samples = int(setDur * rate) # record this many points at one time

datfile = "tdat.csv"  # save ADC readings
my_ip = "ip:analog.local" # local RPi with ADC

# ----------------------------------------------------    
# set up ADC chip through Pyadi-iio system

def initADC(rate, samples):
  adc1 = adi.ad7124(uri=my_ip)
  ad_channel = 0
  sc = adc1.scale_available
  adc1.channel[ad_channel].scale = sc[-1]  # get highest range
  scale = adc1.channel[ad_channel].scale
  adc1.sample_rate = rate  # sets sample rate for all channels
  adc1.rx_buffer_size = samples
  adc1.rx_enabled_channels = [ad_channel]
  adc1._ctx.set_timeout(1000000)
  return adc1
   
# ----------------------------------------------------    
# get the ADC data off the queue and process it

def processData(q):
    while True:
        yr = q.get()
        #fmt = "%dI" % samples
        #yr = np.array( list(unpack(fmt, data_raw)) )
        print(yr)
        q.task_done()

# ----------------------------------------------------    
# main program

adc1 = initADC(rate, samples)

# do the first run but ignore it, due to RC start transient
data_raw = adc1.rx()  

q = queue.Queue()  # create a queue object

# start the queue data processor
worker = threading.Thread(target=processData, args=(q,), daemon=True)
worker.start()
print("worker started")

for i in range(100):
    data_raw = adc1.rx()  # retrieve one buffer of data using Pyadi-iio  
    fmt = "%dI" % samples
    yr = np.array( list(unpack(fmt, data_raw)) )    
    q.put(yr)
    print("Put %d data on queue." % i)

q.join()
del adc1 # Clean up
