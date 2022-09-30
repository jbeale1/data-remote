# Acquire data from ADC using Pyadi-iio
# Plot graph and save data
# J.Beale 9/29/2022

import sys         # command-line arguments, if any
import matplotlib  # plotting data on graphs
import matplotlib.pyplot
import matplotlib.ticker as ticker  # turn off Y offset mode
import datetime    # current date & time
import adi         # Pyadi-iio interface to AD7124 ADC
import numpy as np # array manipulations
from struct import unpack  # extract words from packed binary buffer
import math        # for constant 'e'

matplotlib.use('Qt5Agg')

from PyQt5 import QtCore, QtGui, QtWidgets

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

# ----------------------------------------------------    
# Configure ADC settings

adc1_ip = "ip:analog.local" # local LAN RPi with attached ADC
saveDir = "C:/temp"         # directory to save logged data

setDur = 1.0       # duration of 1 dataset, in seconds
rate = 1000         # readings per second

samples = int(setDur * rate) # record this many points at one time
R = 500            # decimation ratio: points averaged together before saving

def initADC(rate, samples):
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


class MainWindow(QtWidgets.QMainWindow):

    def __init__(self, *args, **kwargs):
        super(MainWindow, self).__init__(*args, **kwargs)
        
        self.Record = False                  # start out not recording
        self.Pause = False                   # start out not paused

        now = datetime.datetime.now()
        fname = now.strftime('%Y%m%d_%H%M%S_log.csv')

        datfile = saveDir +"/" + fname        # use this file to save ADC readings 
        
        self.fout = open(datfile, "w")       # erase pre-existing file if any
        self.fout.write("Temperature\n")     # column header, to read as CSV

        timeString = now.strftime('%Y-%m-%d %H:%M:%S')
        # self.fout.write("# Program Start: %s\n" % timeString)
        self.fout.flush()
        
        self.setWindowTitle("ADC Plot v0.11")
        width = 1000  # fixed width of window
        height = 700
        #self.setFixedWidth(width)
        #self.setFixedHeight(height)
        self.setMinimumSize(width, height)
        
        self.canvas = MplCanvas(self)
        self._adc1 = initADC(rate, samples)  # initialize ADC chip        

        self.dataLog = np.array([])  # log for sub-sampled data
        self._plot_ref = None

        self.update_plot()
        self.show()              
        
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
        self.b5 = QtWidgets.QPushButton('Exit')
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
                
        # Setup a timer to trigger the redraw by calling update_plot.
        self.timer = QtCore.QTimer()
        self.timer.setInterval(int(setDur*1000))  # update after this many milliseconds
        self.timer.timeout.connect(self.update_plot)
        self.timer.start()                           

    def doPause(self):     
        if self.b2.isChecked():
            self.b2.setStyleSheet("background-color : azure4")    
            self.Pause = True
        else:
            self.b2.setStyleSheet("background-color : " + self.b2baseColor)    
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
        self.close()
        
    def update_plot(self):        
        data_raw = self._adc1.rx()
        fmt = "%dI" % samples
        now = datetime.datetime.now()
        timeString = now.strftime('%Y-%m-%d %H:%M:%S')

        yr = np.array( list(unpack(fmt, data_raw)) )
        self.ydata = calcTemp(yr)  # convert raw readings into Temp, deg.C  
        self.dataLog = np.append(self.dataLog, self.ydata)  # save data in array   

        # save out downsampled version of data to a file on disk
        if (self.Record):
            yD = self.ydata.reshape(-1, R).mean(axis=1) # average each set of R values        
            np.savetxt(self.fout, yD, fmt='%+0.5f')  # save out readings to disk
            # self.fout.write("# %s\n" % timeString)   # write out timestamp
            self.fout.flush()  # update file on disk

        if self._plot_ref is None:
            self.xdata = np.arange(1,len(self.ydata)+1)  # create a matching X axis        

        if ( not self.Pause):  # update graphs if we are not in paused mode
            ax = self.canvas.axes   # axis for first plot
            ax.cla()  # clear old data
            fmt=ticker.ScalarFormatter(useOffset=False)
            fmt.set_scientific(False)  
            ax.scatter(self.xdata,self.ydata,s=1, color="green")  # show samples as points
            self.canvas.axes.grid(color='gray', linestyle='dotted' )
            self.canvas.axes.set_xlabel("samples", fontsize = 10)
            self.canvas.axes.yaxis.set_major_formatter(fmt) # turn off Y offset mode
            self.canvas.axes.set_title('Temperature vs Time', fontsize = 15)
            
            ymin,ymax = self.canvas.axes.get_ylim() # find range of displayed values
            xmin,xmax = self.canvas.axes.get_xlim()
            yrange = ymax-ymin
            xrange = xmax-xmin
            xpos = xmin + 1.0*xrange  # location for text annotation
            ypos = ymin + 1.01*yrange
            t = ax.text(xpos,ypos, timeString, style='italic', horizontalalignment='right')  # date,time string
            
            #bb = t.get_window_extent(renderer=r).transformed(matplotlib.pyplot.gca().transData.inverted())
            #width = bb.width
            
            totalPoints = len(self.dataLog)
            x2 = np.arange(totalPoints)
            x2 = x2 * setDur/samples
            self.canvas.ax2.cla()  # clear old data
            self.canvas.ax2.plot(x2, self.dataLog)   # plot of accumulated past data
            self.canvas.ax2.set_xlabel("seconds", fontsize = 10)
            self.canvas.ax2.set_ylabel("degrees C", fontsize = 10)
            self.canvas.ax2.grid(color='gray', linestyle='dotted')
            self.canvas.ax2.yaxis.set_major_formatter(fmt)
            self.canvas.draw()   # redraw plot on canvas       

# ---------------------------------------------------------------
app = QtWidgets.QApplication(sys.argv)
w = MainWindow()
app.exec_()

# w.fout.close()  # close the output file, now we're done
