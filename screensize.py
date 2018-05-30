#!/usr/bin/python

# This file provides a function to retrieve the screen size, with
# different implementations for different backends.
#
# License: Creative Commons CC-BY-SA
#          https://creativecommons.org/licenses/by-sa/4.0/
#
#

import sys
import matplotlib.pyplot as plt

def get_screen_size():
    """This function finds the width and height of the screen. This will be
    for a single monitor in a multi-monitor set-up.

    Args:
        None

    Returns:
        A list of numbers (width-in-pixels, height-in-pixels)
    """
    backend = plt.get_backend()


    if 'GTK' in backend:
        # Implementation by starfry at
        # https://stackoverflow.com/questions/3129322/how-do-i-get-monitor-resolution-in-python
        import gtk
        window = gtk.Window()
        # the screen contains all monitors
        screen = window.get_screen()
        # collect data about active monitor
        curmon = screen.get_monitor_at_window(screen.get_active_window())
        dx, dy, width, height = screen.get_monitor_geometry(curmon)  # get geometry of current monitor

    elif 'Tk' in backend:
        # Modified version of implementation by FogleBird at
        # https://stackoverflow.com/questions/8762536/how-can-i-choose-the-default-wx-display-in-wxpython
        import wx
        MyApp = wx.App(False)   # the wx.App object must be created first.
        display = wx.Display(0) # find the size of the first display screen
        dx, dy, width, height = display.GetGeometry()

    elif 'MacOSX' in backend:
        # Implementation by Mike Rhodes at
        # https://stackoverflow.com/questions/1281397/how-to-get-the-desktop-resolution-in-mac-via-python
        from Quartz import CGDisplayBounds
        from Quartz import CGMainDisplayID
        from Quartz import CGDisplayScreenSize
        mainMonitor = CGDisplayBounds(CGMainDisplayID())
        width = mainMonitor.size.width
        height = mainMonitor.size.height
        sizeInMm = CGDisplayScreenSize(CGMainDisplayID())
        pixels2inches = width * 25.4 / sizeInMm.width   # 25.4 mm = 1 inch

    elif 'WX' in backend:
        # Implementation by Justin at
        # https://stackoverflow.com/questions/3129322/how-do-i-get-monitor-resolution-in-python
        import ctypes
        user32 = ctypes.windll.user32
        user32.SetProcessDPIAware()
        width = user32.GetSystemMetrics(0)
        height = user32.GetSystemMetrics(1)

    elif 'Qt4' in backend:
        # NOT TESTED YET. Implementation by Harsh Kumar Narula at
        # https://stackoverflow.com/questions/3129322/how-do-i-get-monitor-resolution-in-python
        from PyQt4 import QtGui
        MyApp = QtGui.QApplication(sys.argv)
        screen_resolution = MyApp.desktop().screenGeometry()
        width = screen_resolution.width()
        height = screen_resolution.height()

    elif 'Qt5' in backend:
        # Implementation by Harsh Kumar Narula at
        # https://stackoverflow.com/questions/3129322/how-do-i-get-monitor-resolution-in-python
        from PyQt5 import QtWidgets
        MyApp = QtWidgets.QApplication(sys.argv)
        screen_resolution = MyApp.desktop().screenGeometry()
        width = screen_resolution.width()
        height = screen_resolution.height()

    else:
        print 'Solution not implemented yet for backend =', backend
        width, height = (1280, 1024)

    return (width, height)

if __name__ == "__main__":
    w, h = get_screen_size()
    print 'Screen size =', (w, h)
