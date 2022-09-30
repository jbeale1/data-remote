#!/home/john/anaconda3/bin/python3

# Measure voltage with AD7124 ADC chip
# handle data with separate thread using queue structure
# J.Beale 30-Sep-2022

import adi
import numpy as np
from struct import unpack
import sys
import datetime      # time of day
import queue         # transfer ADC data between threads
import threading     # producer and consumer threads
import time          # for time.sleep()
import logging       # thread-safe log info


setDur = 0.5      # duration of 1 set in seconds
rate = 10000         # readings per second
samples = int(setDur * rate) # record this many points at one time

saveDir = "C:/temp"         # directory to save logged data
adc1_ip = "ip:analog.local" # local RPi with ADC

# ----------------------------------------------------    
# set up ADC chip through Pyadi-iio system

def initADC(rate, samples, adc1_ip):
  adc1 = adi.ad7124(uri=adc1_ip)
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
# get the ADC data off the queue, display and save it

def processData(q, samples, fout):
    while True:
        i,data_raw = q.get()
        fmt = "%dI" % samples
        yr = np.array( list(unpack(fmt, data_raw)) )
        print(i,yr)
        # yD = yr.reshape(-1, R).mean(axis=1) # average each set of R values        
        #np.savetxt(fout, yr, fmt='%+0.5f')  # save out readings to disk        
        np.savetxt(fout, yr, fmt='%d')  # save out readings to disk        
        fout.flush()  # update file on disk
        q.task_done()  # finished handling this queue item

# ----------------------------------------------------    
# put the ADC data on the queue

def getData(q, eRun, eStop, adc1):
    i = 0  # count of received data packets    
    while (not eStop.is_set()):
        while eRun.is_set():
        #for i in range(20):
            data_raw = adc1.rx()  # retrieve one buffer of data using Pyadi-iio  
            q.put((i,data_raw))
            i += 1
    logging.debug('now finished getData')
    
# ----------------------------------------------------    
# --- Main Program starts here -----------------------

if __name__ == '__main__':

    logging.basicConfig(level=logging.DEBUG,
                    format='(%(threadName)-9s) %(message)s',)
                    
    q = queue.Queue()                   # create a queue object
    eRun = threading.Event()            # event controls when data aq runs
    eStop = threading.Event()           # event controls when data aq exits
    
    adc1 = initADC(rate, samples, adc1_ip)  # initialize ADC with configuration

    now = datetime.datetime.now()
    fname = now.strftime('%Y%m%d_%H%M%S_log.csv')  # save data in this file

    datfile = saveDir +"/" + fname        # use this file to save ADC readings 
    fout = open(datfile, "w")       # erase pre-existing file if any
    fout.write("Temperature\n")     # column header, to read as CSV

    # start thread that handles the data   daemon=>does not block main thread exiting
    pworker = threading.Thread(target=processData, args=(q,samples,fout,), daemon=True)
    pworker.start()

    data_raw = adc1.rx()  # first buffer we just throw away (turn-on transient)

    # start thread that acquires the data
    dataq_worker = threading.Thread(target=getData, args=(q,eRun,eStop,adc1,), daemon=True)
    dataq_worker.start()

    # ----------------------------------------------------    
    # Producer and Consumer threads do all the work.
    # Possibly do various main-program-like things here
    
    for j in range(15):
        print("Starting up...")
        eRun.set()   # start the data aq thread
        time.sleep(2)
        eRun.clear() # stop the data aq thread
        print("Paused...")
        time.sleep(1)        # simulate some process being too busy

    eStop.set()          # tell data.aq thread to exit
    dataq_worker.join()  # wait until data aquisition thread exits
    q.join()             # then wait until item in queue is processed

    fout.close()         # close out data log file

    del adc1 # Clean up
