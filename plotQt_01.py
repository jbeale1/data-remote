# Initial try at acquiring data with Pyadi-iio
# and plotting with matplotlib under PyQt
# J.Beale 9/28/2022

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
datfile = "tdat.csv"        # use this file to save ADC readings 

setDur = 8.0       # duration of 1 dataset, in seconds
rate = 100         # readings per second

samples = int(setDur * rate) # record this many points at one time
R = 100            # decimation ratio: points averaged together before saving

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
        
        self.fout = open(datfile, "w")       # erase pre-existing file if any
        self.fout.write("Temperature\n")     # column header, to read as CSV
        now = datetime.datetime.now()
        timeString = now.strftime('%Y-%m-%d %H:%M:%S')
        self.fout.write("# Start: %s\n" % timeString)
        

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
        #self.fout = open(datfile, "a")  # append each batch of readings

        self.update_plot()
        self.show()              
        
        # set up GUI layout
        btnLayout = QtWidgets.QHBoxLayout()  # a horizontal bar of button controls
        btnLayout.addWidget(QtWidgets.QPushButton('Start'))
        btnLayout.addWidget(QtWidgets.QPushButton('Pause'))        
        btnLayout.addWidget(QtWidgets.QPushButton('Record'))        
        btnLayout.addWidget(QtWidgets.QPushButton('Reset Plot'))

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
        
    def update_plot(self):        
        data_raw = self._adc1.rx()
        fmt = "%dI" % samples
        now = datetime.datetime.now()
        timeString = now.strftime('%Y-%m-%d %H:%M:%S')

        yr = np.array( list(unpack(fmt, data_raw)) )
        self.ydata = calcTemp(yr)  # convert raw readings into Temp, deg.C  
        self.dataLog = np.append(self.dataLog, self.ydata)  # save data in array   

        # save out downsampled version of data to a file on disk
        yD = self.ydata.reshape(-1, R).mean(axis=1) # average each set of R values
        # print("%+0.5f" % yD[0])
        np.savetxt(self.fout, yD, fmt='%+0.5f')  # save out readings to disk
        self.fout.write("# %s\n" % timeString)   # write out timestamp
        self.fout.flush()  # update file on disk

        if self._plot_ref is None:
            self.xdata = np.arange(1,len(self.ydata)+1)  # create a matching X axis        

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

w.fout.close()  # close the output file, now we're done
