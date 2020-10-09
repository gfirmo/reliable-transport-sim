# do not import anything else from loss_socket besides LossyUDP
from lossy_socket import LossyUDP
# do not import anything else from socket except INADDR_ANY
from socket import INADDR_ANY
from struct import *


class Streamer:
    def __init__(self, dst_ip, dst_port,
                 src_ip=INADDR_ANY, src_port=0):
        """Default values listen on all network interfaces, chooses a random source port,
           and does not introduce any simulated packet loss."""
        self.socket = LossyUDP()
        self.socket.bind((src_ip, src_port))
        self.dst_ip = dst_ip
        self.dst_port = dst_port
        self.recvBuffer = []
        self.sCurrSeq = 0
        self.rCurrSeq = 0
        self.retData = b""
    
    def sortHelp(self, tuple):
        return tuple[0]
    def send(self, data_bytes: bytes) -> None:
        """Note that data_bytes can be larger than one packet."""
        # Your code goes here!  The code below should be changed!
        dataLeft = data_bytes
        datasize = len(data_bytes)
        while len(dataLeft) > 0:
            toSend = min(len(dataLeft), 1460)
            print(toSend)
            sendNow = dataLeft[0:toSend]
            #print(sendNow)
            packet = pack("ll", self.sCurrSeq, datasize) + sendNow
            #print(packet)
            self.socket.sendto(packet, (self.dst_ip, self.dst_port))
            #print(dataLeft)
            dataLeft = dataLeft[toSend:]
            #print(dataLeft)
            self.sCurrSeq += 1
        # for now I'm just sending the raw application-level data in one UDP payload

    def recv(self) -> bytes:
        """Blocks (waits) if no data is ready to be read from the connection."""
        # your code goes here!  The code below should be changed!
        # this sample code just calls the recvfrom method on the LossySocket
        #print("New Recv: ")
        #print ("currSeq: ", self.rCurrSeq)
        data, addr = self.socket.recvfrom()
        pHeader = data[0:8]
        pPayload = data[8:]
        packet = (unpack("ll", pHeader), pPayload)
        retData = b""
        print("Header: ", packet[0], " Payload: ", packet[1].decode())
        self.recvBuffer.append(packet)
        #print(len(self.recvBuffer))
        if (len(self.recvBuffer) > 0):
            self.recvBuffer = sorted(self.recvBuffer, key=self.sortHelp)
            extractedFList = []
            for i in self.recvBuffer:
                #print(i)
                if (i[0][0] == self.rCurrSeq):
                    self.retData += i[1]
                    self.rCurrSeq += 1
                    extractedFList.append(i)
            for z in extractedFList:
                self.recvBuffer.remove(z)   
        #print(self.recvBuffer)
        #print(self.retData.decode())
        returned = self.retData
        self.retData = b""
        return returned
        #if (len(self.retData) >= packet[1]):
        #    returned = self.retData
        #    self.retData = b""
        #    return returned
        #else:
        #    return b""
        # For now, I'll just pass the full UDP payload to the app
        

    def close(self) -> None:
        """Cleans up. It should block (wait) until the Streamer is done with all
           the necessary ACKs and retransmissions"""
        # your code goes here, especially after you add ACKs and retransmissions.
        pass
