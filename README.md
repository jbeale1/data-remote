# data-remote

Transfer readings from local 'iio' device through UDP packets to remote host, which can then use "SerialPlot" 
as if the data source was a locally-attached serial device.

Example pipeline:

  iio_readdev -u "ip:localhost" -b 256 -s 1000 -T 0 ad7124-8 voltage0-voltage1 | adi_bin2csv | findRMS
  
Example video:
https://www.youtube.com/watch?v=nQR6z1zPdEM

![ADC plot screenshot](https://github.com/jbeale1/data-remote/blob/main/ADC-Plot-v014.png)
