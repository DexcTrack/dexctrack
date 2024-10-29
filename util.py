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
#   The thisIsWine() function has been added. The find_usbserial()
# routine has been greatly simplified, eliminating the need for
# linux_find_usbserial() and osx_find_usbserial(). The updates make
# this file usable under both python2.7.* and python3.*.
#
#########################################################################

# Support python3 print syntax in python2
from __future__ import print_function

import constants
import datetime
import platform
import sys
import serial.tools.list_ports

if sys.platform == 'win32':
    if sys.version_info < (3, 0):
        from _winreg import *
    else:
        from winreg import *


def ReceiverTimeToTime(rtime):
  return constants.BASE_TIME + datetime.timedelta(seconds=rtime)

def thisIsWine():
    if sys.platform == 'win32':
        try:
            registry = ConnectRegistry(None, HKEY_LOCAL_MACHINE)
            if registry is not None:
                try:
                    winekey = OpenKey(registry, 'Software\\Wine')
                    if winekey is not None:
                        return True
                    else:
                        return False
                except OSError as e:
                    #print ('OpenKey failed. Exception =', e)
                    if sys.version_info < (3, 0):
                        sys.exc_clear()
                    return False
            else:
                return False

        except OSError as f:
            #print ('ConnectRegistry failed. Exception =', f)
            if sys.version_info < (3, 0):
                sys.exc_clear()
            return False
    else:
        return False

def find_usbserial(vendor, product):
    """Find the tty device for a given usbserial devices identifiers.

    Args:
       vendor: (int) something like 0x0000
       product: (int) something like 0x0000

    Returns:
       String, like /dev/ttyACM0 or /dev/tty.usb...
    """
    if platform.system() == 'Linux':
        pass
    elif platform.system() == 'Darwin':
        pass
    elif platform.system() == 'Windows':
        if thisIsWine():
            # When running under WINE, we have no access to real USB information, such
            # as the Vendor & Product ID values. Also, serial.tools.list_ports.comports()
            # returns nothing. The real port under Linux (or OSX?) is mapped to a windows
            # serial port at \dosdevices\COMxx, but we don't know which one. Normally,
            # COM1 - COM32 are automatically mapped to /dev/ttyS0 - /dev/ttyS31.
            # If the Dexcom device is plugged in, it will be mapped to COM33 or greater.
            # We have no way of identifying which port >= COM33 is the right one, so
            # we'll just guess the first available one.
            return "\\\\.\\com33"
        else:
            pass
    else:
        raise NotImplementedError('Cannot find serial ports on %s' % platform.system())

    # Linux, OSX, or non-Wine Windows
    for cport in serial.tools.list_ports.comports():
        if (cport.vid == vendor) and (cport.pid == product):
            if cport.device is not None:
              return cport.device
    return None
