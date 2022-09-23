#!/usr/bin/python3

import adi
import matplotlib.pyplot as plt
import numpy as np
from struct import unpack
import sys
import time

rate = 2000        # readings per second
samples = 20002    # how many ADC readings at a time

hardcoded_ip = "ip:analog.local" # Default to localhost if no argument given

my_ip = sys.argv[1] if len(sys.argv) >= 2 else hardcoded_ip

my_ad7124 = adi.ad7124(uri=my_ip)
ad_channel = 0

sc = my_ad7124.scale_available
my_ad7124.channel[ad_channel].scale = sc[-1]  # get highest range
scale = my_ad7124.channel[ad_channel].scale
#my_ad7124.rx_output_type = "SI"

my_ad7124.sample_rate = rate  # sets sample rate for all channels
my_ad7124.rx_enabled_channels = [ad_channel]
my_ad7124.rx_buffer_size = samples
my_ad7124._ctx.set_timeout(1000000)

plt.ion()
fig = plt.figure()
ax = fig.add_subplot(111)
lastMean = 0

while ( True ):
    data_raw = my_ad7124.rx()
    fmt = "%dI" % samples
    y = np.array( list(unpack(fmt, data_raw)) )
    x = np.arange(1,len(y)+1)
    a,b = np.polyfit(x, y, 1)  # find best-fit line
    baseline = np.poly1d((a,b))  # line in polynomial form
    y_notrend = y - baseline(x)
    std = np.std(y_notrend)
    mean = np.mean(y)
    delta = mean - lastMean
    print("n: %d avg: %.0f delta: %.0f slope: %.3f stdev: %.2f" % (len(y), mean/100.0, delta, a, std))
    lastMean = mean

    plt.cla()     # clear any previous data
    ax.scatter(x,y,s=2, color="green")  # show samples as points
    ax.plot(x, a*x+b, color="blue")    # linear best-fit as line
    ax.grid(color='gray', linestyle='dotted' )
    fig.canvas.draw()
    fig.canvas.flush_events()

del my_ad7124 # Clean up
