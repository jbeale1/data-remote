#!/usr/bin/python3

# send local data to remote host via UDP network packets
# 18-Sep-2022 J.Beale

# Older python2 version originally from
# http://sfriederichs.github.io/how-to/python/udp/2017/12/07/UDP-Communication.html

import socket
from threading import Thread
from time import sleep
import math     # for generating sine wave
import sys

exit = False
remote_host = "192.168.1.154" # JPB laptop
portNum = 8000  # an arbitrary choice of port number
packetSize = 10   # how many values to send at one time


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

    i = 0
    print("Transmitting to " + remote_host + ": " + str(portNum))
    while True:
        try:

            txString = ""
            for j in range(packetSize):
                txString += newValue(i)
                i += 1
                if (i >= points):
                    i = 0

            #Transmit string as bytes to the local server on the agreed-upon port
            txSocket.sendto(txString.encode(),(remote_host,portNum))
        except socket.error as msg:
            #If no data is received you end up here, but you can ignore
            #the error and continue
            pass
        except KeyboardInterrupt:
            exit = True
            print("Received Ctrl+C... initiating exit")
            break
        sleep(.2)

    return

if __name__=="__main__":
    main(sys.argv[1:0])
