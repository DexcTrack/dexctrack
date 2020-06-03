# This file provides a function to retrieve the screen size, with
# different implementations for different backends.
#
# License: Creative Commons CC-BY-SA
#          https://creativecommons.org/licenses/by-sa/4.0/
#
#

# Support python3 print syntax in python2
from __future__ import print_function

import os
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

    # Linux distributions using Wayland and a GTK or GTK3 backend
    # get us into trouble. For those backends, the code below grabs
    # the Active Window. This works well under X11, but Wayland refuses
    # to identify any Active Window. It's against their philosophy.
    # If we find we're in such a situation, switch to using the code
    # for a Tk backend case.
    if 'GTK' in backend:
        try:
            sessionType = os.environ['XDG_SESSION_TYPE']
            if sessionType == 'wayland':
                backend = 'TkAgg'
        except KeyError as e:
            if sys.version_info < (3, 0):
                sys.exc_clear()

    if 'GTK3' in backend:
        # Based on implementation by starfry, but updated for GTK3
        # https://stackoverflow.com/questions/3129322/how-do-i-get-monitor-resolution-in-python
        from gi.repository import Gtk as gtk

        window = gtk.Window()
        # the screen contains all monitors
        screen = window.get_screen()
        # collect data about active monitor
        curmon = screen.get_monitor_at_window(screen.get_active_window())
        # Newer versions of GTK require more work
        rect = screen.get_monitor_geometry(curmon) # get geometry rectangle of current monitor
        dx, dy, width, height = (rect.x, rect.y, rect.width, rect.height)

    elif 'GTK' in backend:
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
        # We can find the fullscreen size using just Tkinter, but there is an ugly
        # side-effect. To get the size of a full screen, we need to draw a window,
        # expand it to fullscreen, retrieve the size of that window, and then remove
        # it. This works, but drawing the window and then clearing it causes a flash on
        # screen, which is annoying. So, we'll first check to see if we have WX
        # available. Using that package, we can find the fullscreen size without
        # having to draw anything.
        try:
            # Modified version of implementation by FogleBird at
            # https://stackoverflow.com/questions/8762536/how-can-i-choose-the-default-wx-display-in-wxpython
            import wx

            MyApp = wx.App(False)   # the wx.App object must be created first.
            display = wx.Display(0) # find the size of the first display screen
            dx, dy, width, height = display.GetGeometry()
        except ImportError:
            if sys.version_info < (3, 0):
                sys.exc_clear()
            # Modified version of implementation by norok2 at
            # https://stackoverflow.com/questions/3129322/how-do-i-get-monitor-resolution-in-python/56913005#56913005
            # Modification parses the geometry string to extract width and height.
            try:
                # for Python 3
                import tkinter as tk
            except ImportError:
                if sys.version_info < (3, 0):
                    sys.exc_clear()
                # for Python 2
                import Tkinter as tk

            root = tk.Tk()
            root.update_idletasks()
            root.attributes('-fullscreen', True)
            root.state('iconic')
            geometry = root.winfo_geometry()
            # geometry format = Width'x'Height'+'Xoffset'+'Yoffset
            # For example, if run on the second screen of a double
            # monitor system: 1920x1080+1920+0
            width_s, height_s = (geometry.split('+'))[0].split('x')
            width, height = int(width_s), int(height_s)
            root.destroy()

    elif 'MacOSX' in backend:
        # Implementation by Koen Bok and kenorb
        # https://stackoverflow.com/questions/1281397/how-to-get-the-desktop-resolution-in-mac-via-python
        import AppKit
        curScreen = AppKit.NSScreen.mainScreen().frame()
        width = curScreen.size.width
        height = curScreen.size.height

    elif 'WX' in backend:
        if sys.platform == "win32":
            # Implementation by Stevoisiak + totaam at
            # https://stackoverflow.com/questions/3129322/how-do-i-get-monitor-resolution-in-python
            import ctypes
            user32 = ctypes.windll.user32
            user32.SetProcessDPIAware()
            width = user32.GetSystemMetrics(0)
            height = user32.GetSystemMetrics(1)
        else:
            import wx
            MyApp = wx.App(False)
            width, height = wx.GetDisplaySize()

    elif 'Qt4' in backend:
        # Implementation by Harsh Kumar Narula at
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
        print ('Solution not implemented yet for backend =', backend)
        width, height = (1280, 1024)

    return (width, height)

if __name__ == "__main__":
    w, h = get_screen_size()
    print ('Screen size =', (w, h))
