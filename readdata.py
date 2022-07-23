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
# Modifications by Steve Erlenborn:
#   - Added many try ... except blocks to handle exceptions.
#   - Added GetDeviceType() method to identify the generation of the
#     Dexcom device. Returns 'g4', 'g5', 'g6', or the firmware version
#     number.
#   - Added a retry in Connect(). If the retry also fails, and the
#     OS is unix based, suggest steps to fix permission problems.
#   - Added ReadAllManufacturingData()
#   - Added USER_SETTING_DATA for G5 & G6.
#   - Added import of print_function
#
#########################################################################

# Support python3 print syntax in python2
from __future__ import print_function

import datetime
import sys
import time
import struct
import xml.etree.ElementTree as ET
from traceback import print_exc
import serial
import util
import crc16
import constants
import packetwriter
import database_records

# Some services are only to be invoked on unix-based OSs
if sys.platform == "linux" or sys.platform == "linux2" or sys.platform == "darwin":
    import grp
    import pwd
    import os

# xrange is replaced by range in python3
if sys.version_info.major > 2:
    xrange = range


class ReadPacket(object):

  def __init__(self, command, data):
    self._command = command
    self._data = data

  @property
  def command(self):
    return self._command

  @property
  def data(self):
    return self._data


class Dexcom(object):

  @staticmethod
  def FindDevice():
    try:
        return util.find_usbserial(constants.DEXCOM_USB_VENDOR,
                                   constants.DEXCOM_USB_PRODUCT)
    except NotImplementedError:
        print ('FindDevice() : Exception =', e)
        print_exc()
        if sys.version_info < (3, 0):
            sys.exc_clear()
        return None

  def GetDeviceType(self):
    try:
        device = self.FindDevice()
        if not device:
          sys.stderr.write('Could not find Dexcom Receiver!\n')
          return None
        else:
          fwh = self.GetFirmwareHeader()
          #print ('GetFirmwareHeader =', fwh)
          if fwh is None:
              return None
          fw_ver = fwh.get('FirmwareVersion')
          if fw_ver.startswith("2."):   # G4 firmware versions
              return 'g4'
          elif fw_ver.startswith("3."):
              return 'g4'
          elif fw_ver.startswith("4."):
              return 'g4'
          elif fw_ver.startswith("5.0."): # 5.0.1.043 = G5 Receiver Firmware
              return 'g5'
          elif fw_ver.startswith("5."):   # 5.1.1.022 = G6 Receiver Firmware
              return 'g6'
          else: # unrecognized firmware version
              return fw_ver
    except Exception as e:
        print ('GetDeviceType() : Exception =', e)
        print_exc()
        if sys.version_info < (3, 0):
            sys.exc_clear()
        return None

  @classmethod
  def LocateAndDownload(cls):
    device = cls.FindDevice()
    if not device:
      sys.stderr.write('Could not find Dexcom G4|G5|G6 Receiver!\n')
      sys.exit(1)
    else:
      dex = cls(device, dbg = True)
      # Uncomment two lines below to show the size of each record type
      #for item in dex.DataPartitions():
          #print (item.attrib)
      #print ('Ping =', dex.Ping())
      #print ('ReadClockMode =', dex.ReadClockMode())
      print ('Firmware.ProductId =', dex.GetFirmwareHeader().get('ProductId'))
      print ('Found %s S/N: %s'
             % (dex.GetFirmwareHeader().get('ProductName'),
                dex.ReadManufacturingData().get('SerialNumber')))
      print ('Transmitter paired: %s' % dex.ReadTransmitterId())
      print ('Battery Status: %s (%d%%)' % (dex.ReadBatteryState(),
                                            dex.ReadBatteryLevel()))
      print ('Record count:')
      print ('- Meter records: %d' % (len(dex.ReadRecords('METER_DATA'))))
      print ('- CGM records: %d' % (len(dex.ReadRecords('EGV_DATA'))))
      print ('- CGM commitable records: %d'
             % (len([not x.display_only for x in dex.ReadRecords('EGV_DATA')])))
      print ('- Event records: %d' % (len(dex.ReadRecords('USER_EVENT_DATA'))))
      print ('- Insertion records: %d' % (len(dex.ReadRecords('INSERTION_TIME'))))
      print ('- Calibration records: %d' % (len(dex.ReadRecords('CAL_SET'))))

      # Uncomment out any record types you want to display

      #print ('\nEGV_DATA\n======================================================')
      #print ('           +--------------+---------------+-------+---------------+----+----------+---+---+---+--------+------+')
      #print ('           |  systemTime  |  displayTime  | Gluc  |   meterTime   | ?  | testNum  |Rat|Arw| ? | RealGlu| crc  |')
      #print ('           +--------------+---------------+-------+---------------+----+----------+---+---+---+--------+------+')
      #maxrec = 100
      #for egv_rec in dex.ReadRecords('EGV_DATA'):
          #if sys.version_info.major > 2:
              #print ('raw_data =', ' '.join(' %02x' % c for c in egv_rec.raw_data))
          #else:
              #print ('raw_data =', ' '.join(' %02x' % ord(c) for c in egv_rec.raw_data))
          #maxrec -= 1
          #if maxrec <= 0:
              #break
      #print ('\nUSER_EVENT_DATA\n======================================================')
      #print ('           +--------------+---------------+----+---+--------------+---------------+--------+')
      #print ('           |  systemTime  |  displayTime  |Type|Sub|  eventTime   |    Value      |  crc   |')
      #print ('           +--------------+---------------+----+---+--------------+---------------+--------+')
      #maxrec = 100
      #for evt_rec in dex.ReadRecords('USER_EVENT_DATA'):
          #if sys.version_info.major > 2:
              #print ('raw_data =', ' '.join(' %02x' % c for c in evt_rec.raw_data))
          #else:
              #print ('raw_data =', ' '.join(' %02x' % ord(c) for c in evt_rec.raw_data))
          #maxrec -= 1
          #if maxrec <= 0:
              #break
      #print ('SENSOR_DATA\n======================================================')
      #print ('           +--------------+---------------+-------------+-------------+-----------+--------+')
      #print ('           |  systemTime  |  displayTime  | Unfiltered  |   Filtered  |  Rssi     |  crc   |')
      #print ('           +--------------+---------------+-------------+-------------+-----------+--------+')
      #for sen_rec in dex.ReadRecords('SENSOR_DATA'):
          #if sys.version_info.major > 2:
              #print ('raw_data =', ' '.join(' %02x' % c for c in sen_rec.raw_data))
          #else:
              #print ('raw_data =', ' '.join(' %02x' % ord(c) for c in sen_rec.raw_data))
      #print ('\nINSERTION_TIME\n======================================================')
      #print ('           +--------------+---------------+---------------+----+--------------+-----------------------+--------+')
      #print ('           |  systemTime  |  displayTime  | insertionTime |Stat|   unknown    |Transmitter Serial Num |  crc   |')
      #print ('           +--------------+---------------+---------------+----+--------------+-----------------------+--------+')
      #for ins_rec in dex.ReadRecords('INSERTION_TIME'):
          #if sys.version_info.major > 2:
              #print ('raw_data =', ' '.join(' %02x' % c for c in ins_rec.raw_data))
          #else:
              #print ('raw_data =', ' '.join(' %02x' % ord(c) for c in ins_rec.raw_data))
      #print ('\nMETER_DATA\n======================================================')
      #print ('           +--------------+---------------+-------+----+---------------+----------+---+--------+')
      #print ('           |  systemTime  |  displayTime  | Gluc  |Type|   meterTime   | testNum  |xx |  crc   |')
      #print ('           +--------------+---------------+-------+----+---------------+----------+---+--------+')
      #for met_rec in dex.ReadRecords('METER_DATA'):
          #if sys.version_info.major > 2:
              #print ('raw_data =', ' '.join(' %02x' % c for c in met_rec.raw_data))
          #else:
              #print ('raw_data =', ' '.join(' %02x' % ord(c) for c in met_rec.raw_data))
          #print ('            record_type =', met_rec.record_type, ', calib_gluc =', met_rec.calib_gluc, ', testNum =', met_rec.testNum, ' xx =', met_rec.xx)
      #print ('\nMANUFACTURING_DATA\n======================================================')
      #mfg_data = dex.ReadAllManufacturingData()
      #print ('char data =', mfg_data)

      # Not sure if the G4 has USER_SETTING_DATA, so we'll retrieve the
      # device type and restrict the following code to G5 or G6 cases.
      myDevType = dex.GetDeviceType()
      if myDevType is not None:
          if (myDevType == 'g5') or (myDevType == 'g6') :
              print ('- User Setting Records: %d' % (len(dex.ReadRecords('USER_SETTING_DATA'))))

              #################################################################################
              # Every time you modify any user configuration parameter, a new USER_SETTING_DATA
              # record gets generated, so there can be a large number of these.
              #################################################################################
              #print ('USER_SETTING_DATA\n======================================================')
              #for sen_rec in dex.ReadRecords('USER_SETTING_DATA'):
                  #if sys.version_info.major > 2:
                      #print ('raw_data =', ' '.join(' %02x' % c for c in sen_rec.raw_data))
                  #else:
                      #print ('raw_data =', ' '.join(' %02x' % ord(c) for c in sen_rec.raw_data))
                  #print ('transmitterPaired =', sen_rec.transmitterPaired)
                  #print ('highAlert =', sen_rec.highAlert)
                  #print ('highRepeat =', sen_rec.highRepeat)
                  #print ('lowAlert =', sen_rec.lowAlert)
                  #print ('lowRepeat =', sen_rec.lowRepeat)
                  #print ('riseRate =', sen_rec.riseRate)
                  #print ('fallRate =', sen_rec.fallRate)
                  #print ('outOfRangeAlert =', sen_rec.outOfRangeAlert)
                  #print ('soundsType =', sen_rec.soundsType)
                  #if myDevType == 'g6' :
                      #print ('urgentLowSoonRepeat =', sen_rec.urgentLowSoonRepeat)
                      #print ('sensorCode =', sen_rec.sensorCode)
                      #print ('')

  def __init__(self, port_path, port=None, dbg = False):
    self._port_name = port_path
    self._port = port
    self._debug_mode = dbg

  def Connect(self):
    try:
        if self._port is None:
            self._port = serial.Serial(port=self._port_name, baudrate=115200, timeout=4.3)
    except serial.SerialException as e:
        if sys.version_info < (3, 0):
            sys.exc_clear()
        try:
            if self._port is None:
                #print ('First attempt failed')
                if sys.platform == "linux" or sys.platform == "linux2" or sys.platform == "darwin":
                    # Trying to access the port file may help make it visible.
                    # For example, on Linux, running 'ls <self._port_name>' helps make
                    # a subsequent serial port access work.
                    try:
                        stat_info = os.stat(self._port_name)
                    except OSError as e:
                        if self._debug_mode:
                            print ('Connect() - os.stat() : Exception =', e)
                            print_exc()
                        if sys.version_info < (3, 0):
                            sys.exc_clear()
                time.sleep(18)
                self._port = serial.Serial(port=self._port_name, baudrate=115200, timeout=4.3)

        except serial.SerialException as e:
            if sys.version_info < (3, 0):
                sys.exc_clear()
            if self._debug_mode:
                print ('Connect() : Exception =', e)
            if sys.platform == "linux" or sys.platform == "linux2" or sys.platform == "darwin":
                stat_info = os.stat(self._port_name)
                port_gid = stat_info.st_gid
                port_group = grp.getgrgid(port_gid)[0]
                username = pwd.getpwuid(os.getuid())[0]
                # Check to see if the user is a member of the group we need
                userGroups = [grp.getgrgid(gid).gr_name for gid in os.getgroups()]
                if port_group not in userGroups:
                    print ('Read/Write permissions missing for', self._port_name)
                    print ('\nFor a persistent solution (recommended), run ...')
                    if sys.platform == "darwin":
                        print ('\n   sudo dseditgroup -o edit -a', username, '-t user', port_group)
                    else:
                        # On Mint, Ubuntu, etc.
                        print ('\n   sudo addgroup', username, port_group)
                        print ('\n   sudo -', username)
                        print ('\n         OR')
                        # On Fedora, Red Hat, etc.
                        print ('\n   sudo usermod -a -G', port_group, username)
                        print ('\n   su -', username)
                    print ('\nFor a short term solution, run ...')
                    print ('\n   sudo chmod 666', self._port_name, '\n')
    if self._port is not None:
        try:
            self.clear()
            #print ('Connect() : self.clear()')
        except Exception as e:
            if self._debug_mode:
                print ('Connect() - self.clear() : Exception =', e)
                print_exc()
            if sys.version_info < (3, 0):
                sys.exc_clear()

        try:
            self.flush()
            #print ('Connect() : self.flush()')
        except Exception as e:
            if self._debug_mode:
                print ('Connect() - self.flush() : Exception =', e)
                print_exc()
            if sys.version_info < (3, 0):
                sys.exc_clear()

  def Disconnect(self):
    if self._port is not None:
      # If the user disconnects the USB cable while in the middle
      # of a Write/Read operation, we can end up with junk in the
      # serial port buffers. After reconnecting the cable, this
      # junk can cause a lock-up on that port. So, clear and
      # flush the port during this Disconnect operation to prevent
      # a possible future lock-up. Note: the clear() and flush()
      # operations can throw exceptions when there is nothing to
      # be cleaned up, so we use try ... except to ignore those.
      try:
          self.clear()
      except Exception as e:
          #print ('Disconnect() : self.clear Exception =', e)
          if sys.version_info < (3, 0):
              sys.exc_clear()

      try:
          self.flush()
      except Exception as e:
          #print ('Disconnect() : self.flush Exception =', e)
          if sys.version_info < (3, 0):
              sys.exc_clear()
      self._port.close()
    self._port = None

  @property
  def port(self):
    if self._port is None:
      self.Connect()
    return self._port

  def write(self, *args, **kwargs):
    if self.port is not None:
        return self.port.write(*args, **kwargs)
    else:
        return 0

  def read(self, *args, **kwargs):
    if self.port is not None:
        return self.port.read(*args, **kwargs)
    else:
        return []

  def readpacket(self, timeout=None):
    total_read = 4
    initial_read = self.read(total_read)
    if initial_read != []:
        all_data = initial_read
        if ((sys.version_info.major > 2) and (initial_read[0] == 1)) or \
           ((sys.version_info.major <= 2) and ord(initial_read[0]) == 1):
          command = initial_read[3]
          data_number = struct.unpack('<H', initial_read[1:3])[0]
          if data_number > 6:
            toread = abs(data_number-6)
            second_read = self.read(toread)
            all_data += second_read
            total_read += toread
            out = second_read
          else:
            out =  ''
          suffix = self.read(2)
          if len(suffix) < 2:
              raise constants.Error('Packet header too short!')
          sent_crc = struct.unpack('<H', suffix)[0]
          local_crc = crc16.crc16(all_data, 0, total_read)
          if sent_crc != local_crc:
            raise constants.CrcError("readpacket Failed CRC check")
          return ReadPacket(command, out)
        else:
          raise constants.Error('Error reading packet header!')
    return None

  def Ping(self):
    self.WriteCommand(constants.PING)
    try:
        packet = self.readpacket()
    except Exception as e:
        if self._debug_mode:
            print ('Ping() Exception =', e)
            print_exc()
        if sys.version_info < (3, 0):
            sys.exc_clear()
        return None
    if sys.version_info.major > 2:
        return packet.command == constants.ACK
    else:
        return ord(packet.command) == constants.ACK

  def WritePacket(self, packet):
    if not packet:
      raise constants.Error('Need a packet to send')
    packetlen = len(packet)
    if packetlen < 6 or packetlen > 1590:
      raise constants.Error('Invalid packet length')
    self.flush()
    self.write(packet)

  def WriteCommand(self, command_id, *args, **kwargs):
    #if command_id in constants.COMMAND_STRINGS:
        #print ('WriteCommand(', constants.COMMAND_STRINGS[command_id], ') : args =', args, ', kwargs =', kwargs)
    #else:
        #print ('WriteCommand(', command_id, ') : args =', args, ', kwargs =', kwargs)
    p = packetwriter.PacketWriter()
    p.ComposePacket(command_id, *args, **kwargs)
    self.WritePacket(p.PacketBytes())

  def GenericReadCommand(self, command_id):
    try:
        self.WriteCommand(command_id)
        return self.readpacket()
    except (serial.SerialTimeoutException, serial.SerialException) as e:
        if self._debug_mode:
            if command_id in constants.COMMAND_STRINGS:
                print ('GenericReadCommand(', constants.COMMAND_STRINGS[command_id], ') : SerialException =', e)
            else:
                print ('GenericReadCommand(', command_id, ') : SerialException =', e)
            #print_exc()
        if sys.version_info < (3, 0):
            sys.exc_clear()
        return None
    except Exception as e:
        if self._debug_mode:
            if command_id in constants.COMMAND_STRINGS:
                print ('GenericReadCommand(', constants.COMMAND_STRINGS[command_id], ') Exception =', e)
            else:
                print ('GenericReadCommand(', command_id, ') Exception =', e)
            #print_exc()
        if sys.version_info < (3, 0):
            sys.exc_clear()
        return None

  def ReadTransmitterId(self):
    result = self.GenericReadCommand(constants.READ_TRANSMITTER_ID)
    if result is None:
        return None
    return result.data

  def ReadLanguage(self):
    result = self.GenericReadCommand(constants.READ_LANGUAGE)
    if result is None:
        return None
    lang = result.data
    return constants.LANGUAGES[struct.unpack('H', lang)[0]]

  def ReadBatteryLevel(self):
    result = self.GenericReadCommand(constants.READ_BATTERY_LEVEL)
    if result is None:
        return None
    level = result.data
    return struct.unpack('I', level)[0]

  def ReadBatteryState(self):
    result = self.GenericReadCommand(constants.READ_BATTERY_STATE)
    if result is None:
        return None
    state = result.data
    return constants.BATTERY_STATES[ord(state)]

  def ReadRTC(self):
    result = self.GenericReadCommand(constants.READ_RTC)
    if result is None:
        return None
    rtc = result.data
    return util.ReceiverTimeToTime(struct.unpack('I', rtc)[0])

  def ReadSystemTime(self):
    result = self.GenericReadCommand(constants.READ_SYSTEM_TIME)
    if result is None:
        return None
    rtc = result.data
    return util.ReceiverTimeToTime(struct.unpack('I', rtc)[0])

  def ReadSystemTimeOffset(self):
    result = self.GenericReadCommand(constants.READ_SYSTEM_TIME_OFFSET)
    if result is None:
        return None
    raw = result.data
    return datetime.timedelta(seconds=struct.unpack('i', raw)[0])

  def ReadDisplayTimeOffset(self):
    result = self.GenericReadCommand(constants.READ_DISPLAY_TIME_OFFSET)
    if result is None:
        return None
    raw = result.data
    return datetime.timedelta(seconds=struct.unpack('i', raw)[0])

  def WriteDisplayTimeOffset(self, offset=None):
    payload = struct.pack('i', offset)
    self.WriteCommand(constants.WRITE_DISPLAY_TIME_OFFSET, payload)
    try:
        packet = self.readpacket()
    except Exception as e:
        if self._debug_mode:
            print ('WriteDisplayTimeOffset() Exception =', e)
            print_exc()
        if sys.version_info < (3, 0):
            sys.exc_clear()
        return None
    return dict(ACK=ord(packet.command) == constants.ACK)


  def ReadDisplayTime(self):
    return self.ReadSystemTime() + self.ReadDisplayTimeOffset()

  def ReadGlucoseUnit(self):
    UNIT_TYPE = (None, 'mg/dL', 'mmol/L')
    result = self.GenericReadCommand(constants.READ_GLUCOSE_UNIT)
    if result is None:
        return None
    gu = result.data
    if sys.version_info.major > 2:
        return UNIT_TYPE[gu[0]]
    else:
        return UNIT_TYPE[ord(gu[0])]

  def ReadClockMode(self):
    CLOCK_MODE = (24, 12)
    result = self.GenericReadCommand(constants.READ_CLOCK_MODE)
    if result is None:
        return None
    cm = result.data
    if sys.version_info.major > 2:
        return CLOCK_MODE[cm[0]]
    else:
        return CLOCK_MODE[ord(cm[0])]

  def ReadDeviceMode(self):
    # ???
    result = self.GenericReadCommand(constants.READ_DEVICE_MODE)
    if result is None:
        return None
    return result.data

  def ReadBlindedMode(self):
    MODES = { 0: False }
    result = self.GenericReadCommand(constants.READ_BLINDED_MODE)
    if result is None:
        return None
    raw = result.data
    mode = MODES.get(bytearray(raw)[0], True)
    return mode

  def ReadHardwareBoardId(self):
    result = self.GenericReadCommand(constants.READ_HARDWARE_BOARD_ID)
    if result is None:
        return None
    return result.data

  def ReadEnableSetupWizardFlag (self):
    result = self.GenericReadCommand(constants.READ_ENABLE_SETUP_WIZARD_FLAG)
    if result is None:
        return None
    return result.data

  def ReadSetupWizardState (self):
    result = self.GenericReadCommand(constants.READ_SETUP_WIZARD_STATE)
    if result is None:
        return None
    return result.data

  def WriteChargerCurrentSetting (self, status):
    MAP = ( 'Off', 'Power100mA', 'Power500mA', 'PowerMax', 'PowerSuspended' )
    payload = str(bytearray([MAP.index(status)]))
    self.WriteCommand(constants.WRITE_CHARGER_CURRENT_SETTING, payload)
    try:
        packet = self.readpacket()
    except Exception as e:
        if self._debug_mode:
            print ('WriteChargerCurrentSetting() Exception =', e)
            print_exc()
        if sys.version_info < (3, 0):
            sys.exc_clear()
        return None
    if packet is None:
        return None
    raw = bytearray(packet.data)
    return dict(ACK=ord(packet.command) == constants.ACK, raw=list(raw))

  def ReadChargerCurrentSetting (self):
    MAP = ( 'Off', 'Power100mA', 'Power500mA', 'PowerMax', 'PowerSuspended' )
    result = self.GenericReadCommand(constants.READ_CHARGER_CURRENT_SETTING)
    if result is None:
        return None
    raw = bytearray(result.data)
    return MAP[raw[0]]


  # ManufacturingParameters: SerialNumber, HardwarePartNumber, HardwareRevision, DateTimeCreated, HardwareId
  def ReadManufacturingData(self):
    md = self.ReadRecords('MANUFACTURING_DATA')
    if md:
        #print ('ReadManufacturingData() : MANUFACTURING_DATA =', md[0].xmldata)
        data = md[0].xmldata
        return ET.fromstring(data)
    else:
        return None

  def ReadAllManufacturingData(self):
    data = self.ReadRecords('MANUFACTURING_DATA')[0].xmldata
    return data

  def flush(self):
    if self.port is not None:
        self.port.flush()

  def clear(self):
    if self.port is not None:
        self.port.flushInput()
        self.port.flushOutput()

  def GetFirmwareHeader(self):
    i = self.GenericReadCommand(constants.READ_FIRMWARE_HEADER)
    if i is None:
        return None
    return ET.fromstring(i.data)

  # FirmwareSettingsParameters: FirmwareImageId
  def GetFirmwareSettings(self):
    i = self.GenericReadCommand(constants.READ_FIRMWARE_SETTINGS)
    if i is None:
        return None
    return ET.fromstring(i.data)

  def DataPartitions(self):
    i = self.GenericReadCommand(constants.READ_DATABASE_PARTITION_INFO)
    if i is None:
        return None
    return ET.fromstring(i.data)

  def ReadDatabasePageRange(self, record_type):
    record_type_index = constants.RECORD_TYPES.index(record_type)
    self.WriteCommand(constants.READ_DATABASE_PAGE_RANGE,
                      chr(record_type_index))
    packet = self.readpacket()
    if packet is None:
        return []
    return struct.unpack('II', packet.data)

  def ReadDatabasePage(self, record_type, page):
    record_type_index = constants.RECORD_TYPES.index(record_type)
    self.WriteCommand(constants.READ_DATABASE_PAGES,
                      (chr(record_type_index), struct.pack('I', page), chr(1)))
    packet = self.readpacket()
    if packet is None:
        return []
    if sys.version_info.major > 2:
        assert packet.command == 1
    else:
        assert ord(packet.command) == 1
    # first index (uint), numrec (uint), record_type (byte), revision (byte),
    # page# (uint), r1 (uint), r2 (uint), r3 (uint), ushort (Crc)
    header_format = '<2IcB4IH'
    header_data_len = struct.calcsize(header_format)
    header = struct.unpack_from(header_format, packet.data)
    header_crc = crc16.crc16(packet.data[:header_data_len-2])
    assert header_crc == header[-1]
    assert ord(header[2]) == record_type_index
    assert header[4] == page
    packet_data = packet.data[header_data_len:]

    return self.ParsePage(header, packet_data)

  def GenericRecordYielder(self, header, data, record_type):
    for x in xrange(header[1]):
      yield record_type.Create(data, x)

  PARSER_MAP = {
      'USER_EVENT_DATA': database_records.EventRecord,
      'METER_DATA': database_records.MeterRecord,
      'CAL_SET': database_records.Calibration,
      'INSERTION_TIME': database_records.InsertionRecord,
      'EGV_DATA': database_records.EGVRecord,
      'SENSOR_DATA': database_records.SensorRecord,
  }

  def ParsePage(self, header, data):
    record_type = constants.RECORD_TYPES[ord(header[2])]
    revision = int(header[3])
    generic_parser_map = self.PARSER_MAP
    if revision > 4 and record_type == 'EGV_DATA':
      generic_parser_map.update(EGV_DATA=database_records.G6EGVRecord)
    if revision > 1 and record_type == 'INSERTION_TIME':
      generic_parser_map.update(INSERTION_TIME=database_records.G5InsertionRecord)
    if revision > 2 and record_type == 'METER_DATA':
      generic_parser_map.update(METER_DATA=database_records.G5MeterRecord)
    if revision < 2 and record_type == 'CAL_SET':
      generic_parser_map.update(CAL_SET=database_records.LegacyCalibration)
    xml_parsed = ['PC_SOFTWARE_PARAMETER', 'MANUFACTURING_DATA']
    if record_type in generic_parser_map:
      return self.GenericRecordYielder(header, data,
                                       generic_parser_map[record_type])
    elif record_type in xml_parsed:
      return [database_records.GenericXMLRecord.Create(data, 0)]
    else:
      raise NotImplementedError('Parsing of %s has not yet been implemented'
                                % record_type)

  def iter_records (self, record_type):
    assert record_type in constants.RECORD_TYPES
    page_range = self.ReadDatabasePageRange(record_type)
    start, end = page_range
    if start != end or not end:
      end += 1
    for x in reversed(xrange(start, end)):
      page_range = self.ReadDatabasePage(record_type, x)
      if page_range == []:
          break
      records = list(page_range)
      records.reverse( )
      for record in records:
        yield record
  
  def ReadRecords(self, record_type):
    records = []
    assert record_type in constants.RECORD_TYPES
    page_range = self.ReadDatabasePageRange(record_type)
    if page_range != []:
        start, end = page_range
        if start != end or not end:
          end += 1
        for x in range(start, end):
          page_range = self.ReadDatabasePage(record_type, x)
          if page_range == []:
              break
          records.extend(page_range)
    return records

class DexcomG5 (Dexcom):
  PARSER_MAP = {
      'USER_EVENT_DATA': database_records.EventRecord,
      'METER_DATA': database_records.G5MeterRecord,
      'CAL_SET': database_records.Calibration,
      'INSERTION_TIME': database_records.G5InsertionRecord,
      'EGV_DATA': database_records.G5EGVRecord,
      'SENSOR_DATA': database_records.SensorRecord,
      'USER_SETTING_DATA': database_records.G5UserSettings,
  }

class DexcomG6 (Dexcom):
  PARSER_MAP = {
      'USER_EVENT_DATA': database_records.EventRecord,
      'METER_DATA': database_records.G5MeterRecord,
      'CAL_SET': database_records.Calibration,
      'INSERTION_TIME': database_records.G5InsertionRecord,
      'EGV_DATA': database_records.G6EGVRecord,
      'SENSOR_DATA': database_records.SensorRecord,
      'USER_SETTING_DATA': database_records.G6UserSettings,
  }

def GetDevice (port):
  workInst = Dexcom(port)
  devType = workInst.GetDeviceType()  # g4 | g5 | g6
  if devType is None:
      return None
  if devType == 'g6':
    #print ('GetDevice() creating DexcomG6 class')
    return DexcomG6(port)
  elif devType == 'g5':
    #print ('GetDevice() creating DexcomG5 class')
    return DexcomG5(port)
  elif devType == 'g4':
    #print ('GetDevice() creating DexcomG4 class')
    return workInst
  else:
    print ('readdata.GetDevice() : Unrecognized firmware version', devType)
    return None

if __name__ == '__main__':
  dport = Dexcom.FindDevice()
  myDevice = GetDevice(dport)
  if myDevice:
      myDevice.LocateAndDownload()
