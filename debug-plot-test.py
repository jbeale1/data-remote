#!/usr/bin/python

# NOTE: this uses a non-standard, debug-test version of the Pyadi-iio function
#   /usr/local/lib/python3.9/dist-packages/adi/rx_tx.py

import adi
import matplotlib.pyplot as plt
import numpy as np
from struct import unpack
import sys
import time

rate = 1000        # readings per second
samples = 500    # how many ADC readings at a time

hardcoded_ip = "ip:localhost" # Default to localhost if no argument given
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
my_ad7124._ctx.set_timeout(100000)

plt.ion()
fig = plt.figure()
ax = fig.add_subplot(111)

while ( True ):
    data_raw = my_ad7124.rx()
    fmt = "%dI" % samples
    data = list( unpack(fmt, data_raw) ) 

    plt.cla()     # clear any previous data
    line1, = ax.plot(data)
    fig.canvas.draw()
    fig.canvas.flush_events()

del my_ad7124 # Clean up
