# do not import anything else from loss_socket besides LossyUDP
from lossy_socket import LossyUDP
# do not import anything else from socket except INADDR_ANY
from socket import INADDR_ANY
from struct import *
from concurrent.futures import *
import time
from hashlib import *
from threading import Timer


class Streamer:
    def __init__(self, dst_ip, dst_port,
                 src_ip=INADDR_ANY, src_port=0):
        """Default values listen on all network interfaces, chooses a random source port,
           and does not introduce any simulated packet loss."""
        #self.lock = Lock()
        self.socket = LossyUDP()
        self.socket.bind((src_ip, src_port))
        self.dst_ip = dst_ip
        self.dst_port = dst_port
        self.closed = False
        #Buffers and Readers
        self.recvBuffer = []
        self.sendBuffer = []
        self.sCurrSeq = 0
        self.rCurrSeq = 0
        self.retData = b""
        self.ack = False
        self.thread = ThreadPoolExecutor(max_workers=1)
        self.thread.submit(self.listener)
        #Retransmit Trackers
        self.wOn = 0
        self.EarliestAck = 0
        self.sTimer = None
        self.ackTimer = 0
        #TeardownStuff
        self.tDownAck = False
        self.tDownReq = False
        self.tDownTimer = 0
        self.tDownForceTimer = None
    
    def sortHelp(self, tuple):
        return tuple[0]

    def calcCSum(self, packet):
        m = md5()
        m.update(packet)
        checksum = m.digest()
        checksum = checksum[0:8]
        #print(checksum)
        return checksum

    def sRetransmit(self):
        print("Retransmitting...")
        #print(self.sendBuffer)
        if (self.sendBuffer and not self.closed):
            for rPack in self.sendBuffer:
                self.socket.sendto(rPack, (self.dst_ip, self.dst_port))
            self.sTimer = Timer(0.25, self.sRetransmit)
            self.sTimer.start()

    def send(self, data_bytes: bytes) -> None:
        """Note that data_bytes can be larger than one packet."""
        # Your code goes here!  The code below should be changed!
        dataLeft = data_bytes
        datasize = len(data_bytes)
        while len(dataLeft) > 0:
            toSend = min(len(dataLeft), 1450)
            sendNow = dataLeft[0:toSend]
            packet = pack("ll??", self.sCurrSeq, datasize, False, False)
            chSend = packet + sendNow
            checksum = self.calcCSum(chSend)
            fpacket = packet + checksum + sendNow
            self.socket.sendto(fpacket, (self.dst_ip, self.dst_port))
            dataLeft = dataLeft[toSend:]
            self.sendBuffer.append(fpacket)
            self.sCurrSeq += 1
            self.ack = False
            if (self.wOn == 0):
                self.EarliestAck = 0
                self.sTimer = Timer(0.25, self.sRetransmit)
                self.sTimer.start()
            self.wOn += 1
            while self.wOn >= 15: 
                time.sleep(0.01)


    def recv(self) -> bytes:
        """Blocks (waits) if no data is ready to be read from the connection."""
        # your code goes here!  The code below should be changed!
        # this sample code just calls the recvfrom method on the LossySocket
        retData = b""
        #print(self.rCurrSeq)
        if (len(self.recvBuffer) > 0):
            self.recvBuffer = sorted(self.recvBuffer, key=self.sortHelp)
            extractedFList = []
            #print(self.recvBuffer)
            for i in self.recvBuffer:
                if (i[0][0] == self.rCurrSeq):
                    self.retData += i[2]
                    self.rCurrSeq += 1
                    extractedFList.append(i)
            for z in extractedFList:
                self.recvBuffer.remove(z)   
        returned = self.retData
        self.retData = b""
        return returned


    def tDownForce(self):
        print("TearDown Forced")
        self.tDownAck = True

    def listener(self):
        while not self.closed:
            #print("listening...")
            try:
                data, addr = self.socket.recvfrom()
                if (len(data) != 0):
                    pHeader = data[0:10]
                    pPayload = data[10:]
                    packet = (unpack("ll??", pHeader), pPayload[0:8], pPayload[8:],)
                    checksum = 0
                    recChecksu = packet[1]
                    chSend = pack("ll??", packet[0][0], packet[0][1], packet[0][2], packet[0][3]) + packet[2]
                    print("Header: ",  packet[0][0], packet[0][1], packet[0][2], packet[0][3]  ," Payload: ",  packet[2])
                    checksum = self.calcCSum(chSend)
                    if (checksum == recChecksu):
                        if (packet[0][2] and packet[0][0] > self.EarliestAck and not packet[0][3]): #Packet is an Ack and is Acknowledging a more recent packet
                            newEarliest = packet[0][0] - 1
                            packetsConfirmed = newEarliest - self.EarliestAck
                            for i in range(packetsConfirmed):
                                self.sendBuffer.pop(0)
                            self.wOn += -packetsConfirmed
                            self.EarliestAck = newEarliest
                            self.sTimer.cancel()
                            self.sTimer = Timer(0.25, self.sRetransmit)
                            self.sTimer.start()
                        elif (packet[0][2] and packet[0][3] and self.tDownReq): #Packet is a Teardown Ack
                            self.tDownAck = True
                        elif (not packet[0][2] and not packet[0][3]): #Packet is neither a teardown req nor an ACK -- its data
                            if (packet[0][0] >= self.rCurrSeq and packet not in self.recvBuffer): #If we don't already have it, save it
                                self.recvBuffer.append(packet)
                            if ((time.perf_counter() - self.ackTimer) > 0.10): #If we haven't acked recently, ack it.
                                self.ackTimer = time.perf_counter()
                                header = pack("ll??", self.rCurrSeq, 10, True, False)
                                chSend = header + b"  "
                                checksum = self.calcCSum(chSend)
                                fpacket = header + checksum + b"  "
                                self.socket.sendto(fpacket, (self.dst_ip, self.dst_port))
                        elif (packet[0][3] and self.tDownReq): #Packet is a Teardown Request and we are also in the process of tearing down; Send a Teardown Ack
                            header = pack("ll??", self.rCurrSeq, 10, True, True)
                            chSend = header + b"  "
                            checksum = self.calcCSum(chSend)
                            fpacket = header + checksum + b"  "
                            self.socket.sendto(fpacket, (self.dst_ip, self.dst_port))
                            self.tDownForceTimer = Timer(2.0, self.tDownForce)
                            self.tDownForceTimer.start()

            except Exception as e:
                print("listener died")
                print(e)


    def close(self) -> None:
        """Cleans up. It should block (wait) until the Streamer is done with all
           the necessary ACKs and retransmissions"""
        header = pack("ll??", self.rCurrSeq, 10, False, True)
        chSend = header + b"  "
        checksum = self.calcCSum(chSend)
        fpacket = header + checksum + b"  "
        self.socket.sendto(fpacket, (self.dst_ip, self.dst_port))
        self.tDownReq = True
        self.tDownTimer = time.perf_counter()
        while (not self.tDownAck):
            time.sleep(0.05)
            #print(self.tDownAck)
            now_time = time.perf_counter()
            if (now_time - self.tDownTimer > 0.20):
                    print("Retransmitting Teardown...")
                    self.socket.sendto(fpacket, (self.dst_ip, self.dst_port))
        self.closed = True
        self.sTimer.cancel()
        self.thread.shutdown()
        print("SUCCESSFULLY CLOSED")
        self.socket.stoprecv()
