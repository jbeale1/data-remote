# data-remote

Transfer readings from local 'iio' device through UDP packets to remote host, which can then use "SerialPlot" 
as if the data source was a locally-attached serial device.

Example pipeline:
  sudo iio_readdev -u local: -b 256 -s 25000 -T 0 ad7124-8 voltage0-voltage1 | ./read3 | ./in-tx-udp.py
