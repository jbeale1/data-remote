# Acquire data from ADC using Pyadi-iio
# Plot graph and save data
# J.Beale 11/07/2022

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
import logging       # thread-safe log info

from PyQt5 import QtCore, QtGui, QtWidgets
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

matplotlib.use('Qt5Agg')   # connect matplotlib to PyQt5

# ----------------------------------------------------
# Configure Program Settings

version = "ADC Plot v0.21  (7-Nov-2022)"   # this particular code version number


aqTime = 1.0      # duration of 1 dataset, in seconds
rate = 10000         # readings per second
R = 10             # decimation ratio: points averaged together before saving
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

    #addr = 0x19  # CONFIG_0 register
    #reg = phy.reg_read(addr)  # read reguster
    #print("Before: {0:02x}: {1:02x}".format(addr, reg))
    #phy.reg_write(addr, 0x810)  # write to register
    #reg = phy.reg_read(addr)  # read it back
    #print("After: {0:02x}: {1:02x}".format(addr, reg))

    return adc1

# ----------------------------------------------------
# calculate temp in deg.C from ADC reading of thermistor

Vref = 2.500 # voltage of ADC reference

avgMean = 0.004136345  # long-term filtered mean
mLPF = 0.01       # low-pass filter constant


def calcVolt(rawADC):
    V = Vref * rawADC / (2**24)       # ADC as fraction of full-scale
    return V

# ----------------------------------------------------

class MplCanvas(FigureCanvasQTAgg):

    def __init__(self, parent=None, width=9, height=7, dpi=100):
        #fig, (self.axes, self.ax2) = matplotlib.pyplot.subplots(2,1) # two plots vertically
        #fig.set_size_inches(width, height)
        fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = fig.add_subplot(111)
        super(MplCanvas, self).__init__(fig)

class Communicate(QtCore.QObject):  # create a custom signal indicating when data is received

    gotData = QtCore.pyqtSignal()


class MainWindow(QtWidgets.QMainWindow):

    def __init__(self, *args, **kwargs):
        super(MainWindow, self).__init__(*args, **kwargs)

        self.saveDir = saveDir               # directory to save data in
        self.Record = False                  # start out not recording
        self.Pause = False                   # start out not paused
        self.rate = rate                     # ADC sampling rate
        self.aqTime = aqTime                 # duration of one ADC data packet (seconds)
        self.samples = samples               # how many ADC samples per packet
        self.bSets = 5                       # how many packets across upper graph
        self.rCount = 0                      # how many packets recorded to file
        self.bStart = 0                      # location of start of this packet on graph (batch)
        self.bEnd = int(self.samples / R)         # location of end of this packet
        self.R = R                           # decimation ratio (samples to average)
        self.adc1_ip = adc1_ip               # local LAN RPi with attached ADC

        self.adc1 = initADC(self.rate, self.samples, self.adc1_ip)  # initialize ADC with configuration
        if (self.adc1 is None):
            print("Error: unable to connect to ADC %s" % self.adc1_ip)
            self.close()
            sys.exit()                       # leave entire program

        self.c = Communicate()               # to get the custom gotData signal
        self.c.gotData.connect(self.update_plot)  # call update_plot whenever data arrives

        self.q = queue.Queue()                   # create a queue for ADC data
        self.eRun = threading.Event()            # event controls when data aq runs
        self.eStop = threading.Event()           # event controls when data aq exits

        self.rms1f = 0                       # RMS value after LP filter
        self.rms1Filt = 0.1                  # RMS value low-pass filter factor

        now = datetime.datetime.now()
        timeString = now.strftime('%Y-%m-%d %H:%M:%S')

        self.setWindowTitle(version)
        width = 1000  # fixed width of window
        height = 700
        self.setMinimumSize(width, height)

        self.canvas = MplCanvas(self)
        #self._adc1 = initADC(rate, samples)  # initialize ADC chip

        self.batch = np.zeros(int(self.samples*self.bSets/self.R))    # data points of upper plot (fixed time span)
        #self.dataLog = np.array([])  # data points for lower plot, maybe sub-sampled
        self._plot_ref = None


        # set up GUI layout
        btnLayout = QtWidgets.QHBoxLayout()  # a horizontal bar of button controls
        # btnLayout.addWidget(QtWidgets.QPushButton('Start'))

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

        self.l9 = QtWidgets.QLabel("Avg")
        btnLayout.addWidget(self.l9)

        self.sb9 = QtWidgets.QSpinBox()  # set decimation ratio (samples to average)
        self.sb9.setRange(1, 1000)   # range of possible averaging ratios
        self.sb9.setValue(self.R)  # how come 100 prints as 99?
        btnLayout.addWidget(self.sb9)

        self.la = QtWidgets.QLabel("Seg")
        btnLayout.addWidget(self.la)

        self.sba = QtWidgets.QSpinBox()  # set decimation ratio (samples to average)
        self.sba.setRange(1, 100)   # range of possible segments
        self.sba.setValue(self.bSets)
        btnLayout.addWidget(self.sba)


        self.b8 = QtWidgets.QPushButton('Update')  # load the new ADC config values
        self.b8.clicked.connect(self.setup_update)
        btnLayout.addWidget(self.b8)

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

        self.bStart = 0                      # location of start of this packet on graph (batch)
        self.bEnd = int(self.samples / self.R)         # location of end of this packet
        self.bSets = self.sba.value()        # how many sets in upper graph batch
        self.batch = np.zeros(int(self.samples*self.bSets/self.R))    # data points of upper plot (fixed time span)
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
            fname = now.strftime('%Y%m%d_%H%M%S_log.csv')
            datfile = self.saveDir +"/" + fname        # use this file to save ADC readings
            self.fout = open(datfile, "w")       # erase pre-existing file if any
            self.fout.write("mV\n")     # column header, to read as CSV
            #self.fout.write("# Start: %s\n" % timeString)
            self.fout.flush()

        else:
            self.b3.setStyleSheet("background-color : " + self.b3baseColor)
            self.Record = False
            now = datetime.datetime.now()
            timeString = now.strftime('%Y-%m-%d %H:%M:%S')
            self.fout.write("# End: %s\n\n" % timeString)
            self.fout.close()

    def doReset(self):
        self.dataLog = np.array([])  # zero out data log

    def doQuit(self):
        self.Pause = True  # stop GUI update
        self.eRun.clear()  # stop acquisition loop
        self.eStop.set()   # send signal closing out acquisition thread
        try:
            self.fout.close()  # close data logfile, if it was ever opened
        except:
            pass           # no file opened
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

        sRec = (self.rCount * aqTime)   # recorded data duration in seconds
        now = datetime.datetime.now()
        timeString = now.strftime('%Y-%m-%d %H:%M:%S')
        timeString = ("Rec:%.1fs    " % sRec) + timeString  # add "Seconds Recorded" to time
        
        volts = calcVolt(yr)  # convert raw readings into Temp, deg.C
        #self.ydata = calcSeis(volts)  # integrate and filter data
        self.ydata = volts

        if (self.R > 1):  # decimate (average & downsample)
            yD = self.ydata.reshape(-1, self.R).mean(axis=1) # average each set of R values
        else:
            yD = self.ydata

        # self.dataLog = np.append(self.dataLog, yD)  # add new data to ever-larger cumulative array

        # save out data to a file on disk
        if (self.Record):
            np.savetxt(self.fout, self.ydata*1000, fmt='%0.5f')  # save out readings to disk in mV
            self.fout.flush()  # update file on disk
            self.rCount += 1   # increment count of recorded data
            # print("Seconds Recorded: %5.1f" % (self.rCount * aqTime))  # DEBUG


        if ( not self.Pause):  # update graphs if we are not in paused mode

            self.xdata = np.arange(1,len(self.batch)+1)  # create a matching X axis
            bEdge = (self.samples * self.bSets / self.R)  # right-most point on top "batch" graph
            # print("%d, %d, %d" %(self.bStart,self.bEnd, bEdge))
            self.batch[self.bStart:self.bEnd] = yD
            self.bStart += int(self.samples / self.R)
            self.bEnd += int(self.samples / self.R)
            if (self.bEnd > bEdge):
                self.bStart = 0
                self.bEnd = int(self.samples / self.R)
            ax = self.canvas.axes   # axis for first plot (upper graph)
            ax.cla()  # clear old data
            fmt=ticker.ScalarFormatter(useOffset=False)
            fmt.set_scientific(False)
            #ax.scatter(self.xdata,self.ydata,s=2, color="green")  # show samples as points
            #ax.scatter(self.xdata,self.batch,s=1, color="green")  # show samples as points
            ax.plot(self.xdata,self.batch, linewidth=1, color="green")  # show samples as lines
            ax.grid(color='gray', linestyle='dotted' )
            ax.set_xlabel("samples", fontsize = 10)
            ax.yaxis.set_major_formatter(fmt) # turn off Y offset mode
            ax.set_title('Voltage vs Time', fontsize = 15)

            rms1 = np.std(self.ydata)  # instantaneous std.dev. value
            self.rms1f = (1.0-self.rms1Filt)*self.rms1f + self.rms1Filt*rms1  # low-pass filtered value
            
            #rmsString = ("%.3f mV RMS   R:%.1fs" % (self.rms1f*1E3, sRec))
            rmsString = ("%.3f mV RMS" % (self.rms1f*1E3))

            ymin,ymax = self.canvas.axes.get_ylim() # find range of displayed values
            xmin,xmax = self.canvas.axes.get_xlim()
            yrange = ymax-ymin
            xrange = xmax-xmin
            xpos = xmin + 1.0*xrange  # location for time/date
            xpos1 = xmin + 0.01*xrange  # location for time/date
            ypos = ymin + 1.01*yrange # top of chart
            ax.text(xpos,ypos, timeString, style='italic', horizontalalignment='right')  # date,time string
            ax.text(xpos1,ypos, rmsString, fontsize=12)

            """
            totalPoints = len(self.dataLog)  # plot lower graph (accumulated points)
            x2 = np.arange(totalPoints)
            x2 = x2 * self.R * self.aqTime/self.samples
            self.canvas.ax2.cla()  # clear old data
            #self.canvas.ax2.scatter(x2, self.dataLog, s=1)   # plot of accumulated past data
            self.canvas.ax2.plot(x2, self.dataLog, linewidth=1)   # plot of accumulated past data
            self.canvas.ax2.set_xlabel("seconds", fontsize = 10)
            self.canvas.ax2.set_ylabel("Volts", fontsize = 10)
            self.canvas.ax2.grid(color='gray', linestyle='dotted')
            self.canvas.ax2.yaxis.set_major_formatter(fmt)
            """
            
            self.canvas.draw()   # redraw plot on canvas
            self.show()  # show the canvas

# ---------------------------------------------------------------
# logging.basicConfig(level=logging.DEBUG,format='(%(threadName)-9s) %(message)s',)

if __name__ == "__main__":

    #ADC_IP = "192.168.1.202"
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

    app = QtWidgets.QApplication([])
    w = MainWindow()

    app.exec_()
