# apply a 60 Hz notch filter to a signal in a .csv file
# and write it out to another .csv file

from scipy import signal
import matplotlib.pyplot as plt
import numpy as np

fname = "20221008_110259_log_1000.csv"  # input data filename
fout_name = "filt-out.csv"              # output data filename


# load in a signal from CSV file

def getData(fname):
     dat = np.loadtxt(fname, comments='#', skiprows=1)
     return dat


# Create/view notch filter
samp_freq = 1044  # Sample frequency (Hz)
notch_freq = 60.0  # Frequency to be removed from signal (Hz)
quality_factor = 30.0  # Quality factor

b_notch, a_notch = signal.iirnotch(notch_freq, quality_factor, samp_freq)
freq, h = signal.freqz(b_notch, a_notch, fs = samp_freq)
plt.figure('filter')
plt.plot( freq, 20*np.log10(abs(h)))
plt.show()


y_pure = getData(fname)  # get signal from file
points = len(y_pure)
t = np.linspace(0.0, (points/samp_freq), points)

# apply notch filter to signal
y_notched = signal.filtfilt(b_notch, a_notch, y_pure)

fout = open(fout_name, "w")
fout.write("filtered\n")
np.savetxt(fout, y_notched, fmt='%0.5f')  # save out filtered signal to a file

# plot notch-filtered version of signal
plt.figure('result')
plt.subplot(211)
plt.plot(t, y_pure, color = 'r')

plt.subplot(212)
plt.plot(t, y_notched, color = 'r')
plt.show()

