# apply a 60 Hz notch filter to a signal in a .csv file
# and write it out to another .csv file

from scipy import signal
import matplotlib.pyplot as plt
import numpy as np

# input and output filenames
fin_name = "20221008_125340_log_1000.csv"
fout_name = "filt-out.csv"              # output data filename

samp_freq = 1044  # Assumed sample frequency (Hz)
notch_freq = 60.0  # Frequency to be removed from signal (Hz)
quality_factor = 30.0  # Quality factor (sharpness) of notch filter

# ----------------------------------------------------------------
# load in a signal from CSV file
def getData(fname):
     dat = np.loadtxt(fname, comments='#', skiprows=1)
     return dat

# calculate power spectrum and plot it
def plotPowerSpec(ydata, samp_freq, name):

     # find the power spectrum
     ps = 20*np.log10(np.abs(np.fft.rfft(ydata)))  # power spectrum of voltage time sequence
     ps[0] *= 0.1  # don't need that much DC response
     freq = np.linspace(0, samp_freq/2, len(ps))

     # plot the power spectrum
     fig,ax1 = plt.subplots()
     fig.canvas.set_window_title(name)
     ax1.plot(freq, ps)
     ax1.grid(color='gray', linestyle='dotted' )
     ax1.set_title(fin_name)  # title is name of data file
     ax1.set_ylabel('power, dB mV/rtHz')
     ax1.set_xlabel('frequency (Hz)')
     plt.show()

# ----------------------------------------------------------------
# read in a signal from .csv file
y_pure = getData(fin_name) 
points = len(y_pure)
t = np.linspace(0.0, (points/samp_freq), points)

# Create/view notch filter
b_notch, a_notch = signal.iirnotch(notch_freq, quality_factor, samp_freq)
freq, h = signal.freqz(b_notch, a_notch, fs = samp_freq)

# apply notch filter to signal to remove 60 Hz interference
y_notched = signal.filtfilt(b_notch, a_notch, y_pure)

fout = open(fout_name, "w")
fout.write("filtered\n")
np.savetxt(fout, y_notched, fmt='%0.5f')  # save out filtered signal to a file

plotPowerSpec(y_pure, samp_freq, "Raw Signal")     # show spectrum of original signal
plotPowerSpec(y_notched, samp_freq, "Filtered Signal")  # show spectrum of notch-filtered signal



