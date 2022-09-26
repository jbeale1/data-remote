#!/home/john/anaconda3/bin/python3

# Measure thermistor with AD7124 ADC chip
# record and plot data, curve fit, stats
# J.Beale 26-Sep-2022

import adi
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
from struct import unpack
import sys
import datetime
import csv      # write data to CSV file
import math     # for constant 'e'

setDur = 2.0       # duration of 1 set in seconds
rate = 1000        # readings per second
samples = int(setDur * rate) # record this many points at one time
R = 100            # decimation ratio: points averaged together before saving

datfile = "tdat.csv"  # save ADC readings
my_ip = "ip:analog.local" # local RPi with ADC

figW = 12          # matplotlib plot size, inches
figH = figW * 12/16 # height in inches

# ----------------------------------------------------    
# set up ADC chip through Pyadi-iio system

def initADC(rate, samples):
  my_ad7124 = adi.ad7124(uri=my_ip)
  ad_channel = 0
  sc = my_ad7124.scale_available
  my_ad7124.channel[ad_channel].scale = sc[-1]  # get highest range
  scale = my_ad7124.channel[ad_channel].scale
  my_ad7124.sample_rate = rate  # sets sample rate for all channels
  my_ad7124.rx_buffer_size = samples
  my_ad7124.rx_enabled_channels = [ad_channel]
  my_ad7124._ctx.set_timeout(1000000)
  return my_ad7124

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
plt.ion()
#fig = plt.figure()
fig, (ax, ax2) = plt.subplots(2, 1)
fig.set_size_inches(figW, figH)
# ax = fig.add_subplot(111)
lastMean = 0
lastTime = datetime.datetime.now()
dataLog = np.array([])  # log for sub-sampled data

my_ad7124 = initADC(rate, samples)

# do the first run but ignore it, due to RC start transient
data_raw = my_ad7124.rx()  

fout = open(datfile, "w")    # erase pre-existing file if any
fout.write("Temperature\n")  # column header, to read as CSV
fout.close

with open(datfile, "a") as fout:  # append each batch of readings
  datwriter = csv.writer(fout)

  # stdev: RMS power of (data - linear trend)
  # r12: (2nd-order + higher-order RMS) / (higher-order RMS)
  print("date, dT, degC, dT(mC), mC/s, p2, stdev, r12")

  frameNum = 0
  while ( True ):
    data_raw = my_ad7124.rx()
    frameNum += 1

    fmt = "%dI" % samples
    yr = np.array( list(unpack(fmt, data_raw)) )
    y = calcTemp(yr)  # convert raw readings into Temp, deg.C
    totalDur = frameNum * setDur  # total seconds recorded so far
    
    # save out downsampled version of data to a file on disk
    yD = y.reshape(-1, R).mean(axis=1) # average each set of R values
    np.savetxt(fout, yD, fmt='%0.5f')  # save out readings to disk
    fout.flush()  # update file on disk
    dataLog = np.append(dataLog, yD)  # save data in array
        
    x = np.arange(1,len(y)+1)
    slope,offset = np.polyfit(x, y, 1)  # find best-fit line
    base1 = np.poly1d((slope,offset))  # line in polynomial form
    y_d1 = y - base1(x)
    p2 = np.polyfit(x, y_d1, 2) # residual polynomial fit
    base2 = np.poly1d(p2)             # 2nd order curve fit
    y_d2 = y_d1 - base2(x)

    std1 = np.std(y_d1)  # standard dev. of de-trended data
    std2 = np.std(y_d2)  # std after 2nd-order curve fit
    r12 = std1 / std2    # ratio measures non-linearity
    cRate = r12 - 1.0  # rate that things are changing
    mean = np.mean(y)
    delta = mean - lastMean
    now = datetime.datetime.now()
    timeString = now.strftime('%Y-%m-%d %H:%M:%S')
    srString = "Change: %.4f" % cRate
    datString = ("Temp vs Time      T: %.3f°C   dT: %.2f mC/s   d2T:%.3f" %
        (mean, slope*rate*1E3, p2[0]*rate*rate*1E5) )
    dtString = ("%.2f" % (slope*rate*1E3))
    deltaT = (now - lastTime).total_seconds()
    
    #print("%s, %.3f, %.4f, %.1f, %.4f, %.3f, %.2f, %.4f" % 
    #      (timeString, deltaT, mean, delta*1E3, slope*rate*1E3, 
    #      p2[0]*rate*rate*1E5, std1*1E3, cRate))
    lastMean = mean
    lastTime = now

    # ---- display graph of data, trend, curve fit
    #plt.cla()     # clear any previous data (worked with 1 plot only)
    ax.clear()      # clear entire first plot
    ax2.clear()
    ax.scatter(x,y,s=1, color="green")  # show samples as points
    ax.plot(x, (base1(x) + base2(x)), color="red")    # quadratic best-fit as curve
    #ax.plot(x, slope*x+offset, color="blue")    # linear best-fit as line
    ax.plot(x, base1(x), color="blue")    # linear best-fit as line
    ax.grid(color='gray', linestyle='dotted' )
    #ax.set_title('Temp vs Time (5 sec)', fontsize = 15)
    xLabelString = ("sample # (%d sps)" % (rate))
    ax.set_xlabel(xLabelString, fontsize = 12)
    ax.set_ylabel('Temperature (C)', fontsize=12)
    fmt=ticker.ScalarFormatter(useOffset=False)
    fmt.set_scientific(False)  
    ax.yaxis.set_major_formatter(fmt)
    
    ymin,ymax = ax.get_ylim() # find range of displayed values
    xmin,xmax = ax.get_xlim()
    yrange = ymax-ymin
    xrange = xmax-xmin
    xpos = xmin + 0.85*xrange
    xpos3 = xmin + 0.15*xrange
    ypos = ymin + 1.01*yrange
    ypos2 = ymin + 0.9*yrange     # was 0.95
    xpos4 = xmin + 0.5*xrange
    ypos4 = ymin + 0.03*yrange

    x2 = np.arange(0,totalDur,totalDur/len(dataLog))
    ax2.plot(x2, dataLog)   # plot of past data
    ax2.set_xlabel("seconds", fontsize = 12)
    ax2.grid(color='gray', linestyle='dotted' )
    # print(frameNum, len(dataLog))
    
    ax.text(xpos,ypos, timeString, style='italic')
    ax.text(xpos,ypos2, srString, fontsize=11, bbox={'facecolor': 'white', 'pad': 5})
    ax.text(xpos3,ypos, datString, fontsize=15)
    ax.text(xpos4,ypos4, dtString, fontsize=110, color="grey", fontweight="bold", alpha=0.1)
    fig.canvas.draw()
    fig.canvas.flush_events()
    #outname = "%05d.png" % frameNum  # save out screen image
    #fig.savefig(outname)

    
  del my_ad7124 # Clean up
