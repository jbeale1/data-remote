#!/usr/bin/python3

# send local data to remote host via UDP network packets
# 18-Sep-2022 J.Beale

# example pipeline from local iio device:
#   sudo iio_readdev -u local: -b 256 -s 25000 -T 0 ad7124-8 voltage0-voltage1 | ./read3 | ./in-tx-udp.py

import socket
from threading import Thread
from time import sleep
import math     # for generating sine wave
import sys


exit = False
remote_host = "192.168.1.154" # JPB laptop
portNum = 8000  # an arbitrary choice of port number
packetSize = 20   # how many values to send at one time


points = 300  # how many data points in one wave
pi2 = 2 * 3.14159265358979323  #  2 * Pi
off = 0.0;  # phase offset #1
off2 = 0.0; # phase offset #2

def newValue(i):
        global off, off2

        x = i * (pi2 / points)
        off += 0.01;
        off2 += 0.001;
        y = math.sin(x) + 0.4 * math.sin((x+off)*3) + 0.2 * math.sin((x+off2)*2)
        outs = "{:.6f}".format(y) + "\n"  # float to string
        return outs       # return value as string

def main(args):
    global exit
    print("UDP Tx test")
    print("Press Ctrl+C to exit")
    print("")

    sleep(.1)

    #Generate a transmit socket object
    txSocket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)

    #Do not block when looking for received data (see above note)
    txSocket.setblocking(0)

    print("Transmitting to " + remote_host + ": " + str(portNum))
    while True:
    # for line in sys.stdin:  # get input from STDIN one line at a time

        try:
            txString = ""
            for j in range(packetSize):
                line = sys.stdin.readline()  # one line, includes newline
                txString += line

            # Transmit string as bytes to the local server on the agreed-upon port
            if (len(txString) > 0):
                txSocket.sendto(txString.encode(),(remote_host,portNum))
                print(".",end='',flush=True)

        except socket.error as msg:
            # If no data is received you end up here, but you can ignore
            # the error and continue
            pass
        except KeyboardInterrupt:
            exit = True
            print("Received Ctrl+C... initiating exit")
            break
        sleep(.02)

    return

if __name__=="__main__":
    main(sys.argv[1:0])
