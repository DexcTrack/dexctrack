#########################################################################
# This source file is from the openaps/dexcom_reader project. 
#
#    https://github.com/openaps/dexcom_reader
#
# It is under an MIT licence described in the 3 paragraphs below:
#
#########################################################################
#
#    Permission is hereby granted, free of charge, to any person obtaining a
#    copy of this software and associated documentation files (the "Software"),
#    to deal in the Software without restriction, including without limitation
#    the rights to use, copy, modify, merge, publish, distribute, sublicense,
#    and/or sell copies of the Software, and to permit persons to whom the
#    Software is furnished to do so, subject to the following conditions:
#
#    The above copyright notice and this permission notice shall be included
#    in all copies or substantial portions of the Software.
#
#    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
#    OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
#    THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR
#    OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
#    ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
#    OTHER DEALINGS IN THE SOFTWARE.
#
#########################################################################
#
# The original file has been modified by Steve Erlenborn to provide a
# Python 3 version of the PacketWriter class.
#
#########################################################################

import crc16
import struct
import sys

if sys.version_info.major > 2:

    #######################
    # For python3 or newer
    #######################

    class PacketWriter(object):
      MAX_PAYLOAD = 1584
      MIN_LEN = 6
      MAX_LEN = 1590
      SOF = 0x01
      OFFSET_SOF = 0
      OFFSET_LENGTH = 1
      OFFSET_CMD = 3
      OFFSET_PAYLOAD = 4

      def __init__(self):
        self._packet = None

      def Clear(self):
        self._packet = None

      def PacketBytes(self):
        return self._packet

      def ComposePacket(self, command, payload=None):
        assert self._packet is None
        self._packet =  bytearray(b"\x01")  # OFFSET_SOF
        self._packet += b"\x00"             # OFFSET_LENGTH
        self._packet += b"\x00"
        self._packet += command.to_bytes(1, byteorder='little', signed=False)   # OFFSET_CMD
        if payload and len(payload):
          for xx in payload:
              if type(xx) == str:
                  data = bytes(xx, 'utf8')
              elif type(xx) == bytes:
                  data = xx
              elif type(xx) == bytearray:
                  data = bytes(xx)
              elif type(xx) == int:
                  data = xx.to_bytes(4, byteorder='little', signed=False)
              else:
                  print ('ComposePacket : unknown type =', type(xx))
                  raise NotImplementedError

              self._packet += data

        # Set the length
        theLength = len(self._packet) + 2
        self._packet[self.OFFSET_LENGTH]   = theLength & 0xff
        self._packet[self.OFFSET_LENGTH+1] = (theLength >> 8) & 0xff
        # Append the CRC
        crc = crc16.crc16(self._packet, 0, len(self._packet))
        self._packet += crc.to_bytes(2, byteorder='little', signed=False)
        #print ('ComposePacket : final packet =', self._packet.hex())

else:

    #######################
    # For python2
    #######################

    class PacketWriter(object):
      MAX_PAYLOAD = 1584
      MIN_LEN = 6
      MAX_LEN = 1590
      SOF = 0x01
      OFFSET_SOF = 0
      OFFSET_LENGTH = 1
      OFFSET_CMD = 3
      OFFSET_PAYLOAD = 4

      def __init__(self):
            self._packet = None

      def Clear(self):
            self._packet = None

      def NewSOF(self, v):
            self._packet[0] = chr(v)

      def PacketBytes(self):
          return ''.join(self._packet)

      def AppendCrc(self):
        self.SetLength()
        ps = self.PacketBytes()
        crc = crc16.crc16(ps, 0, len(ps))
        for x in struct.pack('H', crc):
          self._packet.append(x)

      def SetLength(self):
        self._packet[1] = chr(len(self._packet) + 2)

      def _Add(self, x):
        try:
          len(x)
          for y in x:
            self._Add(y)
        except:
          self._packet.append(x)

      def ComposePacket(self, command, payload=None):
        assert self._packet is None
        self._packet = [b"\x01", None, b"\x00", chr(command)]
        if payload:
          self._Add(payload)
        self.AppendCrc()
        #print ('ComposePacket : final packet =', ' '.join(x.encode('hex') for x in self._packet))

