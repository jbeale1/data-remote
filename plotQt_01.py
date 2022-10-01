# Acquire data from ADC using Pyadi-iio
# Plot graph and save data
# J.Beale 9/30/2022

import sys         # command-line arguments, if any
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
import logging       # thread-safe log info

from PyQt5 import QtCore, QtGui, QtWidgets
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

matplotlib.use('Qt5Agg')   # connect matplotlib to PyQt5

# ----------------------------------------------------    
# Configure Program Settings

#adc1_ip = "ip:analog.local" # local LAN RPi with attached ADC
adc1_ip = "ip:192.168.1.159" # local LAN RPi with attached ADC
saveDir = "C:/temp"         # directory to save logged data

aqTime = 0.50      # duration of 1 dataset, in seconds
rate = 100         # readings per second

R = 10             # decimation ratio: points averaged together before saving
samples = int(aqTime * rate) # record this many points at one time

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
  adc1._ctx.set_timeout(1000000)  # in what units is this?
  return adc1
  
# ----------------------------------------------------    
# calculate temp in deg.C from ADC reading of thermistor

KtoC = -273.15   # add this to K to get degrees C
Kref = 25 - KtoC # thermistor reference temp in K
Beta = 3380 # for Murata 10k 1% NXRT15XH103FA1B020
Rinf = 1E4 * math.e**(-Beta / (Kref))

def calcTemp(rawADC):  
    f = rawADC / (2**24)       # ADC as fraction of full-scale
    R = (2E4 * f) / (1.0 - f)  # resistance in ohms
    Rf = R / Rinf
    T = (Beta / np.log(Rf)) + KtoC
    return T  
# ----------------------------------------------------    

class MplCanvas(FigureCanvasQTAgg):

    def __init__(self, parent=None, width=9, height=7, dpi=100):
        fig, (self.axes, self.ax2) = matplotlib.pyplot.subplots(2,1) # two plots vertically
        fig.set_size_inches(width, height)
        # fig = Figure(figsize=(width, height), dpi=dpi)
        # self.axes = fig.add_subplot(111)
        super(MplCanvas, self).__init__(fig)

class Communicate(QtCore.QObject):  # create a custom signal indicating when data is received

    gotData = QtCore.pyqtSignal()


class MainWindow(QtWidgets.QMainWindow):

    def __init__(self, *args, **kwargs):
        super(MainWindow, self).__init__(*args, **kwargs)
        
        self.c = Communicate()               # to get the custom gotData signal
        self.c.gotData.connect(self.update_plot)  # call update_plot whenever data arrives
        
        self.Record = False                  # start out not recording
        self.Pause = False                   # start out not paused
        self.rate = rate                     # ADC sampling rate
        self.aqTime = aqTime                 # duration of one ADC data packet (seconds)
        self.samples = samples               # how many ADC samples per packet
        self.bSets = 8                       # how many packets across upper graph
        self.bStart = 0                      # location of this packet on upper graph (batch)
        self.bEnd = self.samples
        self.R = R                           # decimation ratio (samples to average)
        self.adc1_ip = adc1_ip               # local LAN RPi with attached ADC
        
        self.q = queue.Queue()                   # create a queue for ADC data
        self.eRun = threading.Event()            # event controls when data aq runs
        self.eStop = threading.Event()           # event controls when data aq exits
                
        self.rms1f = 0                       # RMS value after LP filter
        self.rms1Filt = 0.1                  # RMS value low-pass filter factor
        now = datetime.datetime.now()
        fname = now.strftime('%Y%m%d_%H%M%S_log.csv')

        datfile = saveDir +"/" + fname        # use this file to save ADC readings 
        
        self.fout = open(datfile, "w")       # erase pre-existing file if any
        self.fout.write("Temperature\n")     # column header, to read as CSV

        timeString = now.strftime('%Y-%m-%d %H:%M:%S')
        # self.fout.write("# Program Start: %s\n" % timeString)
        self.fout.flush()
        
        self.setWindowTitle("ADC Plot v0.12")
        width = 1000  # fixed width of window
        height = 700
        self.setMinimumSize(width, height)
        
        self.canvas = MplCanvas(self)
        #self._adc1 = initADC(rate, samples)  # initialize ADC chip        

        self.batch = np.zeros(self.samples*self.bSets)    # data points of upper plot (fixed time span)
        self.dataLog = np.array([])  # data points for lower plot, maybe sub-sampled
        self._plot_ref = None

        
        # set up GUI layout
        btnLayout = QtWidgets.QHBoxLayout()  # a horizontal bar of button controls
        btnLayout.addWidget(QtWidgets.QPushButton('Start'))
        
        self.b2 = QtWidgets.QPushButton('Pause Display')
        self.b2baseColor = self.b2.palette().color(QtGui.QPalette.Background).name()
        self.b2.setStyleSheet("background-color : " + self.b2baseColor)
        self.b2.setCheckable(True)
        self.b2.clicked.connect(self.doPause)
        btnLayout.addWidget(self.b2)

        
        self.b3 = QtWidgets.QPushButton('Record')
        self.b3baseColor = self.b3.palette().color(QtGui.QPalette.Background).name()
        self.b3.setStyleSheet("background-color : " + self.b3baseColor)
        self.b3.setCheckable(True)
        self.b3.clicked.connect(self.doRecord)
        btnLayout.addWidget(self.b3)

        self.b4 = QtWidgets.QPushButton('Reset Plot')
        self.b4.clicked.connect(self.doReset)
        btnLayout.addWidget(self.b4)
        
        self.l6 = QtWidgets.QLabel(" ADC Config")
        btnLayout.addWidget(self.l6)
        
        self.sb6 = QtWidgets.QDoubleSpinBox()  # set duration of sample size
        self.sb6.setValue(self.aqTime)
        self.sb6.setSuffix(" sec")
        #self.sb6.valueChanged.connect(self.sb6update)  # on every kepress
        #self.sb6.editingFinished.connect(self.sb6update) # only after 'Enter'
        btnLayout.addWidget(self.sb6)
                
        self.sb7 = QtWidgets.QSpinBox()  # set samples per second
        self.sb7.setRange(100, 19200)   # range of possible sampling rates        
        self.sb7.setValue(self.rate)  # how come 100 prints as 99?
        self.sb7.setSuffix(" sps")        
        btnLayout.addWidget(self.sb7)

        self.b8 = QtWidgets.QPushButton('Update Config')  # load the new ADC config values
        self.b8.clicked.connect(self.setup_update)
        btnLayout.addWidget(self.b8)
        
        self.l9 = QtWidgets.QLabel("Avg")
        btnLayout.addWidget(self.l9)

        self.sb9 = QtWidgets.QSpinBox()  # set decimation ratio (samples to average)
        self.sb9.setRange(1, 1000)   # range of possible averaging ratios
        self.sb9.setValue(self.R)  # how come 100 prints as 99?        
        btnLayout.addWidget(self.sb9)
        
        btnLayout.addStretch(1)
        self.b5 = QtWidgets.QPushButton('Quit')  # last button is to quit
        self.b5.clicked.connect(self.doQuit)
        btnLayout.addWidget(self.b5)

        graphLayout = QtWidgets.QVBoxLayout()   # graph with its toollbar at top
        toolbar = NavigationToolbar(self.canvas, self)
        graphLayout.addWidget(toolbar)
        graphLayout.addWidget(self.canvas)
        
        outerLayout = QtWidgets.QVBoxLayout()
        outerLayout.addLayout(btnLayout)
        outerLayout.addLayout(graphLayout)
        
        widget = QtWidgets.QWidget(self)
        widget.setLayout(outerLayout)        
        self.setCentralWidget(widget)
                        
        self.adc1 = initADC(self.rate, self.samples, self.adc1_ip)  # initialize ADC with configuration
        
        # start thread that acquires the data
        dataq_worker = threading.Thread(target=self.getData, daemon=True)
        dataq_worker.start()  # start up the acquisition thread
        
        self.eRun.set()   # enable the data aq thread         
        

    def setup_update(self):
        self.eRun.clear()         # stop acquisition loop
        time.sleep(self.aqTime+0.2)   # enough time for current acquisition to finish
        self.q.queue.clear()      # remove any old data packets in queue (of previous size)       
        self.aqTime = self.sb6.value()
        self.rate = self.sb7.value()        
        self.samples = int(self.aqTime * self.rate) # sampling rate; this many per second
        Rnom = self.sb9.value()   # find best workable value for decimation ratio
        rem = (self.samples % Rnom)    # decimation ratio must divide sample count evenly
        # print("%d, %d, %d" % (self.samples, Rnom, rem))
        if (rem == 0):
            self.R = Rnom
        self.sb9.setValue(self.R)
        
        self.bStart = 0                      # location of this packet on upper graph (batch)
        self.bEnd = self.samples
        self.batch = np.zeros(self.samples*self.bSets)    # data points of upper plot (fixed time span)                
        self.adc1 = initADC(self.rate, self.samples, self.adc1_ip)  # initialize ADC with configuration
        self.eRun.set()     # restart acquistion loop
        
    def getData(self):   # thread that acquires ADC data        
        #logging.debug('getData startup')        
        while (not self.eStop.is_set()):
            while self.eRun.is_set():
                data_raw = self.adc1.rx()   # retrieve one buffer of data using Pyadi-iio  
                self.q.put(data_raw)
                self.c.gotData.emit()       # tell main thread we've now got data
                #logging.debug('gotData...')        
        #logging.debug('now finished getData')        

    def doPause(self):     
        if self.b2.isChecked():
            self.b2.setStyleSheet("background-color : azure4")    
            #self.eRun.clear()  # stop acquisition loop
            self.Pause = True
        else:
            self.b2.setStyleSheet("background-color : " + self.b2baseColor)    
            #self.eRun.set()  # restart acquisition loop
            self.Pause = False
            
    def doRecord(self):     
        if self.b3.isChecked():
            self.b3.setStyleSheet("background-color : red")
            self.Record = True
            now = datetime.datetime.now()
            timeString = now.strftime('%Y-%m-%d %H:%M:%S')
            self.fout.write("# Start: %s\n" % timeString)

        else:
            self.b3.setStyleSheet("background-color : " + self.b3baseColor)    
            self.Record = False
            now = datetime.datetime.now()
            timeString = now.strftime('%Y-%m-%d %H:%M:%S')
            self.fout.write("# End: %s\n\n" % timeString)
            self.fout.flush()
        
    def doReset(self):
        self.dataLog = np.array([])  # zero out data log

    def doQuit(self):        
        self.Pause = True  # stop GUI update
        self.eRun.clear()  # stop acquisition loop
        self.eStop.set()   # send signal closing out acquisition thread
        self.fout.close()  # close data logfile
        self.close()       # close window
        
    def update_plot(self):       
        if self.eStop.is_set():  # no updates if stop signal set
            return
        if self.q.empty():
            self.show()          # needed to handle mouse events?
            return
        data_raw = self.q.get()  # retrieve oldest data from queue
        fmt = "%dI" % self.samples
        yr = np.array( list(unpack(fmt, data_raw)) )

        now = datetime.datetime.now()
        timeString = now.strftime('%Y-%m-%d %H:%M:%S')

        self.ydata = calcTemp(yr)  # convert raw readings into Temp, deg.C  

        if (self.R > 1):  # decimate (average & downsample)
            yD = self.ydata.reshape(-1, self.R).mean(axis=1) # average each set of R values        
        else:
            yD = self.ydata
        self.dataLog = np.append(self.dataLog, yD)  # add new data to cumulative array

        # save out downsampled version of data to a file on disk
        if (self.Record):
            np.savetxt(self.fout, yD, fmt='%+0.5f')  # save out readings to disk
            self.fout.flush()  # update file on disk
        

        if ( not self.Pause):  # update graphs if we are not in paused mode
        
            self.xdata = np.arange(1,len(self.batch)+1)  # create a matching X axis        
            bEdge = self.samples * self.bSets  # right-most point on top "batch" graph
            # print("%d, %d, %d" %(self.bStart,self.bEnd, bEdge))
            self.batch[self.bStart:self.bEnd] = self.ydata
            self.bStart += self.samples
            self.bEnd += self.samples
            if (self.bEnd > bEdge):
                self.bStart = 0
                self.bEnd = self.samples
            ax = self.canvas.axes   # axis for first plot (upper graph)
            ax.cla()  # clear old data
            fmt=ticker.ScalarFormatter(useOffset=False)
            fmt.set_scientific(False)  
            #ax.scatter(self.xdata,self.ydata,s=2, color="green")  # show samples as points
            ax.scatter(self.xdata,self.batch,s=2, color="green")  # show samples as points
            ax.grid(color='gray', linestyle='dotted' )
            ax.set_xlabel("samples", fontsize = 10)
            ax.yaxis.set_major_formatter(fmt) # turn off Y offset mode
            ax.set_title('Temperature vs Time', fontsize = 15)
            
            rms1 = np.std(self.ydata)  # instantaneous std.dev. value
            self.rms1f = (1.0-self.rms1Filt)*self.rms1f + self.rms1Filt*rms1  # low-pass filtered value
            rmsString = ("%.2f mC RMS" % (self.rms1f*1E3))
             
            ymin,ymax = self.canvas.axes.get_ylim() # find range of displayed values
            xmin,xmax = self.canvas.axes.get_xlim()
            yrange = ymax-ymin
            xrange = xmax-xmin
            xpos = xmin + 1.0*xrange  # location for time/date
            xpos1 = xmin + 0.01*xrange  # location for time/date            
            ypos = ymin + 1.01*yrange # top of chart
            ax.text(xpos,ypos, timeString, style='italic', horizontalalignment='right')  # date,time string
            ax.text(xpos1,ypos, rmsString, fontsize=12)
                        
            totalPoints = len(self.dataLog)  # plot lower graph (accumulated points)
            x2 = np.arange(totalPoints)
            x2 = x2 * self.R * self.aqTime/self.samples
            self.canvas.ax2.cla()  # clear old data
            self.canvas.ax2.scatter(x2, self.dataLog, s=1)   # plot of accumulated past data
            self.canvas.ax2.set_xlabel("seconds", fontsize = 10)
            self.canvas.ax2.set_ylabel("degrees C", fontsize = 10)
            self.canvas.ax2.grid(color='gray', linestyle='dotted')
            self.canvas.ax2.yaxis.set_major_formatter(fmt)
            self.canvas.draw()   # redraw plot on canvas   
            self.show()  # show the canvas

# ---------------------------------------------------------------
# logging.basicConfig(level=logging.DEBUG,format='(%(threadName)-9s) %(message)s',)

app = QtWidgets.QApplication(sys.argv)
w = MainWindow()

app.exec_()

