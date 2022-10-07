# Acquire data from ADC using Pyadi-iio
# save data to file on disk
# J.Beale 10/07/2022

import sys         # command-line arguments, if any
import os          # test if directory is writable
import pathlib     # find current working directory
import datetime    # current date & time
import adi         # Pyadi-iio interface to AD7124 ADC
import numpy as np # array manipulations
from struct import unpack  # extract words from packed binary buffer
import math        # for constant 'e'
import queue         # transfer ADC data between threads
import time          # for time.sleep()


import signal       # handle control-C

# ----------------------------------------------------    
# Configure Program Settings

version = "ADC Record v0.11  (7-Oct-2022)"   # this particular code version number


aqTime = 0.50      # duration of 1 dataset, in seconds
rate = 1000         # readings per second
R = 1             # decimation ratio: points averaged together before saving
totalPoints = 0                 # total points recorded so far        

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
    now = datetime.datetime.now()
    timeString = now.strftime('%Y-%m-%d %H:%M:%S')
    print('\nProgram stopped at %s' % timeString)
    fout.write('# Program stopped at %s' % timeString)
    print("Total data points: %d" % totalPoints)
    fout.close()    
    sys.exit(0)


# ----------------------------------------------------    
# calculate temp in deg.C from ADC reading of thermistor

KtoC = -273.15   # add this to K to get degrees C
Kref = 25 - KtoC # thermistor reference temp in K
Beta = 3380 # for Murata 10k 1% NXRT15XH103FA1B020
Rinf = 1E4 * math.e**(-Beta / (Kref))
Vref = 2.500 # voltage of ADC reference

avgMean = 0.004136345  # long-term filtered mean
mLPF = 0.01       # low-pass filter constant

def calcTemp(rawADC):  
    f = rawADC / (2**24)       # ADC as fraction of full-scale
    R = (2E4 * f) / (1.0 - f)  # resistance in ohms
    Rf = R / Rinf
    T = (Beta / np.log(Rf)) + KtoC
    return T  

def calcVolt(rawADC):  
    V = Vref * rawADC / (2**24)       # ADC as fraction of full-scale
    return V
    
def calcSeis(volts):
    global avgMean
    avgMean = (1-mLPF)*avgMean + mLPF*np.average(volts)
    detrend = volts - avgMean
    # print(avgMean)
    seis = np.cumsum(detrend)
    return seis

# ----------------------------------------------------    


def runADC():
        global totalPoints     # how many points we've seen
        
        adc1 = initADC(rate, samples, adc1_ip)  # initialize ADC with configuration
        if (adc1 is None):
            print("Error: unable to connect to ADC %s" % adc1_ip)
            close()
            sys.exit()                       # leave entire program
        
        fout.write("mV\n")     # column header, to read as CSV            
        fout.flush()
        
        packets = 0
        while ( True ):
          try:
            data_raw = adc1.rx()   # retrieve one buffer of data using Pyadi-iio  
            fmt = "%dI" % samples
            yr = np.array( list(unpack(fmt, data_raw)) )
            vdat = calcVolt(yr)
            totalPoints += len(vdat)
            mV = vdat * 1000
            np.savetxt(fout, mV, fmt='%0.5f')  # save out readings to disk in mV
            print("%.3f" % mV[0],end=" ", flush=True)
            packets += 1
            if (packets % 10) == 0:
              print()
          except Exception as e:
            print("Had error:")
            print(e)
            break
        

# ---------------------------------------------------------------
# logging.basicConfig(level=logging.DEBUG,format='(%(threadName)-9s) %(message)s',)

if __name__ == "__main__":

    ADC_IP = "analog.local"
    saveDir = "."         # By default, save logged data in current directory
       
    print(version)        # this program version       
    argc = len(sys.argv)
    if (argc < 2):      # with no arguments, just print help message
        print("Usage: %s <IP_address> [<output_directory>] [<msec_aq>] [<sample_rate>]" % sys.argv[0])
        print("  <IP_address> : domain name, eg. 'analog.local' or IP address of host with ADC")
        print("  <output_directory> : where to store recorded data, defaults to current directory")
        print("  <msec_aq> : how many milliseconds for each acquisition (default 500 msec)")
        print("  <sample_rate> : how many samples per second (default 1000 samples per second)")
        print()
        
        print("Example:\n   %s 192.168.1.202 C:/temp 500 1000\n" % sys.argv[0])
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
    now = datetime.datetime.now()
    timeString = now.strftime('%Y-%m-%d %H:%M:%S')
    fname = now.strftime('%Y%m%d_%H%M%S_log')
    datfile = saveDir +"/" + fname + ("_%d.csv" % rate)       # use this file to save ADC readings       
    print("recording to file: %s  at %d sps, dur %.3f sec"  % (datfile,rate,aqTime))
        
    fout = open(datfile, "w")       # erase pre-existing file if any

    runADC()
