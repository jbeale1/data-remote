#!/usr/bin/python3

# UDP part based on
# http://sfriederichs.github.io/how-to/python/udp/2017/12/07/UDP-Communication.html

import socket                 # get UDP packets from network port
from threading import Thread  # multi-threaded
from time import sleep        # delay the right amount
import serial                 # send data to serial port
import sys

serPort = 'COM3'   # serial port to receive data from network

exit = False

def rxThread(portNum):
    global exit
    
    #Generate a UDP socket
    rxSocket = socket.socket(socket.AF_INET, #Internet
                             socket.SOCK_DGRAM) #UDP                             
    rxSocket.bind(("",portNum))
    #Prevent socket from blocking while receiving specified byte count   
    rxSocket.setblocking(0)

    s = serial.Serial(serPort, 115200, timeout=0.5) # serial port to receive data
    
    print("RX: Receiving data on UDP port " + str(portNum))
    print("")
    
    while not exit:
        try:
            data,addr = rxSocket.recvfrom(1024) # request this many bytes
            print(data.decode('UTF-8'))
            s.write(data)  # send received bytes out serial port

        except socket.error: # ignore error from no data
            pass
        except KeyboardInterrupt:
            exit = True
            break

        sleep(.01)

    s.close()  # now done with output serial port
       
    
def main(args):    
    global exit
    print("UDP Rx Example application")
    print("Press Ctrl+C to exit")
    print("")
    
    host = ""
    portNum = 8000  # an arbitrary choice of port number
   
    udpRxThreadHandle = Thread(target=rxThread,args=(portNum,))    
    udpRxThreadHandle.start()
        
    sleep(.1)
          
    while True:
        try:
            sleep(.2)
            
        except socket.error as msg:    
            #If no data is received you end up here, but you can ignore
            #the error and continue
            pass   
        except KeyboardInterrupt:
            exit = True
            print("Received Ctrl+C... initiating exit")
            break
        sleep(.1)
         
    udpRxThreadHandle.join()
        
    return

if __name__=="__main__":
    main(sys.argv[1:0])     
