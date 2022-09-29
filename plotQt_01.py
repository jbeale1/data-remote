# Initial try at acquiring data with Pyadi-iio
# and plotting with matplotlib under PyQt
# J.Beale 9/28/2022

import sys
import matplotlib
import adi         # Pyadi-iio interface to AD7124 ADC
import numpy as np # array manipulations
from struct import unpack  # extract words from packed binary buffer
import math     # for constant 'e'

matplotlib.use('Qt5Agg')

from PyQt5 import QtCore, QtGui, QtWidgets

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

# ----------------------------------------------------    
# Configure ADC settings

setDur = 8.0       # duration of 1 set in seconds
rate = 100        # readings per second
samples = int(setDur * rate) # record this many points at one time
R = 100            # decimation ratio: points averaged together before saving
adc1_ip = "ip:analog.local" # local LAN RPi with attached ADC

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
        fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = fig.add_subplot(111)
        super(MplCanvas, self).__init__(fig)


class MainWindow(QtWidgets.QMainWindow):

    def __init__(self, *args, **kwargs):
        super(MainWindow, self).__init__(*args, **kwargs)

        self.setWindowTitle("ADC Plot v0.1")
        width = 1000  # fixed width of window
        height = 700
        self.setFixedWidth(width)
        self.setFixedHeight(height)
        
        self.canvas = MplCanvas(self)
        self._adc1 = initADC(rate, samples)  # initialize ADC chip        

        self._plot_ref = None
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
        yr = np.array( list(unpack(fmt, data_raw)) )
        self.ydata = calcTemp(yr)  # convert raw readings into Temp, deg.C        

        if self._plot_ref is None:
            self.xdata = np.arange(1,len(self.ydata)+1)  # create a matching X axis

        self.canvas.axes.cla()  # clear old data
        self.canvas.axes.plot(self.xdata, self.ydata)
        self.canvas.axes.scatter(self.xdata,self.ydata,s=1, color="green")  # show samples as points
        self.canvas.axes.grid(color='gray', linestyle='dotted' )
        self.canvas.draw()   # redraw plot on canvas       

# ---------------------------------------------------------------
app = QtWidgets.QApplication(sys.argv)
w = MainWindow()
app.exec_()
