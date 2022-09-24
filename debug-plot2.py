#!/home/john/anaconda3/bin/python3

# Read AD7124 ADC chip and plot data, print stats
# J.Beale 24-Sep-2022

import adi
import matplotlib.pyplot as plt
import numpy as np
from struct import unpack
import sys
# import time
import datetime

rate = 100        # readings per second
#samples = 3010      # how many adc readings per batch
samples = 1004      # how many adc readings per batch

hardcoded_ip = "ip:analog.local" # Default to localhost if no argument given
my_ip = sys.argv[1] if len(sys.argv) >= 2 else hardcoded_ip

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

plt.ion()
fig = plt.figure()
ax = fig.add_subplot(111)
lastMean = 0
lastTime = datetime.datetime.now()
my_ad7124 = initADC(rate, samples)

# stdev: minus linear trend, stdev2: minus best-fit parabola
print("date, dT, n, avg, delta, slope, p2, stdev, stdev2")

while ( True ):
    data_raw = my_ad7124.rx()

    fmt = "%dI" % samples
    y = np.array( list(unpack(fmt, data_raw)) )
    x = np.arange(1,len(y)+1)
    slope,offset = np.polyfit(x, y, 1)  # find best-fit line
    base1 = np.poly1d((slope,offset))  # line in polynomial form
    y_d1 = y - base1(x)
    p2 = np.polyfit(x, y_d1, 2) # residual polynomial fit
    base2 = np.poly1d(p2)             # 2nd order curve fit
    y_d2 = y_d1 - base2(x)

    std = np.std(y_d1)
    std2 = np.std(y_d2)
    mean = np.mean(y)
    delta = mean - lastMean
    now = datetime.datetime.now()

    deltaT = (now - lastTime).total_seconds()
    
    print(now,end=", ")
    print("%.3f, %d, %.0f, %.0f, %.4f, %.3e, %.2f, %.2f" % 
          (deltaT, len(y), mean, delta, slope, p2[0], std, std2))
    lastMean = mean
    lastTime = now

    plt.cla()     # clear any previous data
    ax.scatter(x,y,s=2, color="green")  # show samples as points
    ax.plot(x, slope*x+offset, color="blue")    # linear best-fit as line
    ax.grid(color='gray', linestyle='dotted' )
    fig.canvas.draw()
    fig.canvas.flush_events()

del my_ad7124 # Clean up
