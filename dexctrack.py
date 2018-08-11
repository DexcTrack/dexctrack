###############################################################################
#    Copyright 2018 Steve Erlenborn
###############################################################################
#    This file is part of DexcTrack.
#
#    DexcTrack is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    DexcTrack is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
###############################################################################

import os
import sys
import time
import glob
import string
import sqlite3
import datetime
import threading
import argparse
import math
import tzlocal
import pytz
import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.style as style
import matplotlib.dates as mdates
from matplotlib.widgets import Slider
from matplotlib.widgets import Button
from matplotlib.widgets import TextBox
from matplotlib.widgets import SpanSelector
import numpy as np

import readReceiver
import constants
import screensize

dexctrackVersion = 1.7

# If a '-d' argument is included on the command line, we'll run in debug mode
parser = argparse.ArgumentParser()
parser.add_argument("-d", "--debug", help="enable debug mode", action="store_true")
parser.add_argument("-v", "--version", help="show version", action="store_true")
args = parser.parse_args()

if args.version:
    print 'Version =', dexctrackVersion
    sys.exit(0)

if args.debug:
    from pympler import muppy
    from pympler import tracker

print 'DexcTrack  Copyright (C) 2018  Steve Erlenborn'
print 'This program comes with ABSOLUTELY NO WARRANTY.\n'

# HD monitor  = 1920 x 1080 -> 1920/1080 = 1.8
# macbook pro = 1440 x 900  -> 1440/900  = 1.6
#               1280 x 1024 -> 1280/1024 = 1.25
width, height = screensize.get_screen_size()
dispRatio = round(float(width) / float(height), 1)
if args.debug:
    print 'get_screen_size width =', width, ', get_screen_size height =', height, ', dispRatio =', dispRatio

# Use the fivethirtyeight style, if it's available
try:
    style.use('fivethirtyeight')
except Exception as e:
    #print 'Style set. Exception =', e
    style.use('ggplot')

#####################################################################################################################
# The following variables are set for G4 or G5 devices. They might need to be altered for others.
#####################################################################################################################
meterSamplingPeriod = 60.0*5    # Dexcom will take a reading every 5 minutes, so we'll read from
                                # the receiver at this same rate.
minDisplayLow = 40              # the minimum glucose value Dexcom can detect
maxDisplayHigh = 400            # the maximum glucose value Dexcom can detect
sensorWarmupPeriod = 60*60*2    # 2 hours, in seconds

#####################################################################################################################
# The following are user interface defaults.
#####################################################################################################################
maxAnnotations = 30             # only display Events and Notes, if there are <= this number in display range
defaultDisplaySecs = 60*60*24   # 1 day, in seconds
displayRangeMin = 60*60*4       # 4 hours, in seconds
displayRangeMax = 60*60*24*14   # 2 weeks, in seconds
displayRange = 60*60*24         # default Scale displays one day of values
displayLow = 75.0               # default low end of Target Range
displayHigh = 200.0             # default high end of Target Range
position = 100.0                # start with display of the latest values
legDefaultPosX = 0.01           # default Legend horizontal location
legDefaultPosY = 1.00           # default Legend vertical location
graphTop = 0.87                 # top of y axis in figure coordinates
graphBottom = 0.24              # bottom of y axis position in figure coordinates
#####################################################################################################################
sliderSpace = 0.26              # reserve this much space below the graph to hold our 2 sliders

graphHeightInFigure = graphTop - graphBottom
UTC_BASE_TIME = datetime.datetime(2009, 1, 1, tzinfo=pytz.UTC)
readSerialNumInstance = None
readDataInstance = None
ax = None
tr = None
firstTestSysSecs = 0
lastTestSysSecs = 0
lastTestDateTime = UTC_BASE_TIME
lastMeanTestDateTime = UTC_BASE_TIME
nextMeanNn = 0
displayStartSecs = 0
cfgDisplayLow = None
cfgDisplayHigh = None
rthread = None
sthread = None
stat_text = None
serialNum = None
sPos = None
avgText = None
trendArrow = None
hba1c = 0.0
egvStdDev = 0.0
lastTestGluc = 0
xnorm = []
ynorm = []
runningMean = []
meanPlot = None
eventList = []
noteList = []
calibList = []
egvList = []
gluUnits = 'mg/dL'
dbGluUnits = 'mg/dL'
evt_annot = None
dis_annot = None
linePlot = None
egvScatter = None
calibScatter = None
desirableRange = None
lastTrend = None
majorFormatter = None
minorFormatter = None
red_patch = None
temp_red_patch = None
inRange_patch = None
temp_inRange_patch = None
temp_inRange_Arrow1 = None
temp_inRange_Arrow2 = None
temp_inRange_Arrow3 = None
redStartSet = set()
inRangeStartSet = set()
redRegionList = []
inRangeRegionList = []
inRangeRegionAnnotList = []
evtPlotList = []
notePlotList = []
etimeSet = set()
noteSet = set()
noteTimeSet = set()
leg = None
legPosX = -1.0
legPosY = -1.0
restart = False
bread = None
firstTestGluc = 0
avgGlu = 0
axNote = None
noteBoxPos = None
noteBox = None
noteArrow = None
noteText = ''
oldNoteText = ''
noteLoc = None
submit_id = None
trendChar = '-'
gluMult = 1.0
axPos = None
posText = None
axScale = None
scaleText = None
sScale = None
dspan = None
setRangeButton = None
sensorWarmupCountDown = None
latestSensorInsertTime = 0
minorTickSequence = range(24)
last_etime = None
annRotation = 1.0
annCloseCount = 0
axtest = None
testRead = None
highPercent = 0.0
midPercent = 0.0
lowPercent = 0.0
highPercentText = None
midPercentText = None
lowPercentText = None


# Disable default keyboard shortcuts so that a user
# accidentally hitting 'q' won't kill the application.
plt.rcParams['keymap.all_axes'] = ''
plt.rcParams['keymap.back'] = ''
plt.rcParams['keymap.forward'] = ''
plt.rcParams['keymap.fullscreen'] = ''
plt.rcParams['keymap.grid'] = ''
plt.rcParams['keymap.grid_minor'] = ''
plt.rcParams['keymap.home'] = ''
plt.rcParams['keymap.pan'] = ''
plt.rcParams['keymap.quit'] = ''
plt.rcParams['keymap.quit_all'] = ''
plt.rcParams['keymap.save'] = ''
plt.rcParams['keymap.xscale'] = ''
plt.rcParams['keymap.yscale'] = ''
plt.rcParams['keymap.zoom'] = ''

home_folder = os.path.expanduser('~')
sqlprefix = os.path.join(home_folder, 'dexc_')

mytz = tzlocal.get_localzone()
displayStartDate = datetime.datetime.now(mytz)

# We want to display dates in the local timezone
plt.rcParams['timezone'] = mytz


plt.rcParams['axes.axisbelow'] = False

#print 'interactive backends =',mpl.rcsetup.interactive_bk
#print 'non_interactive backends =',mpl.rcsetup.non_interactive_bk

# Start with a figure size which will fit on a 15 inch MacBook.
# Note that this will be overridden below, for most backends, by
# instructions to maximize the window size on a monitor.
fig = plt.figure(figsize=(14.5, 8.5))    # size, in inches  for 1440 x 900
#fig = plt.figure(figsize=(19.2, 10.8))   # size, in inches for 1920 x 1080
#fig = plt.figure(figsize=(13.3, 10.6))   # size, in inches for 1280 x 1024
figManager = plt.get_current_fig_manager()

backend = plt.get_backend()
if args.debug:
    print 'sys.platform =', sys.platform
    print 'backend =', backend
if 'Tk' in backend:
    figManager.resize(*figManager.window.maxsize())
elif ('Qt' in backend) or ('QT' in backend):
    figManager.window.showMaximized()
elif 'WX' in backend:
    figManager.frame.Maximize(True)

#---------------------------------------------------------

# The function below is a duplicate of the dexcom_reader util.py
# function ReceiverTimeToTime() except it uses UTC_BASE_TIME,
# which specifies a timezone.
def ReceiverTimeToUtcTime(rtime):
    return UTC_BASE_TIME + datetime.timedelta(seconds=rtime)

def UtcTimeToReceiverTime(dtime):
    return (int)((dtime - UTC_BASE_TIME).total_seconds())
#---------------------------------------------------------


#---------------------------------------------------------
def SecondsToGeneralTimeString(secs):
    """This function converts a number of seconds into a string describing the
    period of time represented by that number. The string indicates the number
    of months, weeks, days, and hours.

    Args:
        secs: : This is the time period in seconds
    Returns:
        A string description of the time period
    """
    seconds = secs
    months = seconds // (3600 * 24 * 30)
    seconds -= months * (3600 * 24 * 30)
    weeks = seconds // (3600 * 24 * 7)
    seconds -= weeks * (3600 * 24 * 7)
    days = seconds // (3600 * 24)
    seconds -= days * (3600 * 24)
    hours = seconds // 3600
    seconds -= hours * 3600
    minutes = seconds // 60
    seconds -= minutes * 60
    #print months,'months, ',weeks,'weeks, ',days,'days, ',hours,'hours, ',minutes,'minutes'

    if minutes > 30:
        hours += 1     # round up
        minutes -= 30
    if hours > 23:
        days += 1      # round up
        hours -= 24
    if days > 6:
        weeks += 1     # round up
        days -= 7
    if weeks > 4:
        months += 1     # round up
        weeks -= 5

    genstr = ''

    if months == 0:
        mstr = ''
    else:
        if months == 1:
            mstr = '%u month'%months
        else:
            mstr = '%u months'%months
        genstr = mstr

    if weeks != 0:
        if weeks == 1:
            wstr = '%u week'%weeks
        else:
            wstr = '%u weeks'%weeks
        if genstr == '':
            genstr = wstr
        else:
            genstr += ', '+wstr

    if days != 0:
        if days == 1:
            dstr = '%u day'%days
        else:
            dstr = '%u days'%days
        if genstr == '':
            genstr = dstr
        else:
            genstr += ', '+dstr

    if hours != 0:
        if hours == 1:
            hstr = '%u hour'%hours
        else:
            hstr = '%u hours'%hours
        if genstr == '':
            genstr = hstr
        else:
            genstr += ', '+hstr

    return genstr



#---------------------------------------------------------
def displayCurrentRange():
    #print 'displayRange =',displayRange,', displayStartSecs =',displayStartSecs,', displayStartSecs+displayRange =',displayStartSecs+displayRange,', lastTestSysSecs =',lastTestSysSecs

    #   +--------------------+--------------------------------------------------------+
    #   |                    |********************************************************|
    #   | <- displayRange -> |********************************************************|
    #   |                    |********************************************************|
    #   +--------------------+--------------------------------------------------------+
    #   |                    |                                                        |
    #   displayStartSecs     displayStartSecs+displayRange                            lastTestSysSecs

    #   +--------------------------+--------------------+-----------------------------+
    #   |**************************|                    |*****************************|
    #   |**************************| <- displayRange -> |*****************************|
    #   |**************************|                    |*****************************|
    #   +--------------------------+--------------------+-----------------------------+
    #   |                          |                    |                             |
    #   firstTestSysSecs           displayStartSecs     displayStartSecs+displayRange lastTestSysSecs

    #   +-----------------------------------------------------------------------------+
    #   |********************************************************|                    |
    #   |********************************************************| <- displayRange -> |
    #   |********************************************************|                    |
    #   +-----------------------------------------------------------------------------+
    #   |                                                        |                    |
    #   firstTestSysSecs                                         displayStartSecs     displayStartSecs+displayRange
    #                                                                                 lastTestSysSecs

    if (displayStartSecs + displayRange) > lastTestSysSecs:
        # there isn't enough data to fill out displayRange
        if (displayStartSecs - displayRange) < firstTestSysSecs:
            dispBegin = firstTestSysSecs
        else:
            dispBegin = max(lastTestSysSecs - displayRange, firstTestSysSecs)
        dispEnd = lastTestSysSecs
    else:
        dispBegin = displayStartSecs
        dispEnd = displayStartSecs + displayRange
    #print 'displayCurrentRange() displayStartSecs =',displayStartSecs,'displayRange =',displayRange,'dispBegin =',dispBegin,'dispEnd =',dispEnd
    if dispEnd > dispBegin:
        try:
            # the following can cause 'RuntimeError: dictionary changed size during iteration'
            ax.set_xlim(mdates.date2num(ReceiverTimeToUtcTime(dispBegin)),
                        mdates.date2num(ReceiverTimeToUtcTime(dispEnd)))
            #if args.debug:
                #print 'displayCurrentRange() before fig.canvas.draw_idle(), count =',len(muppy.get_objects())
            fig.canvas.draw_idle()   # each call generates new references to 120 - 300 objectss
            #if args.debug:
                #print 'displayCurrentRange() after fig.canvas.draw_idle(), count =',len(muppy.get_objects())
                #tr.print_diff()
        except Exception as e:
            print 'displayCurrentRange() : dispBegin =', dispBegin, ', dispEnd =', dispEnd, ', Exception =', e

#---------------------------------------------------------
def getSqlFileName(sNum):
    global serialNum
    #=======================================================================
    # The database files are of the form dexc_<SERIAL_NUMBER>.sqlite
    # This naming scheme allows handling of multiple receiver
    # devices. Each will have its own database file, due to uniqueness
    # of their serial numbers.
    # If a Reciever device is currently connected, then we'll create or open
    # an SQL database using its serial number. Otherwise, we'll look for the
    # most recently written database file, and use that.
    #=======================================================================
    if not sNum:
        # Default to the most recently written database file.
        pathname = '%s*.sqlite' % sqlprefix
        list_of_files = glob.glob(pathname)
        if list_of_files:
            my_sqlite_file = max(list_of_files, key=os.path.getctime)
            serialNum = string.replace(string.replace(my_sqlite_file, sqlprefix, ''), '.sqlite', '')
            #if args.debug:
                #print 'getSqlFileName(None) : No device connected, defaulting to %s' % my_sqlite_file
        else:
            my_sqlite_file = None
            serialNum = None
    else:
        my_sqlite_file = '%s%s.sqlite' % (sqlprefix, sNum)
        serialNum = sNum
    return my_sqlite_file

#---------------------------------------------------------
class deviceReadThread(threading.Thread):
    def __init__(self, threadID, name, loadToDbFunc):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.name = name
        self.readIntoDbFunc = loadToDbFunc
        self.evobj = threading.Event(1)
        self.restart = False
        self.firstDelayPeriod = 0
        if args.debug:
            print 'deviceReadThread launched, threadID =', threadID

    def stop(self):
        self.restart = False
        self.evobj.set()
        if args.debug:
            print 'Turning off device read thread at', datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # This function will cause termination of the current delay
    # sequence, and start of a new one, optionally beginning with
    # a given length for the first delay.
    def restartDelay(self, firstDelaySecs=meterSamplingPeriod):
        self.restart = True
        self.firstDelayPeriod = firstDelaySecs
        self.evobj.set()
        if args.debug:
            print 'Restarting device read delay. First delay =', firstDelaySecs

    def run(self):
        global readDataInstance
        while True:
            if self.restart is True:
                self.restart = False
            else:
                if stat_text:
                    stat_text.set_text('Reading\nReceiver\nDevice')
                    stat_text.set_backgroundcolor('yellow')
                    stat_text.draw(fig.canvas.get_renderer())

                if args.debug:
                    print 'Reading device at', datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                if sqlite_file is not None:
                    # We probably have new records to add to the database
                    self.readIntoDbFunc(sqlite_file)
                    if stat_text:
                        stat_text.set_text('Receiver\nDevice\nPresent')
                        stat_text.set_backgroundcolor('tomato')
                        stat_text.draw(fig.canvas.get_renderer())
                    plotGraph()    # Draw a new graph

            if self.firstDelayPeriod != 0:
                mydelay = float(self.firstDelayPeriod)
                if args.debug:
                    print 'Setting timeout delay to', mydelay
                self.firstDelayPeriod = 0
                waitStatus = self.evobj.wait(timeout=mydelay)   # wait up to firstDelayPeriod seconds
            else:
                waitStatus = self.evobj.wait(timeout=meterSamplingPeriod)

            # waitStatus = False on timeout, True if someone set() the event object
            if waitStatus is True:
                if self.restart is True:
                    if args.debug:
                        print 'deviceReadThread restart requested'
                    self.evobj.clear()
                else:
                    if args.debug:
                        print 'deviceReadThread terminated'
                    del readDataInstance
                    readDataInstance = None
                    return  # terminate the thread
        return

#---------------------------------------------------------
class deviceSeekThread(threading.Thread):
    def __init__(self, threadID, name):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.name = name
        self.connected_state = None
        self.evobj = threading.Event(1)
        #if args.debug:
            #print 'deviceSeekThread launched, threadID =', threadID

    def stop(self):
        self.evobj.set()
        if args.debug:
            print 'Turning off device seek thread at', datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def run(self):
        while True:
            global sqlite_file
            global rthread
            global restart
            global readSerialNumInstance

            prior_sqlite_file = sqlite_file
            prior_connected_state = self.connected_state
            sNum = None
            if readSerialNumInstance is None:
                dport = readReceiver.readReceiverBase.FindDevice()
                if dport is not None:
                    readSerialNumInstance = readReceiver.readReceiver(dport)
                self.connected_state = False

            if readSerialNumInstance is not None:
                sNum = readSerialNumInstance.GetSerialNumber()
                if not sNum:
                    self.connected_state = False
                    del readSerialNumInstance
                    readSerialNumInstance = None
                else:
                    self.connected_state = True

                sqlite_file = getSqlFileName(sNum)

            #if args.debug:
                #print 'deviceSeekThread.run() at', datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            if (self.connected_state != prior_connected_state) or (sqlite_file != prior_sqlite_file):
                #if args.debug:
                    #print 'Connected state :', prior_connected_state,' -> ',self.connected_state
                if not sNum:
                    if rthread != None:
                        # stop trying to read the missing device
                        rthread.stop()
                        rthread.join()
                        rthread = None
                    if stat_text:
                        stat_text.set_text('Receiver\nDevice\nAbsent')
                        stat_text.set_backgroundcolor('thistle')
                        stat_text.draw(fig.canvas.get_renderer())
                    plt.draw()
                else:
                    # A different device has been connected
                    if rthread != None:
                        rthread.stop()
                        rthread.join()
                        rthread = None
                    # set flag so that any plots from previous device get deleted
                    restart = True
                    # launch a thread to read this device periodically
                    PeriodicReadData()
            waitStatus = self.evobj.wait(timeout=21.0)   # wait up to 21 seconds
            # waitStatus = False on timeout, True if someone set() the event object
            if waitStatus is True:
                if args.debug:
                    print 'deviceSeekThread terminated'
                del readSerialNumInstance
                readSerialNumInstance = None
                return  # terminate the thread
        return


#---------------------------------------------------------
def PerodicDeviceSeek():
    global sthread
    sthread = deviceSeekThread(2, "Device seek thread")
    # If the user closes the window, we want this thread to also terminate
    sthread.daemon = True
    sthread.start()
    return

#---------------------------------------------------------
def PeriodicReadData():
    global rthread
    global readDataInstance

    # read data from the reciever
    if readSerialNumInstance is not None:
        devType = readSerialNumInstance.GetDeviceType()
    else:
        devType = None

    if devType is None:
        return
    elif devType == 'g4':
        if readDataInstance is None:
            dport = readReceiver.readReceiverBase.FindDevice()
            if dport is None:
                readDataInstance = None
                return
            else:
                readDataInstance = readReceiver.readReceiver(dport)
    elif devType == 'g5':
        if readDataInstance is None:
            dport = readReceiver.readReceiverBase.FindDevice()
            if dport is None:
                readDataInstance = None
                return
            else:
                readDataInstance = readReceiver.readReceiverG5(dport)
    elif devType == 'g6':
        # We might need a different routine for G6. I won't know until
        # I get access to a G6. For now call the same one as for G5.
        if readDataInstance is None:
            dport = readReceiver.readReceiverBase.FindDevice()
            if dport is None:
                readDataInstance = None
                return
            else:
                readDataInstance = readReceiver.readReceiverG6(dport)
    else:
        print 'PeriodicReadData() : Unrecognized firmware version', devType
        if rthread != None:
            rthread.stop()
            rthread.join()
        return

    if rthread != None:
        rthread.stop()
        rthread.join()
    rthread = deviceReadThread(1, "Periodic read thread", readDataInstance.DownloadToDb)
    # If the user closes the window, we want this thread to also terminate
    rthread.daemon = True
    rthread.start()
    return

#---------------------------------------------------------
def updatePos(val):
    global displayStartSecs
    global displayStartDate
    global position
    position = val
    origDisplayStartSecs = displayStartSecs
    #print 'updatePos() displayStartSecs =',displayStartSecs
    displayStartSecs = int(firstTestSysSecs + (position / 100.0) *
                           max(lastTestSysSecs - firstTestSysSecs - displayRange, 0))
    #print '----------> displayStartSecs =',displayStartSecs
    if posText:
        #posText.set_text('%5.2f%%'%position)
        displayStartDate = ReceiverTimeToUtcTime(displayStartSecs).astimezone(mytz)
        posText.set_text(displayStartDate.strftime("%Y-%m-%d"))
    if displayStartSecs != origDisplayStartSecs:
        displayCurrentRange()

#---------------------------------------------------------
def updateScale(val):
    global displayRange
    global displayStartDate
    global minorTickSequence
    global displayStartSecs

    displayRange = int(displayRangeMin + (val / 100.0) * (displayRangeMax - displayRangeMin))
    priorTickSequence = minorTickSequence

    # If user zooms the Scale way out, reduce the number of Hour ticks displayed
    if displayRange >= 60*60*24*24:
        minorTickSequence = (0, )
    elif displayRange >= 60*60*24*12:
        minorTickSequence = (0, 12)
    elif displayRange >= 60*60*24*8:
        minorTickSequence = (0, 8, 16)
    elif displayRange >= 60*60*24*6:
        minorTickSequence = (0, 6, 12, 18)
    elif displayRange >= 60*60*24*4:
        minorTickSequence = (0, 4, 8, 12, 16, 20)
    elif displayRange >= 60*60*24*3:
        minorTickSequence = (0, 3, 6, 9, 12, 15, 18, 21)
    elif displayRange >= 60*60*24*2:
        minorTickSequence = (0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22)
    else:
        minorTickSequence = range(24)

    # Only retick if the sequence has changed
    if minorTickSequence != priorTickSequence:
        ax.xaxis.set_minor_locator(mpl.dates.HourLocator(byhour=minorTickSequence, tz=mytz))

    displayStartSecs = int(firstTestSysSecs + (position / 100.0) *
                           max(lastTestSysSecs - firstTestSysSecs - displayRange, 0))
    displayStartDate = ReceiverTimeToUtcTime(displayStartSecs).astimezone(mytz)
    if posText:
        posText.set_text(displayStartDate.strftime("%Y-%m-%d"))
    if scaleText:
        scaleText.set_text(SecondsToGeneralTimeString(displayRange))
    ShowOrHideEventsNotes()
    displayCurrentRange()

#-----------------------------------------------------------------------------------
# If user hits the '<-' or '->' keys, scroll the position display to left or right.
#-----------------------------------------------------------------------------------
#
#   min(displayStartSecs) = firstTestSysSecs                 max(displayStartSecs) = LastTestSysSecs - displayRange
#   |<------------------------------------------------------>|
#   |                                                        |
#   0% <------------------ position ----------------------> 100%
#   |                                                        |
#   V                                                        V
#   +----------------------+--------------------+------------+--------------------+
#   |**********************|                    |************|                    |
#   |**********************| <- displayRange -> |************| <- displayRange -> |
#   |**********************|                    |************|                    |
#   +----------------------+--------------------+------------+--------------------+
#   ^                      ^                    ^                                 ^
#   |                      |                    |                                 |
#   firstTestSysSecs       displayStartSecs     displayStartSecs+displayRange     LastTestSysSecs
#
#   position = (displayStartSecs - firstTestSysSecs)/(lastTestSysSecs - displayRange - firstTestSysSecs) * 100.0
#
def press(event):
    global position
    global displayStartSecs
    #print('press', event.key)
    sys.stdout.flush()

    origDisplayStartSecs = displayStartSecs
    origPosition = position

    if event.inaxes is axNote:
        # When we're in the Note entry box, 'left' and 'right' are to be used for
        # editing purposes. We don't want those keys to cause data display adjustments.
        pass
    else:
        if event.key == 'left':
            displayStartSecs = max(firstTestSysSecs, displayStartSecs - displayRange)
            # Need to convert datetime values to floats to avoid occasional
            # 'TypeError: float() argument must be a string or a number' errors.
            if displayStartSecs != origDisplayStartSecs:
                ax.set_xlim(mdates.date2num(ReceiverTimeToUtcTime(displayStartSecs)),
                            mdates.date2num(ReceiverTimeToUtcTime(min(displayStartSecs+displayRange, lastTestSysSecs+1))))
            if lastTestSysSecs-displayRange-firstTestSysSecs > 0:
                position = min(100.0 * (displayStartSecs-firstTestSysSecs) / (lastTestSysSecs-displayRange-firstTestSysSecs), 100.0)
            else:
                position = 100.0
            if position != origPosition:
                sPos.set_val(position)  # this will cause fig.canvas.draw() to be called
            elif displayStartSecs != origDisplayStartSecs:
                fig.canvas.draw()

        elif event.key == 'right':
            displayStartSecs = max(firstTestSysSecs, min(lastTestSysSecs - displayRange, displayStartSecs + displayRange))
            # Need to convert datetime values to floats to avoid occasional
            # 'TypeError: float() argument must be a string or a number' errors.
            if displayStartSecs != origDisplayStartSecs:
                ax.set_xlim(mdates.date2num(ReceiverTimeToUtcTime(displayStartSecs)),
                            mdates.date2num(ReceiverTimeToUtcTime(min(displayStartSecs+displayRange, lastTestSysSecs+1))))
            if lastTestSysSecs-displayRange-firstTestSysSecs > 0:
                position = min(100.0 * (displayStartSecs-firstTestSysSecs) / (lastTestSysSecs-displayRange-firstTestSysSecs), 100.0)
            else:
                position = 100.0
            if position != origPosition:
                sPos.set_val(position)  # this will cause fig.canvas.draw() to be called
            elif displayStartSecs != origDisplayStartSecs:
                fig.canvas.draw()

#---------------------------------------------------------
def submitNote(text):
    global noteText
    global oldNoteText
    #print 'submitNote() : oldNoteText =', noteText,', noteText =', text
    oldNoteText = noteText
    noteText = text
    if noteArrow is not None:
        writeNote()

#---------------------------------------------------------
def writeNote():
    global noteText
    global oldNoteText
    global noteArrow
    global submit_id

    #print 'writeNote() : oldNoteText =',oldNoteText,', noteText =',noteText

    if noteArrow is not None:
        # oldNoteText='', noteText=''       --> do nothing
        # oldNoteText='', noteText='abc'    --> clear arrow
        # oldNoteText='abc', noteText='def' --> clear arrow
        # oldNoteText='abc', noteText=''    --> clear arrow
        if oldNoteText == noteText:
            return
        if noteText is not '':
            #print 'add note', 'noteLoc[0] =',noteLoc[0],'noteLoc[1] =',noteLoc[1]
            if noteLoc[1] > 200:
                yoffset = -50.0
            else:
                yoffset = 50.0
            noteAnn = ax.annotate(noteText,
                                  xy=noteLoc, xycoords='data',
                                  xytext=(0, yoffset), textcoords='offset pixels',
                                  color='black', fontsize=16,
                                  arrowprops=dict(connectionstyle="arc3,rad=-0.3", facecolor='brown',
                                                  shrink=0.10, width=2, headwidth=6.5))
            noteAnn.draggable()
            noteSet.add(noteAnn)
            noteTimeSet.add(mdates.num2date(noteAnn.xy[0], tz=mytz))
            #print 'writeNote note : X =',noteAnn.xy[0],'Y =',noteAnn.xy[1],'datetime =',mdates.num2date(noteAnn.xy[0],tz=mytz)
            noteText = ''
            oldNoteText = ''
            if submit_id is not None:
                noteBox.disconnect(submit_id)
            noteBox.set_val('')
            submit_id = noteBox.on_submit(submitNote)
        #else:
            #print 'writetNote() : noteText = \'\''
        #print 'writetNote() : calling noteArrow.remove()'
        noteArrow.remove()
        noteArrow = None
        fig.canvas.draw()

#-----------------------------------------------------------------------------------
# If user clicks on a plot point
#   If text is present in the Note box, write that note at the click point
#   Else, draw an arrow from the empty Note box to the click point
#-----------------------------------------------------------------------------------
def onpick(event):
    global noteArrow
    global noteLoc
    global noteText
    global oldNoteText
    global submit_id

    mouseevent = event.mouseevent
    if mouseevent:
        if mouseevent.xdata and mouseevent.ydata:
            #print 'onpick(event) : button =',mouseevent.button,', xdata =',tod,', ydata =',gluc
            # Check for a right button click. Some mouse devices only have 2 buttons, and some
            # have 3, so treat either one as a "right button".
            if (mouseevent.button == 2) or (mouseevent.button == 3):
                #print 'onpick(event) : tod =',tod,', xdata =',mouseevent.xdata,', gluc =',gluc
                noteLoc = (mouseevent.xdata, mouseevent.ydata)
                matchNote = None
                for note in noteSet:
                    #print 'onpick(event) : X.dist =',mouseevent.xdata - note.xy[0],'Y.dist =',mouseevent.ydata - note.xy[1]
                    xdist = abs(mouseevent.xdata - note.xy[0])
                    # test if we're within 2.5 minutes of this note
                    if xdist < 0.001735906:
                        #print 'onpick(event) : xdist =',xdist, 'match =',note.xy[0],',',note.xy[1],'=',ReceiverTimeToUtcTime(note.xy[0]),'<--- Match'
                        matchNote = note
                        break

                if noteBoxPos:
                    if noteArrow:
                        # If an arrow already exists ...
                        if (abs(noteArrow.xy[0] - noteLoc[0]) < 0.001735906) and (noteText == ''):
                            # and the position of that arrow matches where the user
                            # just clicked, then we'll delete that arrow
                            #print 'onpick(event) : arrow position matches'
                            noteArrow.remove()
                            noteArrow = None
                            return
                        # Otherwise, we'll remove the old arrow, and ...
                        noteArrow.remove()
                    # Draw a new arrow to the new position
                    noteArrow = ax.annotate('', xy=noteLoc, xycoords='data',
                                            xytext=(noteBoxPos.x0, noteBoxPos.y0),
                                            textcoords='figure fraction',
                                            arrowprops=dict(arrowstyle="->", color='green',
                                                            linewidth=3.0))
                    fig.canvas.draw()

                    if matchNote is None:
                        #print 'onpick(event) : calling writeNote()'
                        oldNoteText = ''
                        writeNote()
                    else:
                        if noteText == '':
                            noteText = matchNote.get_text()
                            if args.debug:
                                print "Editing existing note '%s'" % noteText
                            noteSet.discard(matchNote)
                            matchNote.remove()
                            if submit_id is not None:
                                noteBox.disconnect(submit_id)
                            noteBox.set_val(noteText)
                            submit_id = noteBox.on_submit(submitNote)
                        else:
                            # replace the old note with the new one
                            oldNoteText = matchNote.get_text()
                            if args.debug:
                                print "Replace the old note '%s' with the new one '%s'" % (oldNoteText, noteText)
                            matchNote.set_text(noteText)
                            noteArrow.remove()
                            noteArrow = None
                            noteBox.set_val('')
                            fig.canvas.draw()

            elif mouseevent.button == 1:
                #print 'Button left'
                pass
            elif mouseevent.button == 'up':
                #print 'Button up'
                pass
            elif mouseevent.button == 'down':
                #print 'Button down'
                pass

#---------------------------------------------------------
def onclose(event):
    global rthread
    global sthread

    if args.debug:
        print '*****************'
        print 'Close in progress'
        print '*****************'

    # Shutdown PeriodicReadData thread
    if rthread is not None:
        rthread.stop()
        #print 'Waiting on rthread.join()'
        rthread.join()
        rthread = None

    # Shutdown PerodicDeviceSeek thread
    if sthread is not None:
        sthread.stop()
        #print 'Waiting on sthread.join()'
        sthread.join()
        sthread = None

    if sqlite_file:
        conn = sqlite3.connect(sqlite_file)
        try:
            curs = conn.cursor()

            curs.execute('CREATE TABLE IF NOT EXISTS UserNote( sysSeconds INT PRIMARY KEY, message TEXT, xoffset REAL, yoffset REAL);')
            # The user may have deleted some of the notes, so we need to eliminate them from
            # the database. We'll do this by deleting all notes, and then inserting all notes
            # which currently exist in the note set.
            if len(noteSet) > 0:
                curs.execute('DELETE FROM UserNote')
            insert_note_sql = '''INSERT OR IGNORE INTO UserNote( sysSeconds, message, xoffset, yoffset) VALUES (?, ?, ?, ?);'''
            for note in noteSet:
                #print 'time =',note.xy[0],'=',mdates.num2date(note.xy[0],tz=mytz)
                #print 'INSERT OR IGNORE INTO UserNote( sysSeconds, message, xoffset, yoffset) VALUES (%u,%s,%f,%f);' %(UtcTimeToReceiverTime(mdates.num2date(note.xy[0],tz=mytz)),'%s'%note.get_text(),note.xyann[0],note.xyann[1])
                curs.execute(insert_note_sql, (UtcTimeToReceiverTime(mdates.num2date(note.xy[0], tz=mytz)), '%s'%note.get_text(), note.xyann[0], note.xyann[1]))


            # If the user has repositioned any event text boxes, update the X and Y offsets in the database
            selectSql = 'SELECT sysSeconds,dispSeconds,meterSeconds,type,subtype,value,xoffset,yoffset FROM UserEvent WHERE sysSeconds=?'
            insert_evt_sql = '''INSERT OR REPLACE INTO UserEvent( sysSeconds, dispSeconds, meterSeconds, type, subtype, value, xoffset, yoffset) VALUES (?, ?, ?, ?, ?, ?, ?, ?);'''
            for evt_inst in evtPlotList:
                eseconds = UtcTimeToReceiverTime(mdates.num2date(evt_inst.xy[0]))
                curs.execute(selectSql, (eseconds,))
                sqlData = curs.fetchone()
                if sqlData is not None:
                    if (evt_inst.xyann[0] != sqlData[6]) or (evt_inst.xyann[1] != sqlData[7]):
                        if False:
                            print '\nMatch Event: ', ReceiverTimeToUtcTime(sqlData[0]), 'sysSeconds =', sqlData[0], 'dispSeconds =', sqlData[1], 'meterSeconds =', sqlData[2], 'type =', sqlData[3], 'subtype =', sqlData[4], 'value =', sqlData[5], 'xoffset =', evt_inst.xyann[0], 'yoffset =', evt_inst.xy[1] - evt_inst.xyann[1]
                            print 'evt_inst.xy =', evt_inst.xy, 'evt_inst.xyann =', evt_inst.xyann, ', Evt =', evt_inst.get_text()
                            print 'INSERT OR REPLACE INTO UserEvent( sysSeconds=%u, dispSeconds=%u, meterSeconds=%u, type=%u, subtype=%u, value=%f, xoffset=%f, yoffset=%f);'%(sqlData[0], sqlData[1], sqlData[2], sqlData[3], sqlData[4], sqlData[5], evt_inst.xyann[0], evt_inst.xyann[1])
                        curs.execute(insert_evt_sql, (sqlData[0], sqlData[1], sqlData[2],
                                                      sqlData[3], sqlData[4], sqlData[5],
                                                      evt_inst.xyann[0], evt_inst.xyann[1]))

            if leg:
                lframe = leg.get_frame()
                lx, ly = lframe.get_x(), lframe.get_y()
                legx, legy = fig.transFigure.inverted().transform((lx, ly))
                #print 'legx, legy =',(legx, legy)
            else:
                #legx,legy = legDefaultPosX, legDefaultPosY
                legx, legy = 0, 0

            #print 'INSERT OR REPLACE INTO Config (id, displayLow, displayHigh, legendX, legendY, glUnits) VALUES (0,',displayLow,',',displayHigh,',',legx,',',legy,',\'%s\');' %gluUnits
            insert_cfg_sql = '''INSERT OR REPLACE INTO Config( id, displayLow, displayHigh, legendX, legendY, glUnits) VALUES (0, ?, ?, ?, ?, ?);'''
            curs.execute(insert_cfg_sql, (displayLow, displayHigh, legx, legy, gluUnits))

            curs.close()
            conn.commit()
        except Exception as e:
            print 'onclose() : Rolling back sql changes due to exception =', e
            curs.close()
            conn.rollback()
        conn.close()
    plt.close('all')

#---------------------------------------------------------
def leave_axes(event):
    global displayStartDate
    if event.inaxes is axScale:
        if scaleText:
            scaleText.set_text(SecondsToGeneralTimeString(displayRange))
            fig.canvas.draw_idle()
    elif event.inaxes is axPos:
        if posText:
            #posText.set_text('%5.2f%%'%position)
            displayStartDate = ReceiverTimeToUtcTime(displayStartSecs).astimezone(mytz)
            posText.set_text(displayStartDate.strftime("%Y-%m-%d"))
            fig.canvas.draw_idle()

#---------------------------------------------------------
def update_egc_annot(ind):
    if egvScatter and dis_annot:
        pos = egvScatter.get_offsets()[ind["ind"][0]]
        dis_annot.xy = pos
        tod, gluc = (mdates.num2date(pos[0], tz=mytz), pos[1])
        if gluUnits == 'mmol/L':
            if sys.platform == "win32":
                text = "%s,\n%5.2f" % (tod.strftime("%#I:%M%p"), gluc)
            else:
                text = "%s,\n%5.2f" % (tod.strftime("%-I:%M%p"), gluc)
        else:
            if sys.platform == "win32":
                text = "%s,\n%u" % (tod.strftime("%#I:%M%p"), gluc)
            else:
                text = "%s,\n%u" % (tod.strftime("%-I:%M%p"), gluc)
        dis_annot.set_text(text)
        dis_annot.get_bbox_patch().set_facecolor('k')
        dis_annot.get_bbox_patch().set_alpha(0.3)

#---------------------------------------------------------
def hover(event):
    if event.inaxes is axScale:
        # When we're in the Scale slider we want to display a summary statement for
        # the time period represented by the current position of the mouse.
        xsecs = int(displayRangeMin + event.xdata/100.0 * (displayRangeMax-displayRangeMin))
        #print 'hover() : xdata =',event.xdata,', seconds =',xsecs,SecondsToGeneralTimeString(xsecs)
        text = SecondsToGeneralTimeString(xsecs)
        ptext = '(%s)'%text
        if scaleText:
            scaleText.set_text(ptext)
            fig.canvas.draw_idle()
    elif event.inaxes is axPos:
        #ptext = '(%5.2f%%)'%event.xdata
        xsecs = int(firstTestSysSecs + (event.xdata / 100.0) *
                    max(lastTestSysSecs - firstTestSysSecs - displayRange, 0))
        myDisplayStartDate = ReceiverTimeToUtcTime(xsecs).astimezone(mytz)
        ptext = '(%s)'% myDisplayStartDate.strftime("%Y-%m-%d")
        if posText:
            posText.set_text(ptext)
            fig.canvas.draw_idle()
    else:
        if egvScatter and dis_annot:
            vis = dis_annot.get_visible()
            ycont = False
            if event.inaxes == ax:
                ycont, ind = egvScatter.contains(event)
            if ycont:
                update_egc_annot(ind)
                dis_annot.set_visible(True)
                fig.canvas.draw_idle()
            else:
                if vis:
                    dis_annot.set_visible(False)
                    fig.canvas.draw_idle()
#---------------------------------------------------------
def onselect(ymin, ymax):
    global displayLow
    global displayHigh
    #print 'onselect: min =',ymin,', max =',ymax
    displayLow = round(ymin / gluMult, 0)
    displayHigh = round(ymax / gluMult, 0)
    dspan.active = False
    #print 'onselect: displayLow =', gluMult * displayLow, ', displayHigh =', gluMult * displayHigh
    if (displayLow != cfgDisplayLow) or (displayHigh != cfgDisplayHigh):
        if rthread is not None:
            rthread.restartDelay()
        #print 'onselect: calling plotGraph'
        plotGraph()

#---------------------------------------------------------
def ReadButtonCallback(event):
    #global bread
    #print 'Button pressed'
    if dspan:
        if dspan.active:
            dspan.active = False
            #bread.label.set_text('Click to Set\nDesirable\nRange')
        else:
            dspan.active = True
            #bread.label.set_text('Use Left mouse button\nto select range')

#---------------------------------------------------------
def TestButtonCallback(event):
    print 'Test Button pressed. Will read in 10 seconds.'
    timeLeftSeconds = 10
    if rthread is not None:
        print 'Calling rthread.restartDelay()'
        rthread.restartDelay(firstDelaySecs=timeLeftSeconds)
    else:
        print 'rthread is NULL'

#---------------------------------------------------------
def ClearGraph(event):
    global redRegionList
    global evtPlotList
    global notePlotList
    global egvScatter
    global calibScatter
    global linePlot
    global inRangeRegionList
    global inRangeRegionAnnotList

    # erase all previously plotted red calibration regions
    for redmark in redRegionList:
        redmark.remove()
    redRegionList = []
    redStartSet.clear()
    inRangeRegionList = []
    while len(inRangeRegionAnnotList) > 0:
        inRangeItem = inRangeRegionAnnotList.pop(0)
        inRangeItem.remove()
    inRangeRegionAnnotList = []
    inRangeStartSet.clear()

    # erase all previously plotted events
    for evtP in evtPlotList:
        evtP.remove()
    evtPlotList = []
    # erase all previously plotted notes
    for noteP in notePlotList:
        noteP.remove()
    notePlotList = []
    etimeSet.clear()
    noteSet.clear()
    if egvScatter:
        egvScatter.remove()
        egvScatter = None
    if calibScatter:
        calibScatter.remove()
        calibScatter = None
    if linePlot:
        linePlot.pop(0).remove()
        linePlot = None

#---------------------------------------------------------
def plotInit():
    global sPos
    global sScale
    global stat_text
    global avgText
    global trendArrow
    global majorFormatter
    global minorFormatter
    global axNote
    global noteBox
    global noteBoxPos
    global submit_id
    global axPos
    global axScale
    global setRangeButton
    global bread
    global legDefaultPosX
    global legDefaultPosY
    global highPercentText
    global midPercentText
    global lowPercentText
    #global axtest
    #global testRead

    if args.debug:
        print 'rcParams[timezone] =', mpl.rcParams['timezone']

    # Reserve some space at the bottom for the Sliders
    fig.subplots_adjust(bottom=sliderSpace)

    axcolor = 'lightsteelblue'

    axPos = plt.axes([0.20, 0.05, 0.70, 0.03], facecolor=axcolor)
    sPos = Slider(axPos, 'Start Date', 0.0, position, 100.0, color='royalblue')
    # We don't want to display the numerical value, since we're going to
    # draw a text value of the percentage in the middle of the slider.
    sPos.valtext.set_visible(False)

    axScale = plt.axes([0.20, 0.01, 0.70, 0.03], facecolor=axcolor)
    sScale = Slider(axScale, 'Scale', 0.0, 100.0, 100.0, color='green')
    # We don't want to display the numerical value, since we're going to
    # describe the period of time with a string in the middle of the slider.
    sScale.valtext.set_visible(False)

    stat_text = plt.figtext(.05, .04, 'Search\nReceiver\nDevice', fontsize=14,
                            backgroundcolor='y', size='large', weight='bold',
                            horizontalalignment='center')

    #print 'pixels per inch =',fig.canvas.winfo_fpixels( '1i' )

    ########################################################
    # hd terminal = 1920 x 1080 -> 1920/1080 = 1.8
    # macbook pro = 1440 x 900  -> 1440/900  = 1.6
    #                              1280/1024 = 1.25
    ########################################################
    if 1.0 < dispRatio <= 1.4:   # = 1.25 for 1280 x 1024 ratio
        avgTextX = 0.68
        avgTextY = 0.88
        rangeX = 0.901
        rangeY = 0.008
        rangeW = 0.089
        rangeH = 0.099
        legDefaultPosX = 0.095
        legDefaultPosY = 0.857
        trendX = 0.965
        trendY = 0.930
        noteX = 0.34
        noteY = 0.92
        noteW = 0.32
        noteH = 0.04
        logoX = 0.043
        logoY = 0.952
        verX = 0.010
        verY = 0.886
    elif 1.4 < dispRatio <= 1.7:  # = 1.6 for 1440 x 900 ratio
        avgTextX = 0.70
        avgTextY = 0.85
        rangeX = 0.901
        rangeY = 0.008
        rangeW = 0.089
        rangeH = 0.099
        legDefaultPosX = 0.095
        legDefaultPosY = 0.875
        trendX = 0.965
        trendY = 0.930
        noteX = 0.33
        noteY = 0.92
        noteW = 0.36
        noteH = 0.04
        logoX = 0.037
        logoY = 0.945
        verX = 0.003
        verY = 0.870
    else:  # 1.7 < dispRatio <= 2.0:  # 1.8 for 1920 x 1080 ratio
        avgTextX = 0.76
        avgTextY = 0.88
        rangeX = 0.905
        rangeY = 0.010
        rangeW = 0.085
        rangeH = 0.075
        legDefaultPosX = 0.093
        legDefaultPosY = 0.878
        trendX = 0.965
        trendY = 0.930
        noteX = 0.28
        noteY = 0.92
        noteW = 0.40
        noteH = 0.04
        logoX = 0.037
        logoY = 0.945
        verX = 0.022
        verY = 0.880

    if gluUnits == 'mmol/L':
        avgText = plt.gcf().text(avgTextX, avgTextY, 'Latest = %5.2f (mmol/L)\nAvg = %5.2f (mmol/L)\nStdDev = %5.2f\nHbA1c = %5.2f'
                                 %(0, 0, 0, 0), style='italic', size='x-large', weight='bold')
    else:
        #avgText = plt.gcf().text(0.70, 0.87, 'Latest = %u (mg/dL)\nAvg = %5.2f (mg/dL)\nHbA1c = %5.2f'
        avgText = plt.gcf().text(avgTextX, avgTextY, 'Latest = %u (mg/dL)\nAvg = %5.2f (mg/dL)\nStdDev = %5.2f\nHbA1c = %5.2f'
                                 %(0, 0, 0, 0), style='italic', size='x-large', weight='bold')

    trendArrow = plt.gcf().text(trendX, trendY, "Trend", ha="center", va="center",
                                rotation=0, size=15,
                                bbox=dict(boxstyle="rarrow,pad=0.3", facecolor="cyan", edgecolor="b", lw=2))

    # Plot percentages high, middle, and low
    highPercentText = plt.figtext(0.95, ((maxDisplayHigh - displayHigh) / 2.0 + displayHigh) / maxDisplayHigh * graphHeightInFigure + graphBottom,
                                  '%4.1f' %highPercent, style='italic', size='large', weight='bold', color='red')
    midPercentText = plt.figtext(0.95, ((displayHigh - displayLow) / 2.0 + displayLow) / maxDisplayHigh * graphHeightInFigure + graphBottom,
                                 '%4.1f' %midPercent, style='italic', size='large', weight='bold', color='cornflowerblue')
    lowPercentText = plt.figtext(0.95, displayLow / 2.0 / maxDisplayHigh * graphHeightInFigure + graphBottom,
                                 '%4.1f' %lowPercent, style='italic', size='large', weight='bold', color='magenta')


    # To show every 0.05 step of figure height
    #for bb in range(0, 20, 1):
        #plt.figtext(0.95, 1.0*bb/20.0, '%2.2f' %(1.0*bb/20.0), size='small')

    sPos.on_changed(updatePos)
    sScale.on_changed(updateScale)

    # year-month-day without prepended 0's. E.g. 2018-3-31
    # Locale appropriate date representation. E.g. 03/31/18
    if sys.platform == "win32":
        majorFormatter = mpl.dates.DateFormatter('%Y-%#m-%#d\n%A')
        minorFormatter = mpl.dates.DateFormatter('%#H')
    else:
        majorFormatter = mpl.dates.DateFormatter('%Y-%-m-%-d\n%A')
        minorFormatter = mpl.dates.DateFormatter('%-H')
    minorFormatter.MAXTICKS = int(displayRangeMax / (60*60))

    plt.gca().set_ylim([gluMult * minDisplayLow, gluMult * maxDisplayHigh])

    fig.canvas.mpl_connect('key_press_event', press)
    fig.canvas.mpl_connect("motion_notify_event", hover)

    plt.gcf().autofmt_xdate()

    axNote = plt.axes([noteX, noteY, noteW, noteH], frameon=True, zorder=10)
    #noteBox = TextBox(axNote, 'Note', color='tan', hovercolor='burlywood')
    noteBox = TextBox(axNote, 'Note', color='tan', hovercolor='coral')
    submit_id = noteBox.on_submit(submitNote)
    noteBoxPos = axNote.get_position()
    #print 'noteBoxPos.x0 =',noteBoxPos.x0,'noteBoxPos.y0 =',noteBoxPos.y0,'noteBoxPos =',noteBoxPos

    setRangeButton = plt.axes([rangeX, rangeY, rangeW, rangeH], zorder=13)   # X, Y, X-width, Y-height
    bread = Button(setRangeButton, 'Set\nNew Target\nRange', color='gold', hovercolor='red')
    bread.on_clicked(ReadButtonCallback)

    #axtest = plt.axes([0, 0.15, 0.1, 0.075])
    #testRead = Button(axtest, 'Jump', color='pink')
    #testRead.on_clicked(TestButtonCallback)

    figLogo = plt.gcf().text(logoX, logoY, 'Dexc\nTrack', style='italic', size=25, weight='bold',
                             color='orange', backgroundcolor='teal', ha='center', va='center')

    figVersion = plt.gcf().text(verX, verY, 'v%s' %dexctrackVersion, size=12, weight='bold')


#---------------------------------------------------------
def readDataFromSql():
    global firstTestSysSecs
    global lastTestSysSecs
    global lastTestDateTime
    global firstTestGluc
    global lastTestGluc
    global egvList
    global calibList
    global eventList
    global noteList
    global avgGlu
    global hba1c
    global egvStdDev
    global lastTrend
    global trendChar
    global cfgDisplayLow
    global cfgDisplayHigh
    global latestSensorInsertTime
    global legPosX
    global legPosY
    global dbGluUnits
    global highPercent
    global midPercent
    global lowPercent

    egvList = []
    calibList = []
    eventList = []
    noteList = []

    if sqlite_file:
        conn = sqlite3.connect(sqlite_file)
        curs = conn.cursor()

        # sysSeconds  dispSeconds  full_glucose  glucose     testNum     trend
        # ----------  -----------  ------------  ----------  ----------  ----------
        # 289620658   289599058    87            87          7101        21
        # 289620959   289599359    1             1           7102        88        SENSOR_NOT_ACTIVE
        # 289621558   289599958    5             5           7104        88        SENSOR_NOT_CALIBRATED
        # ...
        # 289628758   289607157    5             5           7133        88        SENSOR_NOT_CALIBRATED
        # 289628951   289607350    32773         5           16777215    88        SENSOR_NOT_CALIBRATED | EGV_DISPLAY_ONLY_MASK
        # 289628977   289607376    32935         167         16777215    88        EGV_DISPLAY_ONLY_MASK
        # 289629059   289607458    16546         162         7134        20
        # 289629358   289607757    162           162         7135        20

        selectSql = "SELECT count(*) from sqlite_master where type='table' and name='EgvRecord'"
        curs.execute(selectSql)
        sqlData = curs.fetchone()
        if sqlData[0] > 0:

            # get the first test info
            curs.execute('SELECT sysSeconds,glucose,testNum FROM EgvRecord ORDER BY sysSeconds ASC LIMIT 1')
            sqlData = curs.fetchall()
            for row in sqlData:
                firstTestSysSecs = row[0]
                firstTestGluc = row[1]

            # get the last test info
            curs.execute('SELECT sysSeconds,glucose,testNum FROM EgvRecord ORDER BY sysSeconds DESC LIMIT 1')
            sqlData = curs.fetchall()
            for row in sqlData:
                lastTestSysSecs = row[0]
                lastTestDateTime = ReceiverTimeToUtcTime(lastTestSysSecs)
                #print 'Last testNum =',row[3]

            # get the last real glucose reading
            curs.execute('SELECT glucose,trend FROM EgvRecord WHERE glucose > 12 ORDER BY sysSeconds DESC LIMIT 1')
            sqlData = curs.fetchall()
            for row in sqlData:
                lastTestGluc = row[0]
                lastTrend = row[1] & constants.EGV_TREND_ARROW_MASK

                if lastTrend == 1:     # doubleUp
                    trendChar = '^'
                elif lastTrend == 2:   # singleUp
                    trendChar = '^'
                elif lastTrend == 3:   # fortyFiveUp
                    trendChar = '/'
                elif lastTrend == 4:   # flat
                    trendChar = '-'
                elif lastTrend == 5:   # fortyFiveDown
                    trendChar = '\\'
                elif lastTrend == 6:   # singleDown
                    trendChar = 'v'
                elif lastTrend == 7:   # doubleDown
                    trendChar = 'V'
                else:                  # none (0) | notComputable (8) | rateOutOfRange (9)
                    trendChar = '-'

            if args.debug:
                print 'Latest glucose at', lastTestDateTime.astimezone(mytz), '=', lastTestGluc

            sqlMinTime = firstTestSysSecs
            sqlMaxTime = lastTestSysSecs
            #print 'sqlMinTime =',sqlMinTime,', sqlMaxTime =',sqlMaxTime
            #-----------------------------------------------------

            selectSql = 'SELECT sysSeconds,glucose FROM EgvRecord WHERE sysSeconds >= ? AND sysSeconds <= ? ORDER BY sysSeconds'

            # We need to limit the size of the selection to avoid ...
            # RuntimeError: RRuleLocator estimated to generate 4194 ticks from
            # 2018-02-13 04:51:15.957009+00:00 to 2018-02-27 18:22:28.042979+00:00
            # : exceeds Locator.MAXTICKS * 2 (2000)
            curs.execute(selectSql, (sqlMinTime, sqlMaxTime))
            sqlData = curs.fetchall()
            #print 'sql results length =',len(sqlData),'sqlMinTime =',sqlMinTime,'sqlMaxTime =',sqlMaxTime

            for row in sqlData:
                egvList.append([ReceiverTimeToUtcTime(row[0]), row[1]])

            #++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
            # testNum == 16777215 for calibration events
            selectSql = 'SELECT sysSeconds,glucose FROM EgvRecord WHERE testNum = 16777215 AND sysSeconds >= ? AND sysSeconds <= ? ORDER BY sysSeconds'
            curs.execute(selectSql, (sqlMinTime, sqlMaxTime))
            sqlData = curs.fetchall()
            #print 'sql calibration results length =',len(sqlData)

            for row in sqlData:
                calibList.append([ReceiverTimeToUtcTime(row[0]), row[1]])
            #++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

            #++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
            # Find HbA1c. This is based on the average of glucose values over the last
            # 3 months, so limit the range of values to be averaged.
            selectSql = 'SELECT AVG(glucose) FROM EgvRecord WHERE glucose > 12 AND sysSeconds >= ?'
            ninetyDaysBack = int(lastTestSysSecs - 60*60*24*30*3)
            #print 'ninetyDaysBack =',ninetyDaysBack
            curs.execute(selectSql, (ninetyDaysBack,))
            sqlData = curs.fetchone()
            if sqlData[0] is None:
                avgGlu = 0.0
                hba1c = 0.0
            else:
                avgGlu = sqlData[0]
                hba1c = (sqlData[0] + 46.7) / 28.7
                #print 'Average glucose =', avgGlu,', HbA1c =',hba1c

            #++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
            selectSql = 'SELECT COUNT (*) FROM EgvRecord WHERE glucose > 12 AND glucose < ? AND sysSeconds >= ?'
            curs.execute(selectSql, (displayLow, ninetyDaysBack))
            sqlData = curs.fetchone()
            if sqlData[0] is None:
                lowCount = 0
            else:
                lowCount = sqlData[0]

            selectSql = 'SELECT COUNT (*) FROM EgvRecord WHERE glucose >= ? AND glucose <= ? AND sysSeconds >= ?'
            curs.execute(selectSql, (displayLow, displayHigh, ninetyDaysBack))
            sqlData = curs.fetchone()
            if sqlData[0] is None:
                midCount = 0
            else:
                midCount = sqlData[0]

            selectSql = 'SELECT COUNT (*) FROM EgvRecord WHERE glucose > ? AND sysSeconds >= ?'
            curs.execute(selectSql, (displayHigh, ninetyDaysBack))
            sqlData = curs.fetchone()
            if sqlData[0] is None:
                highCount = 0
            else:
                highCount = sqlData[0]

            lmhTotal = lowCount + midCount + highCount
            if lmhTotal > 0:
                highPercent = 100.0 * highCount / lmhTotal
                midPercent = 100.0 * midCount / lmhTotal
                lowPercent = 100.0 * lowCount / lmhTotal
            else:
                highPercent = 0.0
                midPercent = 0.0
                lowPercent = 0.0
            #print 'highPercent =', highPercent, ', midPercent =', midPercent, ', lowPercent =', lowPercent

            #++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
            # Calculate the SampleVariance over the last 3 months
            #++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
            #selectSql = 'SELECT AVG((glucose - ?) * (glucose - ?)) FROM EgvRecord WHERE glucose > 12 AND sysSeconds >= ?'
            selectSql = 'SELECT glucose FROM EgvRecord WHERE glucose > 12 AND sysSeconds >= ?'
            curs.execute(selectSql, (ninetyDaysBack,))
            sqlData = curs.fetchall()
            egvCount = len(sqlData)

            if egvCount > 1:
                selectSql = 'SELECT TOTAL((glucose - ?) * (glucose - ?)) FROM EgvRecord WHERE glucose > 12 AND sysSeconds >= ?'
                curs.execute(selectSql, (avgGlu, avgGlu, ninetyDaysBack,))
                sqlData = curs.fetchone()
                if sqlData[0] is None:
                    egvSampleVariance = 0.0
                else:
                    # For a Sample Variance, divide by N - 1
                    egvSampleVariance = sqlData[0] / (egvCount - 1)
            else:
                egvSampleVariance = 0.0
            #++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
            # The Standard Deviation is the square root of the SampleVariance
            #++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
            egvStdDev = math.sqrt(egvSampleVariance)
            #if args.debug:
                #print 'egvCount =',egvCount,', egvSampleVariance =',egvSampleVariance,', egvStdDev =',egvStdDev



        #++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
        selectSql = "SELECT count(*) from sqlite_master where type='table' and name='UserEvent'"
        curs.execute(selectSql)
        sqlData = curs.fetchone()
        if sqlData[0] > 0:
            selectSql = 'SELECT sysSeconds,type,subtype,value,xoffset,yoffset FROM UserEvent ORDER BY sysSeconds'
            curs.execute(selectSql)
            sqlData = curs.fetchall()
            for row in sqlData:
                #print 'Event: sysSeconds =',row[0],'type =',row[1],'subtype =',row[2],'value =',row[3],'xoffset =',row[4],'yoffset =',row[5]
                eventList.append([ReceiverTimeToUtcTime(row[0]), row[1], row[2], row[3], row[4], row[5]])
        #++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
        selectSql = "SELECT count(*) from sqlite_master where type='table' and name='UserNote'"
        curs.execute(selectSql)
        sqlData = curs.fetchone()
        if sqlData[0] > 0:
            selectSql = 'SELECT sysSeconds,message,xoffset,yoffset FROM UserNote ORDER BY sysSeconds'
            curs.execute(selectSql)
            sqlData = curs.fetchall()
            for row in sqlData:
                #print 'Note: sysSeconds =',row[0],'message =',row[1],'xoffset =',row[2],'yoffset =',row[3]
                noteList.append([ReceiverTimeToUtcTime(row[0]), row[1], row[2], row[3]])
        #++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

        selectSql = "SELECT count(*) from sqlite_master where type='table' and name='SensorInsert'"
        curs.execute(selectSql)
        sqlData = curs.fetchone()
        if sqlData[0] > 0:
            # get the latest sensor insertion Start (state == 7) time
            curs.execute('SELECT insertSeconds FROM SensorInsert WHERE state = 7 ORDER BY sysSeconds DESC LIMIT 1')
            sqlData = curs.fetchall()
            for row in sqlData:
                latestSensorInsertTime = row[0]

        #++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
        if (cfgDisplayLow is None) and (cfgDisplayHigh is None):
            selectSql = "SELECT count(*) from sqlite_master where type='table' and name='Config'"
            curs.execute(selectSql)
            sqlData = curs.fetchone()
            if sqlData[0] > 0:
                selectSql = "SELECT displayLow, displayHigh, legendX, legendY, glUnits FROM Config"
                curs.execute(selectSql)
                sqlData = curs.fetchone()
                if sqlData is not None:
                    cfgDisplayLow = sqlData[0]
                    cfgDisplayHigh = sqlData[1]
                    legPosX = sqlData[2]
                    legPosY = sqlData[3]
                    dbGluUnits = sqlData[4]
            else:
                cfgDisplayLow = displayLow
                cfgDisplayHigh = displayHigh
                legPosX = legDefaultPosX
                legPosY = legDefaultPosY
                dbGluUnits = 'mg/dL'

        #++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

        del sqlData

        curs.close()
        conn.close()

#---------------------------------------------------------
def getNearPos(array, value):
    idx = (np.abs(array-value)).argmin()
    return idx


#---------------------------------------------------------
def ShowOrHideEventsNotes():
    global evtPlotList
    global notePlotList
    global last_etime
    global annRotation
    global annCloseCount
    global evt_annot

    #=======================================================
    # Annotate the plot with user events
    #=======================================================
    multX = 1.0
    multY = 1.0
    visibleAnnotCount = 0

    # Find the size of the plotting area in pixels
    ax_bbox = ax.get_window_extent().transformed(fig.dpi_scale_trans.inverted())
    ax_width, ax_height = ax_bbox.width * fig.dpi, ax_bbox.height * fig.dpi
    #print 'ax_width, ax_height =', (ax_width, ax_height)

    #if args.debug:
        #print 'Before visible events count =', len(muppy.get_objects())

    begTime = ReceiverTimeToUtcTime(displayStartSecs)
    endTime = ReceiverTimeToUtcTime(displayStartSecs + displayRange)
    for (estime, etype, esubtype, evalue, exoffset, eyoffset) in eventList:
        if (estime >= begTime) and (estime < endTime):
            visibleAnnotCount += 1

    for (estime, message, xoffset, yoffset) in noteList:
        if (estime >= begTime) and (estime < endTime):
            visibleAnnotCount += 1

    #print 'visibleAnnotCount =',visibleAnnotCount
    #if args.debug:
        #print 'After visible events count =', len(muppy.get_objects())

    if visibleAnnotCount > maxAnnotations:
        # User has probably zoomed out so much that plotting all these
        # annotations will just make a mess, so hide all of them. User
        # can zoom in to see more detail, and show annotations if we
        # pass this test.
        # Erase all previously plotted event annotations
        for evtP in evtPlotList:
            evtP.remove()
        evtPlotList = []
        etimeSet.clear()
        # erase all previously plotted notes
        noteTimeSet.clear()
        for noteP in notePlotList:
            noteP.remove()
        notePlotList = []
        return

    if len(xnorm) == 0:
        return

    #if args.debug:
        #print 'Before events count =', len(muppy.get_objects())
    evtgen = (ev for ev in eventList if ev[0] not in etimeSet)
    for (estime, etype, esubtype, evalue, exoffset, eyoffset) in evtgen:
        timeIndex = getNearPos(xnorm, estime)
        #print 'Event: time =',estime,'type =',etype,'subtype =',esubtype,'value =',evalue,'index =',timeIndex,'glu =',ynorm[timeIndex]
        longTextBump = 0

        if etype == 1:
            evt_color = 'orangered'
            evtStr = '%ug Carbs'%evalue

        elif etype == 2:
            evt_color = 'blue'
            evtStr = '%0.2f Insulin'%(evalue / 100.0)

        elif etype == 3: # Health
            evt_color = 'purple'
            if esubtype == 1:
                evtStr = 'Illness'
            elif esubtype == 2:
                evtStr = 'Stress'
            elif esubtype == 3:
                evtStr = 'Feel High'
            elif esubtype == 4:
                evtStr = 'Feel Low'
            elif esubtype == 5:
                evtStr = 'Cycle'
            elif esubtype == 6:
                evtStr = 'Alcohol'
            else:
                evtStr = 'Health ?'

        elif etype == 4:
            evt_color = 'green'
            longTextBump = 5
            if esubtype == 1:
                evtStr = '%u min light exercise'%evalue
            elif esubtype == 2:
                evtStr = '%u min moderate exercise'%evalue
            elif esubtype == 3:
                evtStr = '%u min heavy exercise'%evalue
            else:
                evtStr = '%u min ? exercise'%evalue
        else:
            evt_color = 'black'
            evtStr = 'Unknown event'
        #if args.debug:
            #print 'After setting event string count =',len(muppy.get_objects())

        if last_etime:
            # Since users can insert many events in close proximity,
            # the default placement tends to cause collisions of the
            # text. Here, we check to see if the current event is
            # close (in time) to the previous one. If so, we'll switch
            # the arrow position from left + down, to left + up, to right + up
            # to right + down. If 5 in a row are close, then we push the
            # distance out. This scheme spirals the placement out in
            # the order 'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', etc.
            #
            #  'H' (-2,2)----------------+   +-------------(2,2) 'E'
            #                            |   |
            #                            |   |
            #          'D' (-1,1)-----+  |   |  +-----(1,1) 'A'
            #                         |  V   V  |
            #                         V         V
            #
            #                         ^         <-------+
            #                         |  ^   ^          |
            #         'C' (-1,-1)-----+  |   |        (1,-1) 'B'
            #                            |   |
            #                            |   |
            # 'G' (-2,-2)----------------+   +-------------(2,-2) 'F'
            #
            if (estime - last_etime) < datetime.timedelta(minutes=110):
                #print '---> estime =',estime,'estime - last_etime =',estime - last_etime,', evtStr =',evtStr
                if annCloseCount & 3 == 0:
                    multX = annRotation
                    multY = -annRotation
                elif annCloseCount & 3 == 1:
                    multX = -annRotation
                    multY = annRotation
                elif annCloseCount & 3 == 2:
                    multX = -annRotation
                    multY = -annRotation
                else:
                    annRotation += 0.85
                    multX = annRotation
                    multY = annRotation
                annCloseCount += 1
            else:
                #print 'estime =',estime,'estime - last_etime =',estime - last_etime,', evtStr =',evtStr
                annRotation = 1.0
                longTextBump = 0
                annCloseCount = 0
                multX = 1.0
                multY = 1.0
            #if args.debug:
                #print 'After setting multX, multY, annRotation, count =',len(muppy.get_objects())

        # If a specific position has not been established for the event yet, automatically
        # generate a value which is distanced away from recent event locations.
        #if True:   # Use this to force automatic repositioning
        if (exoffset == 0.0) and (eyoffset == 0.0):
            exoffset = multX * 70.0
            eyoffset = multY * (75+longTextBump)

        #################################################################################
        #   There's a bug in handling draggable annotations in matplotlib which causes
        # it to sometimes store the offset (in pixels) and sometimes the raw location
        # in data units. Since we're storing the "offset" value into the database and
        # later use that value as an offset, this bug can cause event plotting to drift
        # far away from where it belongs.
        #  To deal with this bug, we'll check to see if the offset values are too
        # large to be reasonable, or if they cause the event string to fall outside
        # the Y dimension of the axes. If so, we'll establish a new plotting offset.
        #################################################################################

        repositioned = False

        # If the X offset is more than half the width of the screen, we'll override
        # with a small offset.
        if exoffset < -ax_width / 2:
            if args.debug:
                print 'Event @ %s \'%s\' X offset %f < -half screen width (%f)' % (estime.astimezone(mytz), evtStr, exoffset, -ax_width / 2)
            exoffset = -60.0
            repositioned = True
        elif exoffset > ax_width / 2:
            if args.debug:
                print 'Event @ %s \'%s\' X offset %f > half screen width (%f)' % (estime.astimezone(mytz), evtStr, exoffset, ax_width / 2)
            exoffset = 60.0
            repositioned = True

        # If the Y offset is more than half the height of the screen, we'll override
        # it with a small offset.
        if eyoffset < -ax_height * gluMult / 2:
            if args.debug:
                print 'Event @ %s \'%s\' Y offset %f < -half screen height (%f)' % (estime.astimezone(mytz), evtStr, eyoffset, -ax_height * gluMult / 2)
            eyoffset = -60.0
            repositioned = True
        elif eyoffset > ax_height * gluMult / 2:
            if args.debug:
                print 'Event @ %s \'%s\' Y offset %f > half screen height (%f)' % (estime.astimezone(mytz), evtStr, eyoffset, ax_height * gluMult / 2)
            eyoffset = 60.0
            repositioned = True

        if repositioned:
            if args.debug:
                print 'After repositioning, new offsets =', (exoffset, eyoffset)

        # Sometimes the calculated or stored Y offset position lands outside
        # the limits of the axes, making it invisible. In such a case, we want to
        # recalculate the offset position.
        if (ynorm[timeIndex] + eyoffset > maxDisplayHigh) or (ynorm[timeIndex] + eyoffset < 0):
            if args.debug:
                print 'Event @ %s \'%s\' Y offset %f (%f + %f) is outside plotting area. Recalculating.' % (estime.astimezone(mytz), evtStr, ynorm[timeIndex] + eyoffset, ynorm[timeIndex], eyoffset)
            strawY = multY*(75+longTextBump)
            if ((ynorm[timeIndex] + strawY) > maxDisplayHigh) or ((ynorm[timeIndex] + strawY) < 0):
                eyoffset = -strawY
            else:
                eyoffset = strawY

            if ((ynorm[timeIndex] + eyoffset) > maxDisplayHigh) or (ynorm[timeIndex] + eyoffset < 0):
                if args.debug:
                    print 'Event @ %s \'%s\' recalculated Y offset %f (%f + %f) is outside plotting area.' % (estime.astimezone(mytz), evtStr, ynorm[timeIndex] + eyoffset, ynorm[timeIndex], eyoffset)
                eyoffset *= -1.5
            if args.debug:
                print '    new offsets =', (exoffset, eyoffset)

        evt_annot = ax.annotate(evtStr,
                                xy=(mdates.date2num(estime), ynorm[timeIndex]), xycoords='data',
                                xytext=(exoffset, eyoffset), textcoords='offset pixels',
                                fontsize=16, color=evt_color,
                                arrowprops=dict(connectionstyle="arc3,rad=.3", facecolor=evt_color,
                                                shrink=0.10, width=2, headwidth=6.5), zorder=11)

        #if args.debug:
            #print 'After event annotation, count =',len(muppy.get_objects())
        evt_annot.draggable()
        evtPlotList.append(evt_annot)
        #if args.debug:
            #print 'After event append, count =',len(muppy.get_objects())
        last_etime = estime
        # add this to the list of events which have already been annotated
        etimeSet.add(estime)

    #=======================================================
    # User Notes
    #=======================================================
    #if args.debug:
        #print 'After events, before Notes count =', len(muppy.get_objects())
    notegen = (nt for nt in noteList if nt[0] not in noteTimeSet)
    for (estime, message, nxoffset, nyoffset) in notegen:
        #tod, gluc = (mdates.num2date(mouseevent.xdata,tz=mytz), mouseevent.ydata)
        timeIndex = getNearPos(xnorm, estime)

        repositioned = False

        # If the X offset is more than half the width of the screen, we'll override
        # with a small offset.
        if nxoffset < -ax_width / 2:
            if args.debug:
                print 'Note @ %s \'%s\' X offset %f < -half screen width (%f)' % (estime.astimezone(mytz), message, nxoffset, -ax_width / 2)
            nxoffset = -60.0
            repositioned = True
        elif nxoffset > ax_width / 2:
            if args.debug:
                print 'Note @ %s \'%s\' X offset %f > half screen width (%f)' % (estime.astimezone(mytz), message, nxoffset, ax_width / 2)
            nxoffset = 60.0
            repositioned = True

        # If the Y offset is more than half the height of the screen, we'll override
        # it with a small offset.
        if nyoffset < -ax_height / 2:
            if args.debug:
                print 'Note @ %s \'%s\' Y offset %f < -half screen height (%f)' % (estime.astimezone(mytz), message, nyoffset, -ax_height / 2)
            nyoffset = -60.0
            repositioned = True
        elif nyoffset > ax_height / 2:
            if args.debug:
                print 'Note @ %s \'%s\' Y offset %f > half screen height (%f)' % (estime.astimezone(mytz), message, nyoffset, ax_height / 2)
            nyoffset = 60.0
            repositioned = True

        if repositioned:
            if args.debug:
                print 'After repositioning, new offsets =', (nxoffset, nyoffset)

        # Sometimes the calculated or stored Y offset position lands outside
        # the limits of the axes, making it invisible. In such a case, we want to
        # recalculate the offset position.
        if (ynorm[timeIndex] + nyoffset > maxDisplayHigh) or (ynorm[timeIndex] + nyoffset < 0):
            if args.debug:
                print 'Note @ %s \'%s\' Y offset %f (%f + %f) is outside plotting area. Recalculating.' % (estime.astimezone(mytz), message, ynorm[timeIndex] + nyoffset, ynorm[timeIndex], nyoffset)
            strawY = multY*(75+longTextBump)
            if ((ynorm[timeIndex] + strawY) > maxDisplayHigh) or ((ynorm[timeIndex] + strawY) < 0):
                nyoffset = -strawY
            else:
                nyoffset = strawY

            if ((ynorm[timeIndex] + nyoffset) > maxDisplayHigh) or (ynorm[timeIndex] + nyoffset < 0):
                if args.debug:
                    print 'Note @ %s \'%s\' recalculated Y offset %f (%f + %f) is outside plotting area.' % (estime.astimezone(mytz), message, ynorm[timeIndex] + nyoffset, ynorm[timeIndex], nyoffset)
                nyoffset *= -1.5
            if args.debug:
                print '    new offsets =', (nxoffset, nyoffset)

        #print 'Note: estime =', estime, ', gluc =', ynorm[timeIndex],'message =', message, 'xoffset =', nxoffset, 'yoffset =', nyoffset
        noteAnn = ax.annotate(message,
                              xy=(mdates.date2num(estime), ynorm[timeIndex]), xycoords='data',
                              xytext=(nxoffset, nyoffset), textcoords='offset pixels',
                              color='black', fontsize=16,
                              arrowprops=dict(connectionstyle="arc3,rad=-0.3", facecolor='brown',
                                              shrink=0.10, width=2, headwidth=6.5), zorder=11)
        noteAnn.draggable()
        notePlotList.append(noteAnn)
        #print 'plotGraph note : X =',noteAnn.xy[0],'Y =',noteAnn.xy[1],'xytext[0] =',noteAnn.xytext[0],'xytext[1] =',noteAnn.xytext[1]
        #print 'plotGraph note : X =', noteAnn.xy[0], 'Y =', noteAnn.xy[1], 'datetime =', estime
        # add this to the list of notes which have already been annotated
        noteTimeSet.add(estime)
        noteSet.add(noteAnn)

#---------------------------------------------------------
def glucInRange(glucose):
    return gluMult * displayLow <= glucose <= gluMult * displayHigh

#---------------------------------------------------------
def plotGraph():
    global ax
    global xnorm
    global ynorm
    global runningMean
    global calibScatter
    global egvScatter
    global desirableRange
    global tr
    global displayRange
    global displayStartSecs
    global firstPlotGraph
    global dis_annot
    global linePlot
    global red_patch
    global temp_red_patch
    global inRange_patch
    global temp_inRange_patch
    global temp_inRange_Arrow1
    global temp_inRange_Arrow2
    global temp_inRange_Arrow3
    global redRegionList
    global inRangeRegionList
    global inRangeRegionAnnotList
    global evtPlotList
    global notePlotList
    global leg
    global legPosX
    global legPosY
    global restart
    global posText
    global scaleText
    global displayLow
    global displayHigh
    global cfgDisplayLow
    global cfgDisplayHigh
    global dspan
    global sensorWarmupCountDown
    global gluUnits
    global gluMult
    global displayStartDate
    global meanPlot
    global lastMeanTestDateTime
    global nextMeanNn
    global highPercentText
    global midPercentText
    global lowPercentText

    #print 'plotGraph() entry\n++++++++++++++++++++++++++++++++++++++++++++++++'
    if firstPlotGraph == 1:
        if args.debug:
            tr = tracker.SummaryTracker()

        ax = fig.add_subplot(1, 1, 1)
        # rotate labels a bit to use less vertical space
        plt.xticks(rotation=30)

        # mpl.dates.MinuteLocator(interval=15)
        ax.xaxis.set_major_locator(mpl.dates.DayLocator())
        ax.xaxis.set_minor_locator(mpl.dates.HourLocator())
        ax.xaxis.set_major_formatter(majorFormatter)
        ax.xaxis.set_minor_formatter(minorFormatter)
        ax.autoscale_view()
        ax.grid(True)
        ax.tick_params(direction='out', pad=15)
        ax.set_xlabel('Date & Time')
        ax.set_ylabel('Glucose (%s)'%gluUnits)

        dis_annot = ax.annotate("", xy=(0, 0), xytext=(12, 12), textcoords="offset points",
                                bbox=dict(boxstyle="round", facecolor="w"),
                                arrowprops=dict(arrowstyle="->"))
        dis_annot.set_visible(False)

        # Don't move the following to plotInit() or Scale slider will be messed up
        plt.autoscale(True, 'both', None)

        displayRange = defaultDisplaySecs

        sScale.set_val(100.0*(displayRange-displayRangeMin)/(displayRangeMax-displayRangeMin))

        #posText = axPos.text(50.0, 0.35, '%5.2f%%'%position, horizontalalignment='center')
        dispDate = displayStartDate.strftime("%Y-%m-%d")
        posText = axPos.text(50.0, 0.35, dispDate, horizontalalignment='center', weight='bold')
        if gluUnits == 'mmol/L':
            scaleText = axScale.text(50.00, 7.0, SecondsToGeneralTimeString(displayRange), horizontalalignment='center', weight='bold')
        else:
            scaleText = axScale.text(50.00, 100.0, SecondsToGeneralTimeString(displayRange), horizontalalignment='center', weight='bold')

        dspan = SpanSelector(ax, onselect, 'vertical', useblit=True,
                             rectprops=dict(alpha=0.5, facecolor='red'),
                             minspan=3.0 * gluMult, button=1)
        # The span selector will not be activated until the setRangeButton is clicked
        dspan.active = False

        firstPlotGraph = 0

    if restart is True:
        if args.debug:
            print 'Erasing plot data from previous device'
        # erase all previously plotted red calibration regions
        for redmark in redRegionList:
            redmark.remove()
        redRegionList = []
        redStartSet.clear()
        while len(inRangeRegionAnnotList) > 0:
            inRangeItem = inRangeRegionAnnotList.pop(0)
            inRangeItem.remove()
        inRangeRegionAnnotList = []
        while len(inRangeRegionList) > 0:
            inRangeRegionList.pop(0).remove()
            #inRangeItem = inRangeRegionList.pop(0)
            #poly = inRangeItem
            #poly.remove()
        inRangeRegionList = []
        inRangeStartSet.clear()

        # erase all previously plotted event annotations
        for evtP in evtPlotList:
            evtP.remove()
        evtPlotList = []
        etimeSet.clear()
        # erase all previously plotted notes
        noteTimeSet.clear()
        for noteP in notePlotList:
            noteP.remove()
        notePlotList = []
        del runningMean[:]
        runningMean = []
        lastMeanTestDateTime = UTC_BASE_TIME
        nextMeanNn = 0
        cfgDisplayLow = None
        cfgDisplayHigh = None
        restart = False

    #if args.debug:
        #tr.print_diff()
    readDataFromSql()

    if dbGluUnits != gluUnits:
        if dbGluUnits == 'mmol/L':
            # mmol/L = mg/dL x 0.0555
            gluMult = 0.0555
            scaleText.y = 7.0
        else:
            gluMult = 1.0
            scaleText.y = 70.0
        ax.set_ylabel('Glucose (%s)'%dbGluUnits)
        # erase all previously plotted event annotations
        for evtP in evtPlotList:
            evtP.remove()
        evtPlotList = []
        etimeSet.clear()
        # erase all previously plotted notes
        noteTimeSet.clear()
        for noteP in notePlotList:
            noteP.remove()
        notePlotList = []

    # mark the desirable glucose region
    if desirableRange:
        # Only redraw desirable range if it has changed since the last drawing
        if (displayLow != cfgDisplayLow) or (displayHigh != cfgDisplayHigh) or (dbGluUnits != gluUnits):

            # Need to clear in target annotations, since the target size has changed
            while len(inRangeRegionAnnotList) > 0:
                inRangeItem = inRangeRegionAnnotList.pop(0)
                inRangeItem.remove()
            inRangeRegionAnnotList = []
            while len(inRangeRegionList) > 0:
                inRangeRegionList.pop(0).remove()
                #inRangeItem = inRangeRegionList.pop(0)
                #poly = inRangeItem
                #poly.remove()
            inRangeRegionList = []
            inRangeStartSet.clear()

            #print 'High/Low value(s) changed'
            cfgDisplayLow = displayLow
            cfgDisplayHigh = displayHigh
            desirableRange.remove()
            desirableRange = plt.axhspan(gluMult * displayLow, gluMult * displayHigh, facecolor='khaki', alpha=1.0)

            # Re-plot percentages high, middle, and low
            highPercentText.remove()
            midPercentText.remove()
            lowPercentText.remove()
            highPercentText = plt.figtext(0.95, ((maxDisplayHigh - displayHigh) / 2.0 + displayHigh) / maxDisplayHigh * graphHeightInFigure + graphBottom,
                                          '%4.1f' %highPercent, style='italic', size='large', weight='bold', color='red')
            midPercentText = plt.figtext(0.95, ((displayHigh - displayLow) / 2.0 + displayLow) / maxDisplayHigh * graphHeightInFigure + graphBottom,
                                         '%4.1f' %midPercent, style='italic', size='large', weight='bold', color='cornflowerblue')
            lowPercentText = plt.figtext(0.95, displayLow / 2.0 / maxDisplayHigh * graphHeightInFigure + graphBottom,
                                         '%4.1f' %lowPercent, style='italic', size='large', weight='bold', color='magenta')
    else:
        #print 'Setting initial High/Low values'
        if cfgDisplayLow is not None:
            displayLow = cfgDisplayLow
        if cfgDisplayHigh is not None:
            displayHigh = cfgDisplayHigh
        desirableRange = plt.axhspan(gluMult * displayLow, gluMult * displayHigh, facecolor='khaki', alpha=1.0)

    gluUnits = dbGluUnits

    highPercentText.set_text('%4.1f%%' %highPercent)
    midPercentText.set_text('%4.1f%%' %midPercent)
    lowPercentText.set_text('%4.1f%%' %lowPercent)

    #if args.debug:
        #print 'plotGraph() :  After desirableRange() count =', len(muppy.get_objects())
        #print '++++++++++++++++++++++++++++++++++++++++++++++++\n'
        #tr.print_diff()

    # Under some window managers, e.g. MATE, a minimized application
    # will still display the window title, or at least the beginning
    # portion of the window title. We want to include critical
    # information at the beginning of that title, so the user can see
    # the the current glucose level and trend.
    # For example, if the current glucose level is 93 and falling, the
    # window title will begin with '93 \'.
    try:    # during shutdown, this can fail with "AttributeError: 'NoneType' object has no attribute 'wm_title'"
        if gluUnits == 'mmol/L':
            fig.canvas.set_window_title('%5.2f %c DexcTrack: %s' % (gluMult * lastTestGluc, trendChar, serialNum))
        else:
            fig.canvas.set_window_title('%u %c DexcTrack: %s' % (lastTestGluc, trendChar, serialNum))
    except Exception as e:
        if args.debug:
            print 'fig.canvas.set_window_title: Exception =', e
        return

    if len(egvList) > 0:
        data = np.array(egvList)
        xx = []
        yy = []
        xx = data[:, 0] # ReceiverTimeToUtcTime(sysSeconds)
        yy = data[:, 1] # glucose
        #print 'sizeof(data) =',len(data),'sizeof(xx) =',len(xx),'sizeof(yy) =',len(yy)

        # If we have at least two data points, and the glucose values are not "special" values
        if len(xx) > 1 and len(yy) > 1 and yy[-1] > 12 and yy[-2] > 12:
            # predict values for the next couple of hours based on the last two data points
            xdiff = xx[-1]-xx[-2]
            ydiff = yy[-1]-yy[-2]

            # Predict glucose value in two hours based on current rate of change.
            # 2 hours = 24 * 5 minute samplings
            predx = xx[-1] + 24 * xdiff
            predy = min(max(minDisplayLow, yy[-1] + 24.0 * ydiff), maxDisplayHigh)
            if args.debug:
                print '2 hour prediction : at', predx.astimezone(mytz), 'glucose =', predy


        # create subset of normal (non-calib) data points
        # and a subset of calibration data points
        xnorm = []
        xnorm = xx[yy > 12]

        calibdata = np.array(calibList)
        #print 'sizeof(calibdata) =',len(calibdata)
        cx = []
        cy = []
        cxnorm = []
        cx = calibdata[:, 0] # sysSeconds
        cy = calibdata[:, 1] # glucose
        cxnorm = cx[cy > 12]
        #print 'sizeof(xnorm) =',len(xnorm),'sizeof(cx) =',len(cx),'sizeof(cy) =',len(cy),'sizeof(cxnorm) =',len(cxnorm)
        ynorm = []
        cynorm = []
        ynorm = yy[yy > 12] * gluMult
        cynorm = cy[cy > 12] * gluMult

        #print 'len(xx) =',len(xx),' len(yy) =',len(yy),' len(cx) =',len(cx),' len(cy) =',len(cy),' len(cxnorm) =',len(cxnorm),' len(cynorm) =',len(cynorm)

        #-----------------------------------------------------
        # Find ranges where we're out of calibration.
        # This implementation only adds new calibration regions.
        # The only one we might need to erase and redraw is a
        # partial region which is increasing in size.
        #-----------------------------------------------------
        calibZoneList = []
        lastx = ReceiverTimeToUtcTime(firstTestSysSecs)
        lasty = firstTestGluc
        startOfZone = lastx
        tempRangeEnd = startOfZone
        for pointx, pointy in zip(xx, yy):
            if (lasty <= 12) and (pointy > 12):
                # we've transitioned out of a calib zone
                #print 'calibZoneList[] adding ',startOfZone,'to',pointx
                calibZoneList.append([startOfZone, pointx])
            elif (lasty > 12) and (pointy <= 12):
                # we've transitioned into a calib zone
                startOfZone = pointx
            lastx = pointx
            lasty = pointy

        #if args.debug:
            #print 'plotGraph() :  After calibZoneList() count =', len(muppy.get_objects())
            #print '++++++++++++++++++++++++++++++++++++++++++++++++\n'
            #tr.print_diff()

        if lasty <= 12:
            # We reached the end of the data points while still in
            # an uncalibrated range, so add this final range.
            secsSinceWarmupStart = max(0, UtcTimeToReceiverTime(lastx) - latestSensorInsertTime)
            if secsSinceWarmupStart < sensorWarmupPeriod:
                if args.debug:
                    print 'Sensor Warm-up Time =', secsSinceWarmupStart, 'out of', sensorWarmupPeriod, 'seconds'
                timeLeftSeconds = sensorWarmupPeriod - secsSinceWarmupStart
                timeLeftString = 'Sensor Warm-up Time Left = %u minutes' % (timeLeftSeconds // 60)
                if sensorWarmupCountDown:
                    sensorWarmupCountDown.set_text(timeLeftString)
                else:
                    sensorWarmupCountDown = plt.figtext(.500, .18, timeLeftString,
                                                        backgroundcolor='pink',
                                                        size='xx-large', weight='bold',
                                                        horizontalalignment='center')
                # Say we only have 80 seconds left. We don't want to wait 5 minutes
                # before telling the user that we're ready for calibration, so we'll
                # restart the device reading sequence, with an initial delay of 80 seconds.
                if timeLeftSeconds < meterSamplingPeriod:
                    if rthread is not None:
                        if args.debug:
                            print 'calling restartDelay(firstDelaySecs=%u)' % timeLeftSeconds
                        rthread.restartDelay(firstDelaySecs=timeLeftSeconds)
                    else:
                        if args.debug:
                            print 'rthread is None'
            elif sensorWarmupCountDown:
                if args.debug:
                    print 'Writing Ready for calibrations message'
                sensorWarmupCountDown.set_text('Ready for calibrations')
            calibZoneList.append([startOfZone, lastx])
            tempRangeEnd = lastx
        else:
            if sensorWarmupCountDown:
                if args.debug:
                    print 'done with sensorWarmupCountDown'
                sensorWarmupCountDown.remove()
                sensorWarmupCountDown = None

        # Highlight any new out-of-calibration ranges
        redgen = (sr for sr in calibZoneList if mdates.date2num(sr[0]) not in redStartSet)
        for specRange in redgen:
            if temp_red_patch:
                #print 'deleting temp_red_patch ending at', tempRangeEnd
                temp_red_patch.remove()
                temp_red_patch = None
            #print 'Highlighting out of calibration range',specRange[0],' to',specRange[1]
            red_patch = ax.axvspan(mdates.date2num(specRange[0]),
                                   mdates.date2num(specRange[1]),
                                   alpha=0.2, color='red',
                                   label='Uncalibrated', zorder=2)
            if tempRangeEnd == lastx == specRange[1]:
                # This range is not necessarily completed yet.
                # Remember it so we can delete it later, if it
                # is to be replaced by a larger range.
                temp_red_patch = red_patch
            else:
                # add this to the list of ranges which have already been colored
                redStartSet.add(mdates.date2num(specRange[0]))
                redRegionList.append(red_patch)
                temp_red_patch = None


        #-----------------------------------------------------------
        # Find where we're in desirable range for 24 hours or more.
        # This implementation only adds new in range regions.
        # The only one we might need to erase and redraw is a
        # partial region which is increasing in size.
        #-----------------------------------------------------------
        inRangeList = []
        lastx = ReceiverTimeToUtcTime(firstTestSysSecs)
        lasty = firstTestGluc
        startOfZone = lastx
        tempRangeEnd = startOfZone
        for pointx, pointy in zip(xnorm, ynorm):
            if (glucInRange(lasty) is True) and (glucInRange(pointy) is False):
                # we've transitioned out desirable range
                if pointx - startOfZone >= datetime.timedelta(hours=24):
                    #print 'inRangeList[] adding ',startOfZone,'to',pointx
                    inRangeList.append([startOfZone, pointx])
            elif (glucInRange(lasty) is False) and (glucInRange(pointy) is True):
                # we've transitioned into desirable range
                startOfZone = pointx
            lastx = pointx
            lasty = pointy

        if glucInRange(lasty) is True:
            # We reached the end of the data points while still in
            # range, so add this final range.
            if lastx - startOfZone >= datetime.timedelta(hours=24):
                #print 'inRangeList[] adding ',startOfZone,'to',lastx
                inRangeList.append([startOfZone, lastx])
            tempRangeEnd = lastx

        # Highlight any in region ranges >= 24 hours
        inRangegen = (sr for sr in inRangeList if mdates.date2num(sr[0]) not in inRangeStartSet)
        for specRange in inRangegen:
            if temp_inRange_patch:
                temp_inRange_patch.remove()
                temp_inRange_patch = None
                temp_inRange_Arrow1.remove()
                temp_inRange_Arrow2.remove()
                temp_inRange_Arrow3.remove()
            #print 'Highlighting 24 hour or greater range', specRange[0], ' to', specRange[1]
            inRange_patch = ax.axvspan(mdates.date2num(specRange[0]),
                                       mdates.date2num(specRange[1]),
                                       0.0, 1.0, color='lightsteelblue',
                                       alpha=1.0, zorder=0)

            inRangeArrow1 = ax.annotate('', xy=(mdates.date2num(specRange[0]), gluMult * 325),
                                        xytext=(mdates.date2num(specRange[1]), gluMult * 325),
                                        xycoords='data', textcoords='data',
                                        arrowprops=dict(arrowstyle='|-|', color='red', linewidth=4),
                                        annotation_clip=False)
            inRangeArrow2 = ax.annotate('', xy=(mdates.date2num(specRange[0]), gluMult * 325),
                                        xytext=(mdates.date2num(specRange[1]), gluMult * 325),
                                        xycoords='data', textcoords='data',
                                        arrowprops=dict(arrowstyle='<->', color='red', linewidth=4),
                                        annotation_clip=False)

            xcenter = mdates.date2num(specRange[0]) + (mdates.date2num(specRange[1])-mdates.date2num(specRange[0]))/2
            inRangeDelta = specRange[1] - specRange[0]
            inRangeHours = inRangeDelta.days * 24 + inRangeDelta.seconds // 3600
            inRangeArrow3 = ax.annotate('%u hours in Target Range!' % inRangeHours,
                                        xy=(xcenter, gluMult * 340), ha='center',
                                        va='center', fontsize=22, annotation_clip=False)

            if tempRangeEnd == lastx == specRange[1]:
                # This range is not necessarily completed yet.
                # Remember it so we can delete it later, if it
                # is to be replaced by a larger range.
                temp_inRange_patch = inRange_patch
                temp_inRange_Arrow1 = inRangeArrow1
                temp_inRange_Arrow2 = inRangeArrow2
                temp_inRange_Arrow3 = inRangeArrow3
            else:
                # add this to the list of ranges which have already been colored
                inRangeStartSet.add(mdates.date2num(specRange[0]))
                inRangeRegionList.append(inRange_patch)
                inRangeRegionAnnotList.append(inRangeArrow1)
                inRangeRegionAnnotList.append(inRangeArrow2)
                inRangeRegionAnnotList.append(inRangeArrow3)
                temp_inRange_patch = None
                temp_inRange_Arrow1 = None
                temp_inRange_Arrow2 = None
                temp_inRange_Arrow3 = None


        #-----------------------------------------------------
        # Set point color to Magenta (Low), Cyan (Normal), or Red (High)
        kcolor = np.where(ynorm < gluMult * displayLow, 'magenta', np.where(ynorm > gluMult * displayHigh, 'red', 'cyan'))
        #-----------------------------------------------------

        displayStartSecs = int(firstTestSysSecs + (position / 100.0) *
                               max(lastTestSysSecs - firstTestSysSecs - displayRange, 0))
        displayStartDate = ReceiverTimeToUtcTime(displayStartSecs).astimezone(mytz)
        if posText:
            posText.set_text(displayStartDate.strftime("%Y-%m-%d"))

        if args.debug:
            print 'plotGraph() : Before plotting              count =', len(muppy.get_objects())

        # Set higher zorder to place scatter points on top of line drawing
        # Setting 'picker' allows us to handle hover events later on.
        if egvScatter:
            egvScatter.remove()
        egvScatter = ax.scatter([mdates.date2num(jj) for jj in xnorm], ynorm, s=15, c=kcolor, zorder=8, marker='o', picker=True)
        #if args.debug:
            #print 'plotGraph() : new size(egvScatter) =', len(muppy.get_objects())

        # Plot the calibration settings with a diamond marker
        if calibScatter:
            calibScatter.remove()
        calibScatter = ax.scatter([mdates.date2num(jj) for jj in cxnorm], cynorm, s=30, c='k', zorder=9, marker='D', picker=True)
        #if args.debug:
            #print 'plotGraph() : new size(calibScatter) =', len(muppy.get_objects())

        if linePlot:
            linePlot.pop(0).remove()
        linePlot = ax.plot(xnorm, ynorm, color='cornflowerblue', zorder=7)
        #if args.debug:
            #print 'After linePlot count =', len(muppy.get_objects())

        #========================================================================================
        # Plot a running mean as a dashed line

        # We only want to add data which has been added since the last time we ran through this code
        newYnorm = ynorm[xnorm > lastMeanTestDateTime]
        #print 'len(ynorm) =', len(ynorm), ', len(newYnorm) =', len(newYnorm),', nextMeanNn =',nextMeanNn
        nn = 0
        for nn, gluc in enumerate(newYnorm):
            if nextMeanNn == 0 and nn == 0:
                # There is no previous entry. The average, so far, is just this value.
                runningMean.append(float(ynorm[0]))
            else:
                runningMean.append(float((nextMeanNn + nn) * runningMean[nextMeanNn + nn - 1] + newYnorm[nn]) / (nextMeanNn + nn + 1))
        if meanPlot:
            meanPlot.pop(0).remove()
        meanPlot = ax.plot(xnorm, runningMean, color='firebrick', linewidth=1.0, linestyle='dashed', zorder=3, alpha=0.6)
        lastMeanTestDateTime = lastTestDateTime
        if len(newYnorm) > 0:
            nextMeanNn = nextMeanNn + nn + 1
        #========================================================================================

        #if args.debug:
            #print 'plotGraph() :  After plots count =', len(muppy.get_objects())
            #print '++++++++++++++++++++++++++++++++++++++++++++++++\n'
            #tr.print_diff()

        #=======================================================
        # Annotate the plot with user events and notes
        #=======================================================
        ShowOrHideEventsNotes()
        #if args.debug:
            #print 'After ShowOrHideEventsNotes count =', len(muppy.get_objects())

    #if args.debug:
        #print 'Before legend count =', len(muppy.get_objects())
    if leg is None:
        # We want to make sure that the Legend is fully visible. The user can drag
        # it to a location which causes it to partially outside the figure space.
        # If we detect this the next time we start up, we'll move it back to the
        # default position.
        #
        # On 1920 x 1080 screen,
        #
        #           (legPosX+0.1394,legPosY+0.1183)
        #         +----------------+
        #         |                |
        #         |     Legend     |
        #         |                |
        #         +----------------+
        # (legPosX,legPosY)

        if legPosX < 0 or legPosX > (1.0 - 0.14) or legPosY < 0.1 or legPosY > (1.0 - 0.12):
            if args.debug:
                print 'Out of range Legend', (legPosX, legPosY), ' moved to', (legDefaultPosX, legDefaultPosY)
            legPosX = legDefaultPosX
            legPosY = legDefaultPosY

        if desirableRange and red_patch and calibScatter and egvScatter and meanPlot:
            # Add a legend. fontsize = [xx-small, x-small, small, medium, large, x-large, xx-large]
            leg = fig.legend((egvScatter, calibScatter, red_patch, desirableRange, meanPlot[0]),
                             ("Glucose values", "User Calibrations", "Sensor Uncalibrated", "Target Range", "Mean Glucose"),
                             scatterpoints=1, loc=(legPosX, legPosY), fontsize='small')
            if leg:
                # set the legend as a draggable entity
                leg.draggable(True)

    #if args.debug:
        #print 'After legend count =', len(muppy.get_objects())

    #if args.debug:
        #print 'plotGraph() :  After legend count =', len(muppy.get_objects())
        #print '++++++++++++++++++++++++++++++++++++++++++++++++\n'
        #tr.print_diff()

    if gluUnits == 'mmol/L':
        avgText.set_text('Latest = %5.2f (mmol/L)\nAvg = %5.2f (mmol/L)\nStdDev = %5.2f\nHbA1c = %5.2f'
                         %(gluMult * lastTestGluc, gluMult * avgGlu, gluMult * egvStdDev, hba1c))
    else:
        avgText.set_text('Latest = %u (mg/dL)\nAvg = %5.2f (mg/dL)\nStdDev = %5.2f\nHbA1c = %5.2f'
                         %(lastTestGluc, avgGlu, egvStdDev, hba1c))

    if lastTrend == 1:     # doubleUp
        trendRot = 90.0
    elif lastTrend == 2:   # singleUp
        trendRot = 60.0
    elif lastTrend == 3:   # fortyFiveUp
        trendRot = 30.0
    elif lastTrend == 4:   # flat
        trendRot = 0.0
    elif lastTrend == 5:   # fortyFiveDown
        trendRot = -30.0
    elif lastTrend == 6:   # singleDown
        trendRot = -60.0
    elif lastTrend == 7:   # doubleDown
        trendRot = -90.0
    else:                  # none (0) | notComputable (8) | rateOutOfRange (9)
        trendRot = 360.0

    if trendRot < 360.0:
        trendArrow.set_rotation(trendRot)
    #+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

    if args.debug:
        print 'plotGraph() : Before displayCurrentRange() count =', len(muppy.get_objects())

    displayCurrentRange()

    # Enable the following to print out the lower left X & Y position
    # and the width and height of the Legend in figure coordinates (0.0 - 1.0)
    if False:
        if args.debug and leg:
            lframe = leg.get_frame()
            lx, ly = lframe.get_x(), lframe.get_y()
            lw, lh = lframe.get_width(), lframe.get_height()
            legxy = fig.transFigure.inverted().transform((lx, ly))
            legwh = fig.transFigure.inverted().transform((lw, lh))
            # If the legend hasn't been plotted yet, you can get odd values. For example:
            #   Legend (X,Y) = [0. 0.] , (W,H) = [0.00068966 0.00117647]
            # so filter such entries out.
            if legxy[0] > 0.01 or legxy[1] > 0.01:
                print 'Legend (X,Y) =', legxy, ', (W,H) =', legwh

    if args.debug:
        print 'plotGraph() :  After displayCurrentRange() count =', len(muppy.get_objects())
        print '++++++++++++++++++++++++++++++++++++++++++++++++\n'
        tr.print_diff()

# end of plotGraph()

fig.canvas.mpl_connect('pick_event', onpick)
fig.canvas.mpl_connect('close_event', onclose)
fig.canvas.mpl_connect('axes_leave_event', leave_axes)


sqlite_file = getSqlFileName(None)
if args.debug:
    print 'sqlite_file =', sqlite_file
firstPlotGraph = 1
plotInit()
PerodicDeviceSeek()  # launch thread to check for device presence every few minutes
time.sleep(2)  # give time for the seek thread to find a device
plotGraph()

plt.show()  # This hangs until the user closes the window
#print 'returned from plt.show()'

#-----------------------------------------------------
#
# |<-----------------maxRangeSecs----------------------->|
# |                                                      |
# firstTestSysSecs                                    lastTestSysSecs
#               +================================+
#               |                                |
#               |    <--displaySecs-->           |
#               | +-------------------+          |
#               | |                   |          |
# 0       1000  | |  2000      3000   |   4000   |  5000
#               | |                   |          |
#               | +-------------------+          |
#               |<......... slider range .......>|
#               |                                |
#               +================================+
#		^				 ^
#               |                                |
#               +------ sql retieve range -------+
#               |                                |
#            sqlMinTime                       sqlMaxTime
#
# <------------------- maxRangeSecs ------------------->
#
# slide (0.0 ... 1.0) ===>  dispTestNum
#		+- sqlMinTime        sqlMaxTime -+

sys.exit(0)
