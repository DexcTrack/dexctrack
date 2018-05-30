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

import datetime


class Error(Exception):
  """Base error for dexcom reader."""


class CrcError(Error):
  """Failed to CRC properly."""


DEXCOM_G4_USB_VENDOR = 0x22a3
DEXCOM_G4_USB_PRODUCT = 0x0047

BASE_TIME = datetime.datetime(2009, 1, 1)

NULL = 0
ACK = 1
NAK = 2
INVALID_COMMAND = 3
INVALID_PARAM = 4
INCOMPLETE_PACKET_RECEIVED = 5
RECEIVER_ERROR = 6
INVALID_MODE = 7
PING = 10
READ_FIRMWARE_HEADER = 11
READ_DATABASE_PARTITION_INFO = 15
READ_DATABASE_PAGE_RANGE = 16
READ_DATABASE_PAGES = 17
READ_DATABASE_PAGE_HEADER = 18
READ_TRANSMITTER_ID = 25
WRITE_TRANSMITTER_ID = 26
READ_LANGUAGE = 27
WRITE_LANGUAGE = 28
READ_DISPLAY_TIME_OFFSET = 29
WRITE_DISPLAY_TIME_OFFSET = 30
READ_RTC = 31
RESET_RECEIVER = 32
READ_BATTERY_LEVEL = 33
READ_SYSTEM_TIME = 34
READ_SYSTEM_TIME_OFFSET = 35
WRITE_SYSTEM_TIME = 36
READ_GLUCOSE_UNIT = 37
WRITE_GLUCOSE_UNIT = 38
READ_BLINDED_MODE = 39
WRITE_BLINDED_MODE = 40
READ_CLOCK_MODE = 41
WRITE_CLOCK_MODE = 42
READ_DEVICE_MODE = 43
ERASE_DATABASE = 45
SHUTDOWN_RECEIVER = 46
WRITE_PC_PARAMETERS = 47
READ_BATTERY_STATE = 48
READ_HARDWARE_BOARD_ID = 49
READ_FIRMWARE_SETTINGS = 54
READ_ENABLE_SETUP_WIZARD_FLAG = 55
READ_SETUP_WIZARD_STATE = 57
READ_CHARGER_CURRENT_SETTING = 59
WRITE_CHARGER_CURRENT_SETTING = 60
MAX_COMMAND = 61
MAX_POSSIBLE_COMMAND = 255

EGV_VALUE_MASK = 1023
EGV_DISPLAY_ONLY_MASK = 32768
EGV_TREND_ARROW_MASK = 15

BATTERY_STATES = [None, 'CHARGING', 'NOT_CHARGING', 'NTC_FAULT', 'BAD_BATTERY']

RECORD_TYPES = [
  'MANUFACTURING_DATA', 'FIRMWARE_PARAMETER_DATA', 'PC_SOFTWARE_PARAMETER',
  'SENSOR_DATA', 'EGV_DATA', 'CAL_SET', 'DEVIATION', 'INSERTION_TIME',
  'RECEIVER_LOG_DATA', 'RECEIVER_ERROR_DATA', 'METER_DATA', 'USER_EVENT_DATA',
  'USER_SETTING_DATA', 'MAX_VALUE',
]

TREND_ARROW_VALUES = [None, 'DOUBLE_UP', 'SINGLE_UP', '45_UP', 'FLAT',
                      '45_DOWN', 'SINGLE_DOWN', 'DOUBLE_DOWN', 'NOT_COMPUTABLE',
                      'OUT_OF_RANGE']

SPECIAL_GLUCOSE_VALUES = {0: None,
                          1: 'SENSOR_NOT_ACTIVE',
                          2: 'MINIMAL_DEVIATION',
                          3: 'NO_ANTENNA',
                          5: 'SENSOR_NOT_CALIBRATED',
                          6: 'COUNTS_DEVIATION',
                          9: 'ABSOLUTE_DEVIATION',
                          10: 'POWER_DEVIATION',
                          12: 'BAD_RF'}


LANGUAGES = {
  0: None,
  1033: 'ENGLISH',
}


