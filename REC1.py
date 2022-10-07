# Acquire data from ADC using Pyadi-iio
# Plot graph and save data
# J.Beale 10/04/2022

import sys         # command-line arguments, if any
import os          # test if directory is writable
import pathlib     # find current working directory
import matplotlib  # plotting data on graphs
import matplotlib.pyplot
import matplotlib.ticker as ticker  # turn off Y offset mode
import datetime    # current date & time
import adi         # Pyadi-iio interface to AD7124 ADC
import numpy as np # array manipulations
from struct import unpack  # extract words from packed binary buffer
import math        # for constant 'e'
import queue         # transfer ADC data between threads
import threading     # producer and consumer threads
import time          # for time.sleep()

from PyQt5 import QtCore, QtGui, QtWidgets
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

matplotlib.use('Qt5Agg')   # connect matplotlib to PyQt5

# ----------------------------------------------------    
# Configure Program Settings

version = "ADC Plot v0.15  (4-Oct-2022)"   # this particular code version number


aqTime = 0.50      # duration of 1 dataset, in seconds
rate = 1000         # readings per second
R = 1             # decimation ratio: points averaged together before saving
samples = int(aqTime * rate) # record this many points at one time

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
        
        self.saveDir = saveDir               # directory to save data in
        self.Record = False                  # start out not recording
        self.Pause = False                   # start out not paused
        self.rate = rate                     # ADC sampling rate
        self.aqTime = aqTime                 # duration of one ADC data packet (seconds)
        self.samples = samples               # how many ADC samples per packet
        self.bSets = 10                       # how many packets across upper graph
        self.bStart = 0                      # location of this packet on upper graph (batch)
        self.bEnd = self.samples
        self.R = R                           # decimation ratio (samples to average)
        self.adc1_ip = adc1_ip               # local LAN RPi with attached ADC

        self.adc1 = initADC(self.rate, self.samples, self.adc1_ip)  # initialize ADC with configuration
        if (self.adc1 is None):
            print("Error: unable to connect to ADC %s" % self.adc1_ip)
            self.close()
            sys.exit()                       # leave entire program

        now = datetime.datetime.now()
        timeString = now.strftime('%Y-%m-%d %H:%M:%S')
        
        fname = now.strftime('%Y%m%d_%H%M%S_log.csv')
        datfile = self.saveDir +"/" + fname        # use this file to save ADC readings       
        
        self.fout = open(datfile, "w")       # erase pre-existing file if any
        self.fout.write("mV\n")     # column header, to read as CSV            
        self.fout.flush()
        
        while ( True ):
            data_raw = self.adc1.rx()   # retrieve one buffer of data using Pyadi-iio  
            fmt = "%dI" % self.samples
            yr = np.array( list(unpack(fmt, data_raw)) )
            np.savetxt(self.fout, yr*1000, fmt='%0.5f')  # save out readings to disk in mV
        

# ---------------------------------------------------------------
# logging.basicConfig(level=logging.DEBUG,format='(%(threadName)-9s) %(message)s',)

if __name__ == "__main__":

    ADC_IP = "analog.local"
    saveDir = "."         # By default, save logged data in current directory
       
    print(version)        # this program version       
    argc = len(sys.argv)
    if (argc < 2):      # with no arguments, just print help message
        print("Usage: %s <IP_address> [<output_directory>]" % sys.argv[0])
        print("  <IP_address> : domain name, eg. 'analog.local' or IP address of host with ADC")
        print("  <output_directory> : where to store recorded data, defaults to current directory\n")
        print("Example:\n   %s 192.168.1.202 C:/temp \n" % sys.argv[0])
        sys.exit()
        
    if (argc > 1):
        ADC_IP = sys.argv[1]  # takes one argument, the IP address of target device            
        
    adc1_ip = "ip:"+ADC_IP       # local LAN RPi with attached ADC
    print("Using ADC device IP:%s" % ADC_IP)

    if (argc > 2):
        saveDir = sys.argv[2]  # takes one argument, the IP address of target device
        print("Data save directory: %s" % saveDir)
    else:
        thisDir = pathlib.Path().resolve()
        print("Data save directory: %s" % thisDir)
                
    if (not os.access(saveDir, os.W_OK)):
        print("Error: directory '%s' is not writable." % saveDir)
        sys.exit()

    runADC()
