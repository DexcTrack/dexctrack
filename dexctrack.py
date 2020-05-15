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

# Support python3 print syntax in python2
from __future__ import print_function

import os
import sys
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
from matplotlib.widgets import TextBox
import numpy as np

import readReceiver
import constants
import screensize


dexctrackVersion = 3.3

# If a '-d' argument is included on the command line, we'll run in debug mode
parser = argparse.ArgumentParser()
parser.add_argument("-d", "--debug", help="enable debug mode", action="store_true")
parser.add_argument("-v", "--version", help="show version", action="store_true")
# Use -x <width> -y <height> to hard code the window size. This is useful for
# testing different window dimensions. When both are specified, we'll skip the
# code which maximizes the window.
parser.add_argument("-x", "--xsize", help="specify width in pixels", type=int)
parser.add_argument("-y", "--ysize", help="specify height in pixels", type=int)
parser.add_argument("databaseFile", nargs='?', help="optionally specified database file", type=str)
args = parser.parse_args()

mytz = tzlocal.get_localzone()

#==========================================================================================
#
# The matplotlib library has a bug which causes problems when trying to drag objects.
# If you drag one object, and then try to drag a different object, often the first
# selected object will get accidentally included in the second drag operation.
# This makes it difficult to reposition User Event strings and User Note strings.
#
# A fix for this bug was submitted 2017-01-20 by fukatani, but his|her
# code has not yet been pulled into an official matplotlib release.
#
#   https://github.com/matplotlib/matplotlib/pull/7894
#
# The 3 methods defined below are replacements for the original matplotlib methods.
#
# Thanks to fukatani for this awesome fix!
#
#==========================================================================================

def off_drag_new_init(self, ref_artist, use_blit=False):
    #print ('running off_drag_new_init()')
    self.ref_artist = ref_artist
    self.got_artist = False
    self.got_other_artist = False

    self.canvas = self.ref_artist.figure.canvas
    self._use_blit = use_blit and self.canvas.supports_blit

    c2 = self.canvas.mpl_connect('pick_event', self.on_pick)
    c3 = self.canvas.mpl_connect('button_release_event', self.on_release)

    ref_artist.set_picker(self.artist_picker)
    self.cids = [c2, c3]

def off_drag_on_pick(self, evt):
    #print ('running off_drag_on_pick()')
    if self.got_other_artist:
        return
    if self.got_artist or evt.artist == self.ref_artist:

        self.mouse_x = evt.mouseevent.x
        self.mouse_y = evt.mouseevent.y
        self.got_artist = True

        if self._use_blit:
            self.ref_artist.set_animated(True)
            self.canvas.draw()
            self.background = self.canvas.copy_from_bbox(
                self.ref_artist.figure.bbox)
            self.ref_artist.draw(self.ref_artist.figure._cachedRenderer)
            self.canvas.blit(self.ref_artist.figure.bbox)
            self._c1 = self.canvas.mpl_connect('motion_notify_event',
                                               self.on_motion_blit)
        else:
            self._c1 = self.canvas.mpl_connect('motion_notify_event',
                                               self.on_motion)
        self.save_offset()
    else:
        self.got_other_artist = True

def off_drag_on_release(self, event):
    #print ('running off_drag_on_release()')
    self.got_other_artist = False
    if self.got_artist:
        self.finalize_offset()
        self.got_artist = False
        self.canvas.mpl_disconnect(self._c1)

        if self._use_blit:
            self.ref_artist.set_animated(False)

# Replace the broken original methods with fukatani's fixed versions
mpl.offsetbox.DraggableBase.__init__ = off_drag_new_init
mpl.offsetbox.DraggableBase.on_pick = off_drag_on_pick
mpl.offsetbox.DraggableBase.on_release = off_drag_on_release

#========================================================================================
#  The default implementation of artist_picker() has 2 issues which need to be overcome.
#========================================================================================
def draggable_anot_picker(self, artist, mouse_evt):
    ann = self.annotation
    if ann:
        # --------------------------------------------------------------------------------
        #   When looking for matching annotations, the default picker routine uses Display
        # coordinates. Unfortunately, the transformation from Data coordinates to Display
        # coordinates places EVERY annotation within the current display. So, even
        # annotations which are not currently visible on the screen can get accidentally
        # selected and dragged when the user is trying to drag an annotation which is
        # visible.
        #
        #   To fix this bug, we'll use the view limits of the current display to
        # filter out any annotation whose Data coordinates are outside those limits.
        # --------------------------------------------------------------------------------
        # Test whether the annotation is on the currently displayed axes view
        if (ann.axes.viewLim.x0 <= ann.xy[0] <= ann.axes.viewLim.x1) and \
           (ann.axes.viewLim.y0 <= ann.xy[1] <= ann.axes.viewLim.y1):
            pass
        else:
            return False, {}


        # --------------------------------------------------------------------------------
        #   If there are two or more annotations located near each other, the default
        # selection area for one annotation can completely eclipse another annotation.
        # For example:
        #
        #           'Annotation A Long String'
        #           /                        .
        #          /    'Annotation B'       .
        #          |   /             .       .
        #          |   |             . bbox  .
        #          |   V . . . . . . .       . bbox
        #          V . . . . . . . . . . . . .
        #
        #   The default selection area is the (bbox) rectangle including the entire arrow
        # and the text string. If the user is trying to drag 'Annotation B' and clicks the
        # mouse on top of that string, both 'Annotation A Long String' and 'Annotation B'
        # are within the selection group. If we're using fukatani's fix, then only the
        # randomly ordered, "first" of these elements in the group will be dragged. If
        # 'Annotation A Long String' is that first one, then the user will be unable to
        # drag 'Annotation B'. When they try to drag it, 'Annotation A Long String'
        # will move instead.
        #
        #   To fix this issue, we'll switch the selection area to a rectangle including
        # just the text string. The _get_xy_display() method provides the position of
        # the lower left corner of the string. The _get_rendered_text_width() method
        # provides the width, and get_size() provides the height.
        #
        #          ............................
        #          .'Annotation A Long String'.
        #          ./..........................
        #          /
        #          |   ................
        #          |   .'Annotation B'.
        #          |   /...............
        #          |   |
        #          |   V
        #          V
        #
        #   If the user clicks on 'Annotation B', the mouse will be within that
        # text string, but outside of 'Annotation A Long String'. This greatly
        # reduces the area of possible collision.
        # --------------------------------------------------------------------------------

        # Find the location of the Text part of the annotation in Display coordinates
        #                +-----------------+ textX1,textY1
        #                | Annotation Text |
        #  textX0,textY0 +-----------------+
        textX0, textY0 = ann._get_xy_display()
        try:
            textX1 = textX0 + ann._get_rendered_text_width(ann.get_text())
        except TypeError:
            textX1 = textX0
            if sys.version_info < (3, 0):
                sys.exc_clear()

        if textX1 == textX0:
            # Annotation Text is empty, so don't require the mouse position
            # to be within the text area.
            pass
        else:
            textY1 = textY0 + ann.get_size()
            # Test whether the mouse is within the Annotation Text area
            if (textX0 <= mouse_evt.x <= textX1) and \
               (textY0 <= mouse_evt.y <= textY1):
                pass
            else:
                return False, {}
        return self.ref_artist.contains(mouse_evt)
    else:
        return False, {}

# For annotations, replace the default artist_picker method with a better one
mpl.offsetbox.DraggableAnnotation.artist_picker = draggable_anot_picker

#==========================================================================================


def new_da_finalize_offset(self):
    ann = self.annotation
    self.fx, self.fy = ann.get_transform().transform(ann.xyann)
    #print ('new_da_finalize_offset(): ox =', self.ox, ', oy =', self.oy, ', fx =', self.fx, ', fy =', self.fy)
    #print ('x = %s' % mdates.num2date(ann.xy[0], tz=mytz), ', y =', ann.xy[1])
    if (self.fx != self.ox) or (self.fy != self.oy):
        #print (ann, 'Annotation moved')
        saveAnnToDb(ann)
    #else:
        #print (ann, 'Annotation unmoved')

mpl.offsetbox.DraggableAnnotation.finalize_offset = new_da_finalize_offset

#==========================================================================================


if args.version:
    print ('Version =', dexctrackVersion)
    sys.exit(0)

specDatabase = None
if args.databaseFile:
    # abspath() will normalize path navigation elements like '~/' or '../'
    specDatabase = os.path.abspath(args.databaseFile)
    print ('Specified Database =', specDatabase)
    if not os.path.exists(specDatabase):
        print ("Specified database file '%s' does not exist" % specDatabase)
        sys.exit(2)

if args.debug:
    from pympler import muppy
    from pympler import tracker

print ('DexcTrack  Copyright (C) 2018  Steve Erlenborn')
print ('This program comes with ABSOLUTELY NO WARRANTY.\n')

# HD monitor  = 1920 x 1080 -> 1920/1080 = 1.78
# small laptop  1366 x  768 -> 1366/ 768 = 1.78
# macbook pro = 1440 x 900  -> 1440/900  = 1.6
#               1280 x 1024 -> 1280/1024 = 1.25
if args.xsize and args.ysize:
    width = args.xsize
    height = args.ysize
else:
    width, height = screensize.get_screen_size()
dispRatio = round(float(width) / float(height), 1)
if args.debug:
    print ('get_screen_size width =', width, ', get_screen_size height =', height, ', dispRatio =', dispRatio)

# Use the fivethirtyeight style, if it's available
# To find explicit Exception type use ...
#except Exception as e:
#    print ('Exception type =', type(e).__name__)
try:
    style.use('fivethirtyeight')
except IOError as e:
    print ('Exception =', e)
    style.use('ggplot')
    if sys.version_info < (3, 0):
        sys.exc_clear()

#####################################################################################################################
# The following variables are set for G4, G5, or G6 devices. They might need to be altered for others.
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
sliderSpace = 0.24              # reserve this much space below the graph to hold our 2 sliders
powerState = None
lastPowerState = None
powerLevel = 0
lastPowerLevel = 0

# Constants for use in SQL retrieve operations. We'll collect data
# for (ninetyDaysInSeconds + bufferSeconds) at a time.
ninetyDaysInSeconds = 60*60*24*90
bufferSeconds = 60*60*24*15
hourSeconds = 60*60

graphHeightInFigure = graphTop - graphBottom
UTC_BASE_TIME = datetime.datetime(2009, 1, 1, tzinfo=pytz.UTC)
readSerialNumInstance = None
readDataInstance = None
ax = None
tr = None
firstTestSysSecs = 0
lastTestSysSecs = 0
lastTestGluc = 0
lastTestDateTime = UTC_BASE_TIME
displayStartSecs = 0
displayEndSecs = 0
cfgDisplayLow = None
cfgDisplayHigh = None
rthread = None
sthread = None
stat_text = None
batt_text = None
serialNum = None
sPos = None
avgText = None
trendArrow = None
hba1c = 0.0
egvStdDev = 0.0
lastRealGluc = 0
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
calibDict = {}
noteTimeSet = set()
leg = None
legPosX = -1.0
legPosY = -1.0
restart = False
sqlEarliestGluc = 0
sqlMaximumGluc = 0
avgGlu = 0
axNote = None
noteBox = None
noteBoxPos = None
axTgtLow = None
tgtLowBox = None
axTgtHigh = None
tgtHighBox = None
noteArrow = None
noteText = ''
oldNoteText = ''
oldNoteXoff = 0.0
oldNoteYoff = 0.0
noteLoc = None
submit_note_id = None
submit_tgtLow_id = None
submit_tgtHigh_id = None
trendChar = '-'
gluMult = 1.0
axPos = None
posText = None
axScale = None
scaleText = None
sScale = None
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
largeFontSize = 'large'
mediumFontSize = 'medium'
smallFontSize = 'small'
percentFontSize = largeFontSize
trendArrowSize = 15
battX = 0.946
battY = 0.10
curSqlMinTime = 0
curSqlMaxTime = 0
# Can we append new readings to the database?
# We'll only allow appending to a db matching a currently attached device.
appendable_db = True
disconTimerEnabled = True
unitRead = None
#unitButton = None
newRange = True
disconUtcTime = datetime.datetime.min
disconText = None
# Number of digits to display after the decimal point for Target Range values
tgtDecDigits = 0
dayRotation = 30


# Sometimes there's a failure running under Windows. If this happens before
# the graphics window has been set up, then there's no simple
# way to terminate the program. Ctrl-C gets ignored, by default.
# Here we set up a handler for Ctrl-C, which we'll use under Windows.
def CtrlCHandler(signum, frame):
    print ('Exiting due to Ctrl-C')
    sys.exit(1)

# Linux & Mac automatically handle Ctrl-C, but for Windows
# we need to set up a specific handler
if sys.platform == "win32":
    import signal
    signal.signal(signal.SIGINT, CtrlCHandler)

# Disable toolbar which appears in some backends
plt.rcParams['toolbar'] = 'None'

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

displayStartDate = datetime.datetime.now(mytz)

# We want to display dates in the local timezone
plt.rcParams['timezone'] = mytz


plt.rcParams['axes.axisbelow'] = False

dotsPerInch = plt.rcParams['figure.dpi']
if args.xsize and args.ysize:
    xinches = float(args.xsize) / dotsPerInch
    yinches = float(args.ysize) / dotsPerInch
else:
    xinches = 14.5
    yinches = 8.5

#print ('interactive backends =',mpl.rcsetup.interactive_bk)
#print ('non_interactive backends =',mpl.rcsetup.non_interactive_bk)

# Start with a figure size corresponding to any given screen dimensions,
# or the default for a 15 inch laptop.
# Note that this will be overridden below, for most backends, by
# instructions to maximize the window size on a monitor.
fig = plt.figure("DexcTrack", figsize=(xinches, yinches))
figManager = plt.get_current_fig_manager()

backend = plt.get_backend()
if args.debug:
    print ('sys.platform =', sys.platform)
    print ('backend =', backend)
if args.xsize and args.ysize:
    pass
else:
    if 'Tk' in backend:
        if sys.platform == "win32":
            # On Windows, we can get max size, without the taskbar, by zooming
            figManager.window.state('zoomed')
        else:
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
# If this routine gets called from plotGraph, set the
# calledFromPlotGraph to True to avoid recursion.
def SetCurrentSqlSelectRange(calledFromPlotGraph=False):
    global curSqlMinTime
    global curSqlMaxTime
    global newRange
    global displayEndSecs
    global displayStartSecs

    # Check to see if the new display range will fall outside of the previous
    # SQL retrieve range. If so, then we'll update the SQL retrieve range and
    # cause a new read from the SQL database.

    # |<-----------------------------------maxRangeSecs----------------------------------------->|
    # |                                                                                          |
    # firstTestSysSecs                                                             lastTestSysSecs
    #
    #         <--displayRange-->            <--displayRange-->                 <--displayRange-->
    #       +-------------------+         +-------------------+              +-------------------+
    #       |                   |         |                   |              |                   |
    # 0     | 1000       2000   |  3000   |   4000      5000  |    6000      |7000   |   8000    |
    #       |                   |         |                   |              |                   |
    #       +-------------------+         +-------------------+              +-------------------+
    #       ^                   ^         ^                   ^              ^                   |
    #       |                   |         |                   |              |                   |
    #       +-displayStartSecs  |         +-displayStartSecs  |              +-displayStartSecs  |
    #                           |                             |                                  |
    #            displayEndSecs-+              displayEndSecs-+                   displayEndSecs-+
    # ^                                ^
    # |                                |
    # +------ sql retrieve range ------+
    # |                                |
    # curSqlMinTime                    curSqlMaxTime

    displayStartSecs = int(firstTestSysSecs + (position / 100.0) *
                           max(lastTestSysSecs - firstTestSysSecs - displayRange, 0))
    displayEndSecs = min(displayStartSecs + displayRange, lastTestSysSecs)

    if (displayStartSecs < curSqlMinTime) or (displayEndSecs > curSqlMaxTime):
        # the range of data we need is outside of the last retrieved one
        curSqlMinTime = max(displayEndSecs - ninetyDaysInSeconds - bufferSeconds, firstTestSysSecs)
        curSqlMaxTime = min(max(displayEndSecs + bufferSeconds, curSqlMinTime + ninetyDaysInSeconds + bufferSeconds), lastTestSysSecs)
        #qtime = ReceiverTimeToUtcTime(curSqlMinTime)
        #rtime = ReceiverTimeToUtcTime(curSqlMaxTime)
        newRange = True
        #print ('SetCurrentSqlSelectRange(): newRange =', newRange)
        #print ('SetCurrentSqlSelectRange(', curSqlMinTime, ',', curSqlMaxTime, ') : curSqlMinTime =', qtime.astimezone(mytz), ', curSqlMaxTime =', rtime.astimezone(mytz))
        if calledFromPlotGraph is False:
            #print ('SetCurrentSqlSelectRange : Calling plotGraph()')
            plotGraph()

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
    #print (months,'months, ',weeks,'weeks, ',days,'days, ',hours,'hours, ',minutes,'minutes')

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

    if months != 0:
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
    global displayEndSecs
    #print ('displayRange =',displayRange,', displayStartSecs =',displayStartSecs,', displayStartSecs+displayRange =',displayStartSecs+displayRange,', lastTestSysSecs =',lastTestSysSecs)

    #   +--------------------+--------------------------------------------------------+
    #   |                    |********************************************************|
    #   | <- displayRange -> |********************************************************|
    #   |                    |********************************************************|
    #   +--------------------+--------------------------------------------------------+
    #   |                    |                                                        |
    #   displayStartSecs     displayStartSecs+displayRange                            lastTestSysSecs
    #                        displayEndSecs

    #   +--------------------------+--------------------+-----------------------------+
    #   |**************************|                    |*****************************|
    #   |**************************| <- displayRange -> |*****************************|
    #   |**************************|                    |*****************************|
    #   +--------------------------+--------------------+-----------------------------+
    #   |                          |                    |                             |
    #   firstTestSysSecs           displayStartSecs     displayStartSecs+displayRange lastTestSysSecs
    #                                                   displayEndSecs

    #   +-----------------------------------------------------------------------------+
    #   |********************************************************|                    |
    #   |********************************************************| <- displayRange -> |
    #   |********************************************************|                    |
    #   +-----------------------------------------------------------------------------+
    #   |                                                        |                    |
    #   firstTestSysSecs                                         displayStartSecs     displayStartSecs+displayRange
    #                                                                                 lastTestSysSecs
    #                                                                                 displayEndSecs

    if (displayStartSecs + displayRange) > lastTestSysSecs:
        # there isn't enough data to fill out displayRange
        if (displayStartSecs - displayRange) < firstTestSysSecs:
            dispBegin = firstTestSysSecs
        else:
            dispBegin = max(lastTestSysSecs - displayRange, firstTestSysSecs)
        displayEndSecs = lastTestSysSecs
    else:
        dispBegin = displayStartSecs
        displayEndSecs = displayStartSecs + displayRange
    #print ('displayCurrentRange() displayStartSecs =',displayStartSecs,'displayRange =',displayRange,'dispBegin =',dispBegin,'displayEndSecs =',displayEndSecs)
    if displayEndSecs > dispBegin:
        try:
            # the following can cause 'RuntimeError: dictionary changed size during iteration'
            ax.set_xlim(mdates.date2num(ReceiverTimeToUtcTime(dispBegin)),
                        mdates.date2num(ReceiverTimeToUtcTime(displayEndSecs)))
            #if args.debug:
                #print ('displayCurrentRange() before fig.canvas.draw_idle(), count =',len(muppy.get_objects()))
            fig.canvas.draw_idle()   # each call generates new references to 120 - 300 objectss
            #if args.debug:
                #print ('displayCurrentRange() after fig.canvas.draw_idle(), count =',len(muppy.get_objects()))
                #tr.print_diff()
        except RuntimeError as e:
            print ('displayCurrentRange() : dispBegin =', dispBegin, ', displayEndSecs =', displayEndSecs, ', Exception =', e)
            if sys.version_info < (3, 0):
                sys.exc_clear()

#---------------------------------------------------------
def getSqlFileName(sNum):
    global serialNum
    global appendable_db
    global disconTimerEnabled

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
            serialNum = my_sqlite_file.replace(sqlprefix, '').replace('.sqlite', '')
            #if args.debug:
                #print ('getSqlFileName(None) : No device connected, defaulting to %s' % my_sqlite_file)
        else:
            my_sqlite_file = None
            serialNum = None
        appendable_db = False
    else:
        my_sqlite_file = '%s%s.sqlite' % (sqlprefix, sNum)
        serialNum = sNum
        appendable_db = True

    # A specified database overrides the value determined above
    if specDatabase:
        if appendable_db and my_sqlite_file and (specDatabase != my_sqlite_file):
            appendable_db = False

        disconTimerEnabled = my_sqlite_file and (specDatabase == my_sqlite_file)

        my_sqlite_file = specDatabase
        serialNum = string.replace(string.replace(specDatabase, sqlprefix, ''), '.sqlite', '')

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
            print ('deviceReadThread launched at', datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    def stop(self):
        self.restart = False
        self.evobj.set()
        if args.debug:
            print ('Turning off device read thread at', datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    # This function will cause termination of the current delay
    # sequence, and start of a new one, optionally beginning with
    # a given length for the first delay.
    def restartDelay(self, firstDelaySecs=meterSamplingPeriod):
        self.restart = True
        self.firstDelayPeriod = firstDelaySecs
        self.evobj.set()
        if args.debug:
            print ('Restarting device read delay. First delay =', firstDelaySecs)

    def run(self):
        global readDataInstance
        global lastRealGluc
        global lastTrend
        while True:
            if self.restart is True:
                self.restart = False
            else:
                if stat_text:
                    stat_text.set_text('Reading\nReceiver\nDevice')
                    stat_text.set_backgroundcolor('yellow')
                    stat_text.draw(fig.canvas.get_renderer())

                if args.debug:
                    print ('Reading device at', datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

                if sqlite_file is not None:
                    if appendable_db:
                        # We probably have new records to add to the database
                        self.readIntoDbFunc(sqlite_file)
                    else:
                        if readDataInstance is None:
                            readDataInstance = getReadDataInstance()
                        if readDataInstance:
                            curGluc, curFullTrend = readDataInstance.GetCurrentGlucoseAndTrend()
                            if curGluc and curFullTrend:
                                lastRealGluc = curGluc
                                lastTrend = curFullTrend & constants.EGV_TREND_ARROW_MASK
                            else:
                                lastRealGluc = 0
                        else:
                            lastRealGluc = 0
                            #print ('deviceReadThread.run() readDataInstance = NULL')

                    if stat_text:
                        stat_text.set_text('Receiver\nDevice\nPresent')
                        stat_text.set_backgroundcolor('tomato')
                        stat_text.draw(fig.canvas.get_renderer())

                    plotGraph()    # Draw a new graph

            if self.firstDelayPeriod != 0:
                mydelay = float(self.firstDelayPeriod)
                if args.debug:
                    print ('Setting timeout delay to', mydelay)
                self.firstDelayPeriod = 0
                waitStatus = self.evobj.wait(timeout=mydelay)   # wait up to firstDelayPeriod seconds
            else:
                waitStatus = self.evobj.wait(timeout=meterSamplingPeriod)

            # waitStatus = False on timeout, True if someone set() the event object
            if waitStatus is True:
                if self.restart is True:
                    #if args.debug:
                        #print ('deviceReadThread restart requested')
                    self.evobj.clear()
                else:
                    if args.debug:
                        print ('deviceReadThread terminated')
                    lastRealGluc = 0
                    if sys.platform != "win32":
                        try:
                            # During shutdown, set_window_title() can fail with
                            # "AttributeError: 'NoneType' object has no attribute 'wm_title'"
                            fig.canvas.set_window_title('DexcTrack: %s' % (serialNum))
                        except AttributeError as e:
                            #if args.debug:
                                #print ('deviceReadThread.run() fig.canvas.set_window_title: Exception =', e)
                            if sys.version_info < (3, 0):
                                sys.exc_clear()

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
        self.evobj = threading.Event()
        #if args.debug:
            #print ('deviceSeekThread launched, threadID =', threadID)

    def stop(self):
        self.evobj.set()
        if args.debug:
            print ('Turning off device seek thread at', datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    def run(self):
        while True:
            global sqlite_file
            global rthread
            global restart
            global readSerialNumInstance
            global powerState
            global powerLevel
            global lastPowerState
            global lastPowerLevel
            global batt_text
            global disconUtcTime
            global disconText

            prior_sqlite_file = sqlite_file
            prior_connected_state = self.connected_state
            sNum = None
            if readSerialNumInstance is None:
                dport = readReceiver.readReceiverBase.FindDevice()
                if dport is not None:
                    readSerialNumInstance = readReceiver.readReceiver(dport)
                self.connected_state = False

            if readSerialNumInstance is not None:
                (powerState, powerLevel) = readSerialNumInstance.GetPowerInfo()
                sNum = readSerialNumInstance.GetSerialNumber()
                if not sNum:
                    self.connected_state = False
                    del readSerialNumInstance
                    readSerialNumInstance = None
                    (powerState, powerLevel) = (None, 0)
                else:
                    self.connected_state = True

                sqlite_file = getSqlFileName(sNum)
            else:
                (powerState, powerLevel) = (None, 0)

            if disconTimerEnabled is True:
                if disconUtcTime != datetime.datetime.min:
                    disconDelta = datetime.datetime.utcnow() - disconUtcTime
                    disconMinutes = disconDelta.total_seconds() // 60
                    if disconMinutes > 0:
                        # Show how long the Receiver has been disconnected
                        if disconText:
                            disconText.set_text('%d minutes' % disconMinutes)
                        else:
                            disconText = plt.figtext(.10, .10, '%d minutes' % disconMinutes,
                                                     size=largeFontSize, weight='bold')
                        plt.draw()
                else:
                    if disconText:
                        disconText.remove()
                        disconText = None

            #if args.debug:
                #print ('deviceSeekThread.run() at', datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

            #print ('deviceSeekThread.run() connected_state =', self.connected_state, ', prior_connected_state =', prior_connected_state, ', sqlite_file =', sqlite_file, ', prior_sqlite_file =', prior_sqlite_file)
            if (self.connected_state != prior_connected_state) or (sqlite_file != prior_sqlite_file):
                #if args.debug:
                    #print ('Connected state :', prior_connected_state,' -> ',self.connected_state)
                if not sNum:
                    disconUtcTime = datetime.datetime.utcnow()
                    if rthread is not None:
                        # stop trying to read the missing device
                        rthread.stop()
                        rthread.join()
                        rthread = None
                    if stat_text:
                        stat_text.set_text('Receiver\nDevice\nAbsent')
                        stat_text.set_backgroundcolor('thistle')
                        stat_text.draw(fig.canvas.get_renderer())
                    if batt_text:
                        batt_text.remove()
                        batt_text = None
                        (powerState, powerLevel) = (None, 0)
                        (lastPowerState, lastPowerLevel) = (None, 0)
                    plt.draw()
                else:
                    # A different device has been connected
                    disconUtcTime = datetime.datetime.min
                    if disconText:
                        # Fade the text before complete removal
                        disconText.set_alpha(0.5)

                    if rthread is not None:
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
                    print ('deviceSeekThread terminated')
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
def getReadDataInstance():
    rsni = None
    rdi = None

    my_dport = readReceiver.readReceiverBase.FindDevice()
    if readSerialNumInstance:
        rsni = readSerialNumInstance
        devType = rsni.GetDeviceType()
    else:
        devType = None
        if my_dport is not None:
            rsni = readReceiver.readReceiver(my_dport)
            if rsni:
                devType = rsni.GetDeviceType()

    if my_dport:
        if rsni:
            if devType and my_dport:
                if devType == 'g4':
                    rdi = readReceiver.readReceiver(my_dport, rsni.port)
                elif devType == 'g5':
                    rdi = readReceiver.readReceiverG5(my_dport, rsni.port)
                elif devType == 'g6':
                    rdi = readReceiver.readReceiverG6(my_dport, rsni.port)
                else:
                    print ('getReadDataInstance() : Unrecognized firmware version', devType)
        else:
            rdi = readReceiver.readReceiver(my_dport)

    return rdi

#---------------------------------------------------------
def PeriodicReadData():
    global rthread
    global readDataInstance
    global lastRealGluc
    global lastTrend

    if readDataInstance is None:
        readDataInstance = getReadDataInstance()

    if readDataInstance is None:
        if rthread is not None:
            rthread.stop()
            rthread.join()
        return

    if appendable_db is False:
        curGluc, curFullTrend = readDataInstance.GetCurrentGlucoseAndTrend()
        if curGluc and curFullTrend:
            lastRealGluc = curGluc
            lastTrend = curFullTrend & constants.EGV_TREND_ARROW_MASK

    if rthread is not None:
        rthread.stop()
        rthread.join()
    rthread = deviceReadThread(1, "Periodic read thread", readDataInstance.DownloadToDb)
    # If the user closes the window, we want this thread to also terminate
    rthread.daemon = True
    rthread.start()
    return

#---------------------------------------------------------
def updatePos(val):
    global displayStartDate
    global position

    position = val
    origDisplayStartSecs = displayStartSecs
    SetCurrentSqlSelectRange() # this may modify displayStartSecs, displayEndSecs, curSqlMinTime, curSqlMaxTime
    if posText:
        displayStartDate = ReceiverTimeToUtcTime(displayStartSecs).astimezone(mytz)
        posText.set_text(displayStartDate.strftime("%Y-%m-%d"))
    if displayStartSecs != origDisplayStartSecs:
        calcStats()
        displayCurrentRange()

#---------------------------------------------------------
def updateScale(val):
    global displayRange
    global displayStartDate
    global minorTickSequence

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

    SetCurrentSqlSelectRange() # this may modify displayStartSecs, displayEndSecs, curSqlMinTime, curSqlMaxTime
    displayStartDate = ReceiverTimeToUtcTime(displayStartSecs).astimezone(mytz)
    if posText:
        posText.set_text(displayStartDate.strftime("%Y-%m-%d"))
    if scaleText:
        scaleText.set_text(SecondsToGeneralTimeString(displayRange))
    ShowOrHideEventsNotes()
    calcStats()
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
    global displayEndSecs

    #print('press', event.key)
    sys.stdout.flush()

    origDisplayStartSecs = displayStartSecs
    origPosition = position

    if event.inaxes is axNote:
        # When we're in the Note entry box, 'left' and 'right' are to be used for
        # editing purposes. We don't want those keys to cause data display adjustments.
        pass
    elif event.inaxes is axTgtLow:
        # When we're in the Target Low entry box, 'left' and 'right' are to be used for
        # editing purposes. We don't want those keys to cause data display adjustments.
        pass
    elif event.inaxes is axTgtHigh:
        # When we're in the Target Low entry box, 'left' and 'right' are to be used for
        # editing purposes. We don't want those keys to cause data display adjustments.
        pass
    else:
        if event.key == 'left':         # shift one screen left
            displayStartSecs = max(firstTestSysSecs, displayStartSecs - displayRange)

        elif event.key == 'right':      # shift one screen right
            displayStartSecs = max(firstTestSysSecs, min(lastTestSysSecs - displayRange, displayStartSecs + displayRange))

        elif event.key == 'alt+left':   # shift one hour left
            displayStartSecs = max(firstTestSysSecs, displayStartSecs - hourSeconds)

        elif event.key == 'alt+right':  # shift one hour right
            displayStartSecs = max(firstTestSysSecs, min(lastTestSysSecs - displayRange, displayStartSecs + hourSeconds))

        else:
            #print('you pressed', event.key)
            return

        displayEndSecs = min(displayStartSecs + displayRange, lastTestSysSecs)
        if lastTestSysSecs-displayRange-firstTestSysSecs > 0:
            position = min(100.0 * (displayStartSecs-firstTestSysSecs) / (lastTestSysSecs-displayRange-firstTestSysSecs), 100.0)
        else:
            position = 100.0
        SetCurrentSqlSelectRange() # this may modify displayStartSecs, displayEndSecs, curSqlMinTime, curSqlMaxTime
        if displayStartSecs != origDisplayStartSecs:
            ax.set_xlim(mdates.date2num(ReceiverTimeToUtcTime(displayStartSecs)),
                        mdates.date2num(ReceiverTimeToUtcTime(min(displayStartSecs+displayRange, lastTestSysSecs+1))))
        if position != origPosition:
            calcStats()
            sPos.set_val(position)  # this will cause fig.canvas.draw() to be called
        elif displayStartSecs != origDisplayStartSecs:
            fig.canvas.draw()

#---------------------------------------------------------
def submitNote(text):
    global noteText
    global oldNoteText
    global oldNoteXoff
    global oldNoteYoff

    #print ('submitNote() : oldNoteText =', noteText,', noteText =', text)
    oldNoteText = noteText
    noteText = text
    if noteArrow is not None:
        #print ('submitNote() : writeNote(xoff=', oldNoteXoff, 'yoff=', oldNoteYoff, ')')
        writeNote(oldNoteXoff, oldNoteYoff)
        oldNoteXoff = 0.0
        oldNoteYoff = 0.0

#---------------------------------------------------------
def submitTgtLow(text):
    global displayLow
    global displayHigh
    global tgtLowBox
    global tgtHighBox

    try:
        # convert input to Float
        newLow = float(text)
        newLowConv = round(newLow / gluMult, 0)
        if minDisplayLow <= newLowConv <= maxDisplayHigh:
            # Handle case where user entered a Low value greater than the current High
            if newLowConv > displayHigh:
                displayLow = displayHigh
                displayHigh = newLowConv
                tgtLowBox.set_val('%g' % round((displayLow * gluMult), tgtDecDigits))
                tgtHighBox.set_val('%g' % round((displayHigh * gluMult), tgtDecDigits))
            else:
                displayLow = newLowConv
                tgtLowBox.set_val('%g' % round((displayLow * gluMult), tgtDecDigits))
        else:
            # Replace the illegal value with the original one
            tgtLowBox.set_val('%g' % round((displayLow * gluMult), tgtDecDigits))

        if (displayLow != cfgDisplayLow) or (displayHigh != cfgDisplayHigh):
            saveConfigToDb()

            # If the user increases the Low end of Target Range, we may be able to
            # reduce the scale of the Y axis, depending on the minimum data value in
            # that axis. The lines below allow us to possibly zoom in on the Y axis.
            ax.ignore_existing_data_limits = True
            ax.update_datalim(egvScatter.get_datalim(ax.transData))
            ax.autoscale_view()
            ax.ignore_existing_data_limits = False

            plotGraph()
    except ValueError:
        if sys.version_info < (3, 0):
            sys.exc_clear()

#---------------------------------------------------------
def submitTgtHigh(text):
    global displayLow
    global displayHigh
    global tgtLowBox
    global tgtHighBox

    try:
        # convert input to Float
        newHigh = float(text)
        newHighConv = round(newHigh / gluMult, 0)
        if minDisplayLow <= newHighConv <= maxDisplayHigh:
            # Handle case where user entered a High value less than the current Low
            if newHighConv < displayLow:
                displayHigh = displayLow
                displayLow = newHighConv
                tgtLowBox.set_val('%g' % round((displayLow * gluMult), tgtDecDigits))
                tgtHighBox.set_val('%g' % round((displayHigh * gluMult), tgtDecDigits))
            else:
                displayHigh = newHighConv
                tgtHighBox.set_val('%g' % round((displayHigh * gluMult), tgtDecDigits))
        else:
            # Replace the illegal value with the original one
            tgtHighBox.set_val('%g' % round((displayHigh * gluMult), tgtDecDigits))

        if (displayLow != cfgDisplayLow) or (displayHigh != cfgDisplayHigh):
            saveConfigToDb()

            # If the user reduces the High end of Target Range, we may be able to
            # reduce the scale of the Y axis, depending on the maximum data value in
            # that axis. The lines below allow us to possibly zoom in on the Y axis.
            ax.ignore_existing_data_limits = True
            ax.update_datalim(egvScatter.get_datalim(ax.transData))
            ax.autoscale_view()
            ax.ignore_existing_data_limits = False

            plotGraph()
    except ValueError:
        if sys.version_info < (3, 0):
            sys.exc_clear()

#---------------------------------------------------------
def writeNote(xoff=0.0, yoff=0.0):
    global noteText
    global oldNoteText
    global noteArrow
    global submit_note_id
    global noteTimeSet
    global noteSet
    global notePlotList

    #print ('writeNote() : oldNoteText =',oldNoteText,', noteText =',noteText, ', xoff =', xoff, ', yoff =', yoff)

    if noteArrow is not None:
        # oldNoteText='', noteText=''       --> do nothing
        # oldNoteText='', noteText='abc'    --> clear arrow
        # oldNoteText='abc', noteText='def' --> clear arrow
        # oldNoteText='abc', noteText=''    --> clear arrow
        if oldNoteText == noteText:
            return
        if noteText != '':
            #print ('add note', 'noteLoc[0] =',noteLoc[0],'noteLoc[1] =',noteLoc[1])
            if (xoff == 0.0) and (yoff == 0.0):
                xoffset = 0.0
                if noteLoc[1] > 200:
                    yoffset = -50.0
                else:
                    yoffset = 50.0
            else:
                xoffset = xoff
                yoffset = yoff
            noteAnn = ax.annotate(noteText,
                                  xy=noteLoc, xycoords='data',
                                  xytext=(xoffset, yoffset), textcoords='offset pixels',
                                  color='black', fontsize=16,
                                  arrowprops=dict(connectionstyle="arc3,rad=-0.3", facecolor='brown',
                                                  shrink=0.10, width=2, headwidth=6.5, zorder=16), zorder=16)
            noteAnn.draggable()
            noteSet.add(noteAnn)
            notePlotList.append(noteAnn)
            timeIndex = getNearPos(xnorm, mdates.num2date(noteAnn.xy[0], tz=mytz))
            noteTimeSet.add(xnorm[timeIndex])
            #print ('writeNote note : X =',noteAnn.xy[0],'Y =',noteAnn.xy[1],'datetime =',xnorm[timeIndex])
            saveAnnToDb(noteAnn)
            noteText = ''
            oldNoteText = ''
            if submit_note_id is not None:
                noteBox.disconnect(submit_note_id)
            noteBox.set_val('')
            submit_note_id = noteBox.on_submit(submitNote)
        #else:
            #print ('writetNote() : noteText = \'\'')
        #print ('writetNote() : calling noteArrow.remove()')
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
    global oldNoteXoff
    global oldNoteYoff
    global submit_note_id

    mouseevent = event.mouseevent
    if mouseevent:
        if mouseevent.xdata and mouseevent.ydata:
            #print ('onpick(event) : button =',mouseevent.button,', xdata =',tod,', ydata =',gluc)
            # Check for a right button click. Some mouse devices only have 2 buttons, and some
            # have 3, so treat either one as a "right button".
            if (mouseevent.button == 2) or (mouseevent.button == 3):
                #print ('onpick(event) : tod =',tod,', xdata =',mouseevent.xdata,', gluc =',gluc)
                noteLoc = (mouseevent.xdata, mouseevent.ydata)
                matchNote = None
                for note in noteSet:
                    #print ('onpick(event) : X.dist =',mouseevent.xdata - note.xy[0],'Y.dist =',mouseevent.ydata - note.xy[1])
                    xdist = abs(mouseevent.xdata - note.xy[0])
                    # test if we're within 2.5 minutes of this note
                    if xdist < 0.001735906:
                        #print ('onpick(event) : xdist =',xdist, 'match =',note.xy[0],',',note.xy[1],'=',ReceiverTimeToUtcTime(note.xy[0]),'<--- Match')
                        matchNote = note
                        break

                if noteBoxPos:
                    if noteArrow:
                        # If an arrow already exists ...
                        if (abs(noteArrow.xy[0] - noteLoc[0]) < 0.001735906) and (noteText == ''):
                            # and the position of that arrow matches where the user
                            # just clicked, then we'll delete that arrow
                            #print ('onpick(event) : arrow position matches')
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
                                                            linewidth=3.0, zorder=16), zorder=16)
                    fig.canvas.draw()

                    if matchNote is None:
                        #print ('onpick(event) : calling writeNote()')
                        oldNoteText = ''
                        writeNote()
                    else:
                        oldNoteXoff = matchNote.xyann[0]
                        oldNoteYoff = matchNote.xyann[1]
                        if noteText == '':
                            noteText = matchNote.get_text()
                            #if args.debug:
                                #print ("Deleting existing note '%s'" % noteText)
                            deleteNoteFromDb(UtcTimeToReceiverTime(mdates.num2date(matchNote.xy[0], tz=mytz)), noteText)
                            try:
                                notePlotList.remove(matchNote)
                            except ValueError as e:
                                if sys.version_info < (3, 0):
                                    sys.exc_clear()
                            noteSet.discard(matchNote)
                            matchNote.remove()
                            matchNote = None
                            if submit_note_id is not None:
                                noteBox.disconnect(submit_note_id)
                            noteBox.set_val(noteText)
                            submit_note_id = noteBox.on_submit(submitNote)
                        else:
                            # replace the old note with the new one
                            oldNoteText = matchNote.get_text()
                            if args.debug:
                                print ("Replace the old note '%s' with the new one '%s'" % (oldNoteText, noteText))
                            matchNote.set_text(noteText)
                            saveAnnToDb(matchNote)
                            noteArrow.remove()
                            noteArrow = None
                            noteBox.set_val('')
                            fig.canvas.draw()

            elif mouseevent.button == 1:
                #print ('Button left')
                pass
            elif mouseevent.button == 'up':
                #print ('Button up')
                pass
            elif mouseevent.button == 'down':
                #print ('Button down')
                pass

#---------------------------------------------------------
def onclose(event):
    global rthread
    global sthread

    if args.debug:
        print ('*****************')
        print ('Close in progress')
        print ('*****************')

    # Shutdown PeriodicReadData thread
    if rthread is not None:
        rthread.stop()
        if args.debug:
            print ('Waiting on rthread.join()')
        rthread.join()
        rthread = None

    # Shutdown PerodicDeviceSeek thread
    if sthread is not None:
        sthread.stop()
        if args.debug:
            print ('Waiting on sthread.join()')
        sthread.join()
        sthread = None

    plt.close('all')
    sys.exit(0)

#---------------------------------------------------------
def leave_axes(event):
    global displayStartDate
    if event.inaxes is axScale:
        if scaleText:
            scaleText.set_text(SecondsToGeneralTimeString(displayRange))
            fig.canvas.draw_idle()
    elif event.inaxes is axPos:
        if posText:
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
        #print ('hover() : xdata =',event.xdata,', seconds =',xsecs,SecondsToGeneralTimeString(xsecs))
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
def UnitButtonCallback(event):
    print ('Unit Button pressed.')
    if gluUnits == 'mmol/L':
        #gluUnits = 'mg/dL'
        unitRead.label.set_text('Switch to\nmmol/L')
    else:
        #gluUnits = 'mmol/L'
        unitRead.label.set_text('Switch to\nmg/dL')

#---------------------------------------------------------
def TestButtonCallback(event):
    print ('Test Button pressed. Will read in 10 seconds.')
    timeLeftSeconds = 10
    if rthread is not None:
        print ('Calling rthread.restartDelay()')
        rthread.restartDelay(firstDelaySecs=timeLeftSeconds)
    else:
        print ('rthread is NULL')

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
    global curSqlMinTime
    global curSqlMaxTime

    # erase all previously plotted red calibration regions
    for redmark in redRegionList:
        redmark.remove()
    redRegionList = []
    redStartSet.clear()
    inRangeRegionList = []
    while inRangeRegionAnnotList:
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
    calibDict.clear()
    if linePlot:
        linePlot.pop(0).remove()
        linePlot = None
    curSqlMinTime = 0
    curSqlMaxTime = 0

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
    global axTgtLow
    global axTgtHigh
    global noteBox
    global noteBoxPos
    global tgtLowBox
    global tgtHighBox
    global submit_note_id
    global submit_tgtLow_id
    global submit_tgtHigh_id
    global axPos
    global axScale
    global legDefaultPosX
    global legDefaultPosY
    global highPercentText
    global midPercentText
    global lowPercentText
    global largeFontSize
    global mediumFontSize
    global smallFontSize
    global trendArrowSize
    global percentFontSize
    global battX
    global battY
    global gluMult
    global cfgDisplayLow
    global cfgDisplayHigh
    global dbGluUnits
    global dayRotation
    #global unitRead
    #global unitButton
    #global axtest
    #global testRead

    if args.debug:
        print ('rcParams[timezone] =', mpl.rcParams['timezone'])

    # Reserve some space at the bottom for the Sliders
    fig.subplots_adjust(bottom=sliderSpace)

    axcolor = 'lightsteelblue'

    #                [Left, Bottom, Width, Height]
    axPos = plt.axes([0.20, 0.05, 0.69, 0.03], facecolor=axcolor)
    sPos = Slider(axPos, 'Start Date', 0.0, position, 100.0, color='deepskyblue')
    # We don't want to display the numerical value, since we're going to
    # draw a text value of the percentage in the middle of the slider.
    sPos.valtext.set_visible(False)

    axScale = plt.axes([0.20, 0.01, 0.69, 0.03], facecolor=axcolor)
    sScale = Slider(axScale, 'Scale', 0.0, 100.0, 100.0, color='limegreen')
    # We don't want to display the numerical value, since we're going to
    # describe the period of time with a string in the middle of the slider.
    sScale.valtext.set_visible(False)

    #print ('pixels per inch =',fig.canvas.winfo_fpixels( '1i' ))
    #print ('axPos : Rect =', axPos.get_position().bounds)
    #print ('axPos : Rect.bottom =', axPos.get_position().bounds[1])

    ########################################################
    # hd terminal = 1920 x 1080 -> 1920/1080 = 1.78
    # laptop        1366 x  768 -> 1366/ 768 = 1.78
    # macbook pro = 1440 x 900  -> 1440/900  = 1.6
    #                              1280/1024 = 1.25
    ########################################################
    if 1.0 < dispRatio <= 1.4:   # 1.25 ratio for 1280 x 1024
                                 # 1.30 ratio for 1024 x 768
        rangeX = 0.947
        rangeY = 0.038
        tgtLowX = 0.893
        tgtLowY = 0.005
        tgtLowW = 0.039
        tgtLowH = 0.035
        tgtHighX = 0.957
        tgtHighY = 0.005
        tgtHighW = 0.048
        tgtHighH = 0.035

        trendX = 0.955
        trendY = 0.945
        battX = 0.946
        battY = 0.10
        noteX = 0.34
        noteY = 0.92
        noteW = 0.32
        noteH = 0.04
        logoX = 0.043
        logoY = 0.952
        avgTextX = 0.68
        avgTextY = 0.89
        verX = 0.003
        if height < 1024:
            largeFontSize = 'medium'
            mediumFontSize = 'small'
            smallFontSize = 'x-small'
            legDefaultPosX = 0.109
            legDefaultPosY = 0.865
            avgFontSz = 'medium'
            trendArrowSize = 13
            sPos.label.set_size('small')
            sScale.label.set_size('small')
            verY = 0.870
        else:
            largeFontSize = 'large'
            mediumFontSize = 'medium'
            smallFontSize = 'small'
            legDefaultPosX = 0.099
            legDefaultPosY = 0.879
            avgFontSz = 'large'
            trendArrowSize = 15
            verY = 0.880
        percentFontSize = mediumFontSize
    elif 1.4 < dispRatio <= 1.7:  # 1.6 ration for 1440 x 900, 1680 x 1050, 1920 x 1200
        rangeX = 0.950
        rangeY = 0.045
        tgtLowX = 0.910
        tgtLowY = 0.005
        tgtLowW = 0.030
        tgtLowH = 0.040
        tgtHighX = 0.959
        tgtHighY = 0.005
        tgtHighW = 0.03
        tgtHighH = 0.04

        trendX = 0.965
        trendY = 0.945
        battX = 0.946
        battY = 0.13
        noteX = 0.33
        noteY = 0.92
        noteW = 0.36
        noteH = 0.04
        logoX = 0.037
        logoY = 0.945
        largeFontSize = 'large'
        mediumFontSize = 'medium'
        smallFontSize = 'small'
        avgTextX = 0.73
        legDefaultPosX = 0.095
        avgFontSz = 'large'
        verX = 0.007
        verY = 0.870
        trendArrowSize = 15
        if height < 1080:
            avgTextY = 0.885
            legDefaultPosY = 0.862
            percentFontSize = mediumFontSize
        else:
            avgTextY = 0.900
            legDefaultPosY = 0.882
            percentFontSize = largeFontSize
    else:  # 1.78 ratio for 1920 x 1080, 1366 x 768, 1280 x 720, 1536 x 864,
           #                1600 x 900, 2560 x 1440, 3840 x 2160, 7680 x 4320
        rangeX = 0.950
        rangeY = 0.045
        tgtLowX = 0.912
        tgtLowY = 0.005
        tgtLowW = 0.032
        tgtLowH = 0.040
        tgtHighX = 0.959
        tgtHighY = 0.005
        tgtHighW = 0.030
        tgtHighH = 0.04

        trendX = 0.965
        trendY = 0.945
        battX = 0.946
        battY = 0.10
        noteX = 0.28
        noteY = 0.92
        noteW = 0.40
        noteH = 0.04
        logoX = 0.037
        logoY = 0.945
        if height < 1080:
            # For 1366 x 768, 1280 x 720, 1536 x 864, 1600 x 900 ...
            largeFontSize = 'medium'
            mediumFontSize = 'small'
            smallFontSize = 'x-small'
            avgTextX = 0.710
            avgTextY = 0.855
            avgFontSz = 'large'
            legDefaultPosX = 0.088
            legDefaultPosY = 0.844
            verX = 0.010
            verY = 0.860
            trendArrowSize = 13
            percentFontSize = mediumFontSize
        else:
            # For 1920 x 1080, 3840 x 2160, 7680 x 4320 ...
            largeFontSize = 'large'
            mediumFontSize = 'medium'
            smallFontSize = 'small'
            avgTextX = 0.760
            avgTextY = 0.880
            legDefaultPosX = 0.093
            legDefaultPosY = 0.878
            avgFontSz = 'x-large'
            verX = 0.022
            verY = 0.880
            trendArrowSize = 15
            percentFontSize = largeFontSize

    # If we're squeezed for vertical space, rotate the date and day name less so
    # that "Date & Time" string won't be pushed down to collide with Start Date.
    if height < 800:
        dayRotation = 20
    else:
        dayRotation = 30

    stat_text = plt.figtext(.05, .04, 'Search\nReceiver\nDevice',
                            backgroundcolor='y', size=largeFontSize, weight='bold',
                            horizontalalignment='center')

    if gluUnits == 'mmol/L':
        avgText = plt.gcf().text(avgTextX, avgTextY, 'Latest = %5.2f (mmol/L)\nAvg = %5.2f (mmol/L)\nStdDev = %5.2f\nHbA1c = %5.2f'
                                 %(0, 0, 0, 0), style='italic', size=avgFontSz, weight='bold')
    else:
        #avgText = plt.gcf().text(0.70, 0.87, 'Latest = %u (mg/dL)\nAvg = %5.2f (mg/dL)\nHbA1c = %5.2f'
        avgText = plt.gcf().text(avgTextX, avgTextY, 'Latest = %u (mg/dL)\nAvg = %5.2f (mg/dL)\nStdDev = %5.2f\nHbA1c = %5.2f'
                                 %(0, 0, 0, 0), style='italic', size=avgFontSz, weight='bold')

    trendArrow = plt.gcf().text(trendX, trendY, "Trend", ha="center", va="center",
                                rotation=0, size=trendArrowSize,
                                bbox=dict(boxstyle="rarrow,pad=0.3", facecolor="cyan", edgecolor="b", lw=2))

    # Plot percentages high, middle, and low
    highPercentText = plt.figtext(0.95, ((maxDisplayHigh - displayHigh) / 2.0 + displayHigh) / maxDisplayHigh * graphHeightInFigure + graphBottom,
                                  '%4.1f' %highPercent, style='italic', size=percentFontSize, weight='bold', color='red')
    midPercentText = plt.figtext(0.95, ((displayHigh - displayLow) / 2.0 + displayLow) / maxDisplayHigh * graphHeightInFigure + graphBottom,
                                 '%4.1f' %midPercent, style='italic', size=percentFontSize, weight='bold', color='cornflowerblue')
    lowPercentText = plt.figtext(0.95, displayLow / 2.0 / maxDisplayHigh * graphHeightInFigure + graphBottom,
                                 '%4.1f' %lowPercent, style='italic', size=percentFontSize, weight='bold', color='magenta')

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

    cfgDisplayLow, cfgDisplayHigh, dbGluUnits = readConfigFromSql()
    if dbGluUnits == 'mmol/L':
        # mmol/L = mg/dL x 0.0555
        gluMult = 0.0555
    else:
        gluMult = 1.0

    plt.gca().set_ylim([gluMult * minDisplayLow, gluMult * maxDisplayHigh])

    fig.canvas.mpl_connect('key_press_event', press)
    fig.canvas.mpl_connect("motion_notify_event", hover)

    plt.gcf().autofmt_xdate()

    axNote = plt.axes([noteX, noteY, noteW, noteH], frameon=True, zorder=10)
    noteBox = TextBox(axNote, 'Note', color='wheat', hovercolor='lightsalmon')
    submit_note_id = noteBox.on_submit(submitNote)
    noteBoxPos = axNote.get_position()
    #print ('noteBoxPos.x0 =',noteBoxPos.x0,'noteBoxPos.y0 =',noteBoxPos.y0,'noteBoxPos =',noteBoxPos)

    ####################################################################################
    axTgtLow = plt.axes([tgtLowX, tgtLowY, tgtLowW, tgtLowH], frameon=True, zorder=10)
    axTgtHigh = plt.axes([tgtHighX, tgtHighY, tgtHighW, tgtHighH], frameon=True, zorder=10)

    tgtLowBox = TextBox(axTgtLow, '', initial='%g' % round((cfgDisplayLow * gluMult), tgtDecDigits),
                        color='gold', hovercolor='lightsalmon')
    tgtHighBox = TextBox(axTgtHigh, '', initial='%g' % round((cfgDisplayHigh * gluMult), tgtDecDigits),
                         color='gold', hovercolor='lightsalmon')

    submit_tgtLow_id = tgtLowBox.on_submit(submitTgtLow)
    submit_tgtHigh_id = tgtHighBox.on_submit(submitTgtHigh)

    plt.gcf().text(rangeX, rangeY, 'Target Range\n\n-', size=mediumFontSize, color='black',
                   backgroundcolor='gold', ha='center', va='center')
    ####################################################################################

    #axtest = plt.axes([0, 0.15, 0.1, 0.075])
    #testRead = Button(axtest, 'Jump', color='pink')
    #testRead.on_clicked(TestButtonCallback)

    #                     Left, Bottom, Width, Height
    #unitButton = plt.axes([0.010, 0.20, 0.054, 0.065])
    #if gluUnits == 'mmol/L':
        #unitRead = Button(unitButton, 'Switch to\nmg/dL', color='lightsalmon')
    #else:
        #unitRead = Button(unitButton, 'Switch to\nmmol/L', color='lightsalmon')
    #unitRead.on_clicked(UnitButtonCallback)

    plt.gcf().text(logoX, logoY, 'Dexc\nTrack', style='italic', size=25, weight='bold',
                   color='orange', backgroundcolor='teal', ha='center', va='center')

    plt.gcf().text(verX, verY, 'v%s' %dexctrackVersion, size=12, weight='bold')

#---------------------------------------------------------
# This function coverts a trend value to a character which
# represents the direction represented by that trend.
def trendToChar(trendValue):
    if trendValue == 1:     # doubleUp
        my_trendChar = '^'
    elif trendValue == 2:   # singleUp
        my_trendChar = '^'
    elif trendValue == 3:   # fortyFiveUp
        my_trendChar = '/'
    elif trendValue == 4:   # flat
        my_trendChar = '-'
    elif trendValue == 5:   # fortyFiveDown
        my_trendChar = '\\'
    elif trendValue == 6:   # singleDown
        my_trendChar = 'v'
    elif trendValue == 7:   # doubleDown
        my_trendChar = 'V'
    elif trendValue == 0:   # none
        my_trendChar = '-'
    else:                  # notComputable (8) | rateOutOfRange (9)
        my_trendChar = '?'
    return my_trendChar

#---------------------------------------------------------
def calcStats():
    global avgGlu
    global hba1c
    global egvStdDev
    global highPercent
    global midPercent
    global lowPercent
    global displayEndSecs

    if displayEndSecs == 0:
        displayEndSecs = lastTestSysSecs

    if sqlite_file:
        conn = sqlite3.connect(sqlite_file)
        curs = conn.cursor()

        #++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
        # Find HbA1c. This is based on the average of glucose values over a 3 month period
        #++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
        selectSql = 'SELECT AVG(glucose) FROM EgvRecord WHERE glucose > 12 AND sysSeconds >= ? AND sysSeconds <= ?'
        ninetyDaysBack = int(displayEndSecs - 60*60*24*30*3)
        #print ('ninetyDaysBack =',ninetyDaysBack)
        curs.execute(selectSql, (ninetyDaysBack, displayEndSecs))
        sqlData = curs.fetchone()
        if sqlData[0] is None:
            avgGlu = 0.0
            hba1c = 0.0
        else:
            avgGlu = sqlData[0]
            hba1c = (sqlData[0] + 46.7) / 28.7
            #if args.debug:
                #print ('Average glucose =', avgGlu,', HbA1c =',hba1c)

        #++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
        # Find percentages of readings in High, Middle, and Low ranges over a 3 month period
        #++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
        selectSql = 'SELECT COUNT (*) FROM EgvRecord WHERE glucose > 12 AND glucose < ? AND sysSeconds >= ? AND sysSeconds <= ?'
        curs.execute(selectSql, (displayLow, ninetyDaysBack, displayEndSecs))
        sqlData = curs.fetchone()
        if sqlData[0] is None:
            lowCount = 0
        else:
            lowCount = sqlData[0]

        selectSql = 'SELECT COUNT (*) FROM EgvRecord WHERE glucose >= ? AND glucose <= ? AND sysSeconds >= ? AND sysSeconds <= ?'
        curs.execute(selectSql, (displayLow, displayHigh, ninetyDaysBack, displayEndSecs))
        sqlData = curs.fetchone()
        if sqlData[0] is None:
            midCount = 0
        else:
            midCount = sqlData[0]

        selectSql = 'SELECT COUNT (*) FROM EgvRecord WHERE glucose > ? AND sysSeconds >= ? AND sysSeconds <= ?'
        curs.execute(selectSql, (displayHigh, ninetyDaysBack, displayEndSecs))
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
        #if args.debug:
            #print ('highPercent =', highPercent, ', midPercent =', midPercent, ', lowPercent =', lowPercent)

        #++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
        # Calculate the SampleVariance over a 3 month period
        #++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
        #selectSql = 'SELECT AVG((glucose - ?) * (glucose - ?)) FROM EgvRecord WHERE glucose > 12 AND sysSeconds >= ?'
        selectSql = 'SELECT glucose FROM EgvRecord WHERE glucose > 12 AND sysSeconds >= ? AND sysSeconds <= ?'
        curs.execute(selectSql, (ninetyDaysBack, displayEndSecs))
        sqlData = curs.fetchall()
        egvCount = len(sqlData)

        if egvCount > 1:
            selectSql = 'SELECT TOTAL((glucose - ?) * (glucose - ?)) FROM EgvRecord WHERE glucose > 12 AND sysSeconds >= ? AND sysSeconds <= ?'
            curs.execute(selectSql, (avgGlu, avgGlu, ninetyDaysBack, displayEndSecs))
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
            #print ('egvCount =',egvCount,', egvSampleVariance =',egvSampleVariance,', egvStdDev =',egvStdDev)

        del sqlData
        curs.close()
        conn.close()

        if avgText:
            if gluUnits == 'mmol/L':
                if (lastTestGluc == 5) or (lastTestGluc == 1):
                    avgText.set_text('Latest = ?\nAvg = %5.2f (mmol/L)\nStdDev = %5.2f\nHbA1c = %5.2f'
                                     %(gluMult * avgGlu, gluMult * egvStdDev, hba1c))
                else:
                    avgText.set_text('Latest = %5.2f (mmol/L)\nAvg = %5.2f (mmol/L)\nStdDev = %5.2f\nHbA1c = %5.2f'
                                     %(gluMult * lastRealGluc, gluMult * avgGlu, gluMult * egvStdDev, hba1c))
            else:
                if (lastTestGluc == 5) or (lastTestGluc == 1):
                    avgText.set_text('Latest = ?\nAvg = %5.2f (mg/dL)\nStdDev = %5.2f\nHbA1c = %5.2f'
                                     %(avgGlu, egvStdDev, hba1c))
                else:
                    avgText.set_text('Latest = %u (mg/dL)\nAvg = %5.2f (mg/dL)\nStdDev = %5.2f\nHbA1c = %5.2f'
                                     %(lastRealGluc, avgGlu, egvStdDev, hba1c))

        if highPercentText:
            highPercentText.set_text('%4.1f%%' %highPercent)
        if midPercentText:
            midPercentText.set_text('%4.1f%%' %midPercent)
        if lowPercentText:
            lowPercentText.set_text('%4.1f%%' %lowPercent)

#---------------------------------------------------------
def readConfigFromSql():
    global tgtDecDigits

    if sqlite_file:
        conn = sqlite3.connect(sqlite_file)
        curs = conn.cursor()

        selectSql = "SELECT count(*) from sqlite_master where type='table' and name='Config'"
        curs.execute(selectSql)
        sqlData = curs.fetchone()
        if sqlData[0] > 0:
            selectSql = "SELECT displayLow, displayHigh, glUnits FROM Config"
            curs.execute(selectSql)
            sqlData = curs.fetchone()
            if sqlData is not None:
                myDisplayLow = sqlData[0]
                myDisplayHigh = sqlData[1]
                myGluUnits = sqlData[2]
                if myGluUnits == 'mmol/L':
                    tgtDecDigits = 1
                else:
                    tgtDecDigits = 0
                curs.close()
                conn.close()
                return myDisplayLow, myDisplayHigh, myGluUnits

        curs.close()
        conn.close()
    # Couldn't read from database, so return default values
    return displayLow, displayHigh, gluUnits

#---------------------------------------------------------
def readRangeFromSql():
    global firstTestSysSecs
    global lastTestSysSecs
    global lastTestGluc
    global lastTestDateTime

    if sqlite_file:
        conn = sqlite3.connect(sqlite_file)
        curs = conn.cursor()

        selectSql = "SELECT count(*) from sqlite_master where type='table' and name='EgvRecord'"
        curs.execute(selectSql)
        sqlData = curs.fetchone()
        if sqlData[0] > 0:
            # get the first test info
            curs.execute('SELECT sysSeconds,glucose FROM EgvRecord ORDER BY sysSeconds ASC LIMIT 1')
            sqlData = curs.fetchall()
            for row in sqlData:
                firstTestSysSecs = row[0]

            # get the last test info
            curs.execute('SELECT sysSeconds,glucose FROM EgvRecord ORDER BY sysSeconds DESC LIMIT 1')
            sqlData = curs.fetchall()
            for row in sqlData:
                lastTestSysSecs = row[0]
                lastTestGluc = row[1]
                lastTestDateTime = ReceiverTimeToUtcTime(lastTestSysSecs)

        del sqlData
        curs.close()
        conn.close()

#---------------------------------------------------------
def readDataFromSql(sqlMinTime, sqlMaxTime):
    global sqlEarliestGluc
    global sqlMaximumGluc
    global lastRealGluc
    global egvList
    global calibList
    global eventList
    global noteList
    global lastTrend
    global trendChar
    global cfgDisplayLow
    global cfgDisplayHigh
    global latestSensorInsertTime
    global legPosX
    global legPosY
    global dbGluUnits
    global readDataInstance
    global tgtDecDigits

    #if args.debug:
        #print ('readDataFromSql(%s, %s)' %(ReceiverTimeToUtcTime(sqlMinTime).astimezone(mytz), ReceiverTimeToUtcTime(sqlMaxTime).astimezone(mytz)))
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

            selectSql = 'SELECT sysSeconds,glucose FROM EgvRecord WHERE sysSeconds >= ? AND sysSeconds <= ? AND glucose > 12 ORDER BY sysSeconds ASC LIMIT 1'
            curs.execute(selectSql, (sqlMinTime, sqlMaxTime))
            sqlData = curs.fetchall()
            for row in sqlData:
                sqlEarliestGluc = row[1]

            selectSql = 'SELECT sysSeconds,glucose FROM EgvRecord WHERE sysSeconds >= ? AND sysSeconds <= ? AND glucose > 12 ORDER BY glucose DESC LIMIT 1'
            curs.execute(selectSql, (sqlMinTime, sqlMaxTime))
            sqlData = curs.fetchall()
            for row in sqlData:
                sqlMaximumGluc = row[1]

            if appendable_db:
                # get the last real glucose reading
                selectSql = 'SELECT glucose,trend FROM EgvRecord WHERE glucose > 12 ORDER BY sysSeconds DESC LIMIT 1'
                curs.execute(selectSql)
                sqlData = curs.fetchall()
                for row in sqlData:
                    lastRealGluc = row[0]
                    lastTrend = row[1] & constants.EGV_TREND_ARROW_MASK
            else:
                if not readDataInstance:
                    readDataInstance = getReadDataInstance()
                if readDataInstance:
                    curGluc, curFullTrend = readDataInstance.GetCurrentGlucoseAndTrend()
                    if curGluc and curFullTrend:
                        lastRealGluc = curGluc
                        lastTrend = curFullTrend & constants.EGV_TREND_ARROW_MASK
                    #print ('readDataFromSql() lastRealGluc =', lastRealGluc)
                #else:
                    #print ('readDataFromSql() readDataInstance = NULL')

            trendChar = trendToChar(lastTrend)

            if args.debug:
                print ('Latest glucose at', lastTestDateTime.astimezone(mytz), '=', lastRealGluc)

            #print ('sqlMinTime =',sqlMinTime,', sqlMaxTime =',sqlMaxTime)
            #-----------------------------------------------------

            selectSql = 'SELECT sysSeconds,glucose FROM EgvRecord WHERE sysSeconds >= ? AND sysSeconds <= ? ORDER BY sysSeconds'

            # Limit the range of the selection ...
            curs.execute(selectSql, (sqlMinTime, sqlMaxTime))
            sqlData = curs.fetchall()
            #print ('sql results length =',len(sqlData),'sqlMinTime =',sqlMinTime,'sqlMaxTime =',sqlMaxTime)

            for row in sqlData:
                egvList.append([ReceiverTimeToUtcTime(row[0]), row[1]])
            #print ('readDataFromSql(2) length egvList =', len(egvList))

            #++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
            # Check to see if we have any Calib records in the database
            selectSql = "SELECT count(*) from sqlite_master where type='table' and name='Calib'"
            curs.execute(selectSql)
            sqlData = curs.fetchone()
            haveCalib = (sqlData[0] > 0)

            if haveCalib:
                #                          0        1
                selectCalSql = 'SELECT sysSeconds,glucose FROM Calib WHERE type=1 AND sysSeconds >= ? AND sysSeconds <= ?'
                selectEgvSql = 'SELECT sysSeconds,glucose FROM EgvRecord WHERE glucose > 12 AND sysSeconds BETWEEN ?-300 AND ?+300 ORDER BY ABS(sysSeconds - ?) LIMIT 1'
                curs.execute(selectCalSql, (sqlMinTime, sqlMaxTime))
                sqlData = curs.fetchall()
                #print ('sql calibration results length =',len(sqlData))

                for calibRow in sqlData:
                    # Search for the closest EGV record within 5 minutes of the User Calibration entry
                    curs.execute(selectEgvSql, (calibRow[0], calibRow[0], calibRow[0]))
                    egvRow = curs.fetchone()
                    if egvRow:
                        #ctime = ReceiverTimeToUtcTime(egvRow[0])
                        #print ('New --> Calib @', ctime.astimezone(mytz), ', calib_gluc =', calibRow[1], ', timeDiff =', calibRow[0] - egvRow[0], ', cgmGluc =', egvRow[1], ', calibDiff =', calibRow[1] - egvRow[1])
                        # calculate an errorbar offset
                        calibList.append([ReceiverTimeToUtcTime(egvRow[0]), egvRow[1], calibRow[1] - egvRow[1], None])
                    else:
                        # No egvRow was found (possibly due to this Calibration happening
                        # within a Sensor Calibration period), so specify a 0 distance offset.
                        # We'll end up plotting the User Calibration without an errorbar.
                        calibList.append([ReceiverTimeToUtcTime(calibRow[0]), calibRow[1], 0, None])

        #++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
        selectSql = "SELECT count(*) from sqlite_master where type='table' and name='UserEvent'"
        curs.execute(selectSql)
        sqlData = curs.fetchone()
        if sqlData[0] > 0:
            #                       0           1           2         3     4      5      6       7
            selectSql = 'SELECT sysSeconds,dispSeconds,meterSeconds,type,subtype,value,xoffset,yoffset FROM UserEvent WHERE sysSeconds >= ? AND sysSeconds <= ? ORDER BY sysSeconds-dispSeconds+meterSeconds'
            curs.execute(selectSql, (sqlMinTime, sqlMaxTime))
            sqlData = curs.fetchall()
            for row in sqlData:
                #print ('Event: sysSeconds =',row[0],'type =',row[1],'subtype =',row[2],'value =',row[3],'xoffset =',row[4],'yoffset =',row[5])
                #########################################################################################
                # In older (G5) versions Receiver firmware, the current date and time is always assigned
                # when a user enters an Event.  In newer (G6) releases of firmware, the user is allowed
                # to specify an alternate date and time for the Event.
                #    sysSeconds = event creation time in seconds since BASE_TIME in UTC timezone
                #    dispSeconds = event creation time in seconds since BASE_TIME in Local timezone
                #    meterSeconds = User entered Event time in seconds since BASE_TIME in Local timezone
                # We need the User entered Event time in the UTC timezone.
                #   Offset in seconds = sysSeconds - dispSeconds
                #   Event time (in UTC)= (sysSeconds - dispSeconds) + meterSeconds
                #########################################################################################
                eventList.append([ReceiverTimeToUtcTime(row[0] - row[1] + row[2]), row[3], row[4], row[5], row[6], row[7]])
        #++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
        selectSql = "SELECT count(*) from sqlite_master where type='table' and name='UserNote'"
        curs.execute(selectSql)
        sqlData = curs.fetchone()
        if sqlData[0] > 0:
            selectSql = 'SELECT sysSeconds,message,xoffset,yoffset FROM UserNote WHERE sysSeconds >= ? AND sysSeconds <= ? ORDER BY sysSeconds'
            curs.execute(selectSql, (sqlMinTime, sqlMaxTime))
            sqlData = curs.fetchall()
            for row in sqlData:
                #print ('Note: sysSeconds =',row[0],'message =',row[1],'xoffset =',row[2],'yoffset =',row[3])
                noteList.append([ReceiverTimeToUtcTime(row[0]), row[1], row[2], row[3]])
        #++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

        selectSql = "SELECT count(*) from sqlite_master where type='table' and name='SensorInsert'"
        curs.execute(selectSql)
        sqlData = curs.fetchone()
        if sqlData[0] > 0:
            selectSql = 'SELECT insertSeconds FROM SensorInsert WHERE state = 7 ORDER BY sysSeconds DESC LIMIT 1'
            # get the latest sensor insertion Start (state == 7) time
            curs.execute(selectSql)
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
                    #legPosX = sqlData[2]
                    #legPosY = sqlData[3]
                    legPosX = legDefaultPosX
                    legPosY = legDefaultPosY
                    dbGluUnits = sqlData[4]
            else:
                cfgDisplayLow = displayLow
                cfgDisplayHigh = displayHigh
                legPosX = legDefaultPosX
                legPosY = legDefaultPosY
                dbGluUnits = 'mg/dL'

            if dbGluUnits == 'mmol/L':
                tgtDecDigits = 1
            else:
                tgtDecDigits = 0

        #++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

        del sqlData

        curs.close()
        conn.close()

#---------------------------------------------------------
def saveAnnToDb(ann):
    conn = sqlite3.connect(sqlite_file)
    try:
        curs = conn.cursor()
        if ann.get_color() == 'black':
            # We may have modified offsets, or modified message, or a completely new UserNote
            #print ('SELECT sysSeconds,message,xoffset,yoffset FROM UserNote WHERE sysSeconds=%u AND message=\'%s\';' % (UtcTimeToReceiverTime(mdates.num2date(ann.xy[0], tz=mytz)), ann.get_text()))
            selectSql = 'SELECT sysSeconds,message,xoffset,yoffset FROM UserNote WHERE sysSeconds=? AND message=?'
            curs.execute(selectSql, (UtcTimeToReceiverTime(mdates.num2date(ann.xy[0], tz=mytz)), '%s'%ann.get_text()))
            sqlData = curs.fetchone()
            if sqlData is None:
                #print ('SELECT sysSeconds,message,xoffset,yoffset FROM UserNote WHERE sysSeconds=%u AND xoffset=%f AND yoffset=%f;' % (UtcTimeToReceiverTime(mdates.num2date(ann.xy[0], tz=mytz)), ann.xyann[0], ann.xyann[1]))
                selectSql = 'SELECT sysSeconds,message,xoffset,yoffset FROM UserNote WHERE sysSeconds=? AND xoffset=? AND yoffset=?'
                curs.execute(selectSql, (UtcTimeToReceiverTime(mdates.num2date(ann.xy[0], tz=mytz)), ann.xyann[0], ann.xyann[1]))
                sqlData = curs.fetchone()
                if sqlData is None:
                    # A completely new UserNote
                    curs.execute('CREATE TABLE IF NOT EXISTS UserNote( sysSeconds INT PRIMARY KEY, message TEXT, xoffset REAL, yoffset REAL);')
                    insert_note_sql = '''INSERT OR IGNORE INTO UserNote( sysSeconds, message, xoffset, yoffset) VALUES (?, ?, ?, ?);'''
                    #print ('INSERT OR IGNORE INTO UserNote( sysSeconds, message, xoffset, yoffset) VALUES (%u,%s,%f,%f);' %(UtcTimeToReceiverTime(mdates.num2date(ann.xy[0],tz=mytz)),'%s'%ann.get_text(),ann.xyann[0],ann.xyann[1]))
                    curs.execute(insert_note_sql, (UtcTimeToReceiverTime(mdates.num2date(ann.xy[0], tz=mytz)), '%s'%ann.get_text(), ann.xyann[0], ann.xyann[1]))
                else:
                    # Modified message
                    update_note_sql = '''UPDATE UserNote SET message=? WHERE sysSeconds=? AND xoffset=? AND yoffset=?;'''
                    #print ('UPDATE UserNote SET message=\'%s\' WHERE sysSeconds=%u AND xoffset=%f AND yoffset=%f;' %(ann.get_text(), UtcTimeToReceiverTime(mdates.num2date(ann.xy[0],tz=mytz)), ann.xyann[0], ann.xyann[1]))
                    curs.execute(update_note_sql, ('%s'%ann.get_text(), UtcTimeToReceiverTime(mdates.num2date(ann.xy[0], tz=mytz)), ann.xyann[0], ann.xyann[1]))
            else:
                # Modified offsets
                update_note_sql = '''UPDATE UserNote SET xoffset=?, yoffset=? WHERE sysSeconds=? AND message=?;'''
                #print ('UPDATE UserNote SET xoffset=%f, yoffset=%f WHERE sysSeconds=%u AND message=\'%s\';' %(ann.xyann[0], ann.xyann[1], UtcTimeToReceiverTime(mdates.num2date(ann.xy[0],tz=mytz)), ann.get_text()))
                curs.execute(update_note_sql, (ann.xyann[0], ann.xyann[1], UtcTimeToReceiverTime(mdates.num2date(ann.xy[0], tz=mytz)), '%s'%ann.get_text()))
            curs.close()
            conn.commit()
        else:
            #print ('SELECT sysSeconds,dispSeconds,meterSeconds,type,subtype,value,xoffset,yoffset FROM UserEvent WHERE sysSeconds=%u AND xoffset=%d AND yoffset=%d;' % (UtcTimeToReceiverTime(mdates.num2date(ann.xy[0])), ann.xyann[0], ann.xyann[1]))
            selectSql = 'SELECT sysSeconds,dispSeconds,meterSeconds,type,subtype,value,xoffset,yoffset FROM UserEvent WHERE sysSeconds-dispSeconds+meterSeconds=?'
            curs.execute(selectSql, (UtcTimeToReceiverTime(mdates.num2date(ann.xy[0])),))
            sqlData = curs.fetchone()
            if sqlData is None:
                #print ('saveAnnToDb() : No match for', ann)
                pass
            else:
                update_evt_sql = '''UPDATE UserEvent SET xoffset=?, yoffset=? WHERE sysSeconds=? AND type=? AND subtype=? AND value=?;'''
                #print ('UPDATE UserEvent SET xoffset=%f, yoffset=%f WHERE sysSeconds=%u AND type=%u AND subtype=%u AND value=%u;'%(ann.xyann[0], ann.xyann[1], sqlData[0], sqlData[3], sqlData[4], sqlData[5]))
                curs.execute(update_evt_sql, (ann.xyann[0], ann.xyann[1], sqlData[0],
                                              sqlData[3], sqlData[4], sqlData[5]))
            curs.close()
            conn.commit()
    except sqlite3.Error as e:
        print ('saveAnnToDb() : sql changes failed to exception =', e)
        curs.close()
    conn.close()

#---------------------------------------------------------
def deleteNoteFromDb(sysSeconds, message):
    conn = sqlite3.connect(sqlite_file)
    try:
        curs = conn.cursor()
        #print ('DELETE FROM UserNote WHERE sysSeconds=%u AND message=\'%s\';' %(sysSeconds,message))
        deleteSql = 'DELETE FROM UserNote WHERE sysSeconds=? AND message=?'
        curs.execute(deleteSql, (sysSeconds, '%s'%message))
        curs.close()
        conn.commit()
    except sqlite3.Error as e:
        print ('deleteNoteFromDb() : sql changes failed to exception =', e)
        curs.close()
    conn.close()

#---------------------------------------------------------
def saveConfigToDb():
    if sqlite_file:
        conn = sqlite3.connect(sqlite_file)
        try:
            curs = conn.cursor()

            if leg:
                lframe = leg.get_frame()
                lx, ly = lframe.get_x(), lframe.get_y()
                legx, legy = fig.transFigure.inverted().transform((lx, ly))
                #print ('legx, legy =',(legx, legy))
            else:
                #legx,legy = legDefaultPosX, legDefaultPosY
                legx, legy = 0, 0

            #print ('INSERT OR REPLACE INTO Config (id, displayLow, displayHigh, legendX, legendY, glUnits) VALUES (0,', displayLow, ',', displayHigh, ',', legx, ',', legy, ',\'%s\');' %gluUnits)
            insert_cfg_sql = '''INSERT OR REPLACE INTO Config( id, displayLow, displayHigh, legendX, legendY, glUnits) VALUES (0, ?, ?, ?, ?, ?);'''
            curs.execute(insert_cfg_sql, (displayLow, displayHigh, legx, legy, gluUnits))

            curs.close()
            conn.commit()
        except sqlite3.Error as e:
            print ('saveConfigToDb() : Rolling back sql changes due to exception =', e)
            curs.close()
            conn.rollback()
            if sys.version_info < (3, 0):
                sys.exc_clear()
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
    global noteTimeSet

    #=======================================================
    # Annotate the plot with user events
    #=======================================================
    multX = 1.0
    multY = 1.0
    visibleAnnotCount = 0
    longTextBump = 0

    # Find the size of the plotting area in pixels
    ax_bbox = ax.get_window_extent().transformed(fig.dpi_scale_trans.inverted())
    ax_width, ax_height = ax_bbox.width * fig.dpi, ax_bbox.height * fig.dpi
    #print ('ax_width, ax_height =', (ax_width, ax_height))

    #if args.debug:
        #print ('Before visible events count =', len(muppy.get_objects()))

    begTime = ReceiverTimeToUtcTime(displayStartSecs)
    endTime = ReceiverTimeToUtcTime(displayStartSecs + displayRange)
    for (estime, etype, esubtype, evalue, exoffset, eyoffset) in eventList:
        if (estime >= begTime) and (estime < endTime):
            visibleAnnotCount += 1

    for (estime, message, xoffset, yoffset) in noteList:
        if (estime >= begTime) and (estime < endTime):
            visibleAnnotCount += 1

    #print ('visibleAnnotCount =',visibleAnnotCount)
    #if args.debug:
        #print ('After visible events count =', len(muppy.get_objects()))

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

    # Note: 'pylint' complains about the following line,
    #   Do not use `len(SEQUENCE)` to determine if a sequence is empty (len-as-condition)
    # but it is WRONG because 'xnorm' is a numpy.array.
    if len(xnorm) == 0:
        return

    #if args.debug:
        #print ('Before events count =', len(muppy.get_objects()))
    evtgen = (ev for ev in eventList if ev[0] not in etimeSet)
    for (estime, etype, esubtype, evalue, exoffset, eyoffset) in evtgen:
        timeIndex = getNearPos(xnorm, estime)
        #print ('Event: time =',estime,'type =',etype,'subtype =',esubtype,'value =',evalue,'index =',timeIndex,'glu =',ynorm[timeIndex])
        longTextBump = 0

        if etype == 1:
            evt_color = 'orangered'
            evtStr = '%ug Carbs'%evalue

        elif etype == 2:
            evt_color = 'blue'
            if esubtype == 1:
                evtStr = '%g Fast Insulin'%(evalue / 100.0)
            elif esubtype == 2:
                evtStr = '%g Long Insulin'%(evalue / 100.0)
            else:
                evtStr = '%g Insulin'%(evalue / 100.0)

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
            evt_color = 'brown'
            evtStr = 'Unknown event'
        #if args.debug:
            #print ('After setting event string count =',len(muppy.get_objects()))

        if last_etime:
            # Since users can insert many events in close proximity,
            # the default placement tends to cause collisions of the
            # text. Here, we check to see if the current event is
            # close (in time) to the previous one. If so, we'll switch the
            # arrow position from left + up, to left + down, to right + down
            # to right + up. If 5 in a row are close, then we push the
            # distance out. This scheme spirals the placement out in
            # the order 'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', etc.
            #
            #  'E' (-2,2)                    +-------------------(2,2) 'H'
            #      |                         |
            #      |                         |
            #      |   'A' (-1,1)            |  +-------(1,1) 'D'
            #      |          |              V  |
            #      |          +------->         V
            #      |
            #      +---------------->
            #                                    <-----------------+
            #                                                      |
            #                         ^        <-------+           |
            #                         |  ^             |           |
            #         'B' (-1,-1)-----+  |           (1,-1) 'C'    |
            #                            |                         |
            #                            |                         |
            # 'F' (-2,-2)----------------+                     (2,-2) 'G'
            #
            if (estime - last_etime) < datetime.timedelta(minutes=110):
                #print ('---> estime =',estime,'estime - last_etime =',estime - last_etime,', evtStr =',evtStr)
                if annCloseCount & 3 == 0:
                    multX = annRotation
                    multY = -annRotation
                elif annCloseCount & 3 == 1:
                    multX = -annRotation
                    multY = -annRotation
                elif annCloseCount & 3 == 2:
                    multX = -annRotation
                    multY = annRotation
                else:
                    annRotation += 0.85
                    multX = annRotation
                    multY = annRotation
                annCloseCount += 1
            else:
                #print ('estime =',estime,'estime - last_etime =',estime - last_etime,', evtStr =',evtStr)
                annRotation = 1.0
                longTextBump = 0
                annCloseCount = 0
                multX = 1.0
                multY = 1.0
            #if args.debug:
                #print ('After setting multX, multY, annRotation, count =',len(muppy.get_objects()))

        # If a specific position has not been established for the event yet, automatically
        # generate a value which is distanced away from recent event locations.
        #if True:   # Use this to force automatic repositioning
        if (exoffset == 0.0) and (eyoffset == 0.0):
            if multX > 0:
                # Push the position to the left using an estimate of the string width
                exoffset = multX * -50.0 - len(evtStr) * 11.8
            else:
                exoffset = multX * -50.0
            eyoffset = multY * (50.0+longTextBump)

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
                print ('Event @ %s \'%s\' X offset %f < -half screen width (%f)' % (estime.astimezone(mytz), evtStr, exoffset, -ax_width / 2))
            exoffset = -60.0
            repositioned = True
        elif exoffset > ax_width / 2:
            if args.debug:
                print ('Event @ %s \'%s\' X offset %f > half screen width (%f)' % (estime.astimezone(mytz), evtStr, exoffset, ax_width / 2))
            exoffset = 60.0
            repositioned = True

        # If the Y offset is more than half the height of the screen, we'll override
        # it with a small offset.
        if eyoffset < -ax_height / 2:
            if args.debug:
                print ('Event @ %s \'%s\' Y offset %f < -half screen height (%f)' % (estime.astimezone(mytz), evtStr, eyoffset, -ax_height / 2))
            eyoffset = -60.0
            repositioned = True
        elif eyoffset > ax_height / 2:
            if args.debug:
                print ('Event @ %s \'%s\' Y offset %f > half screen height (%f)' % (estime.astimezone(mytz), evtStr, eyoffset, ax_height / 2))
            eyoffset = 60.0
            repositioned = True

        if repositioned:
            if args.debug:
                print ('After repositioning, new offsets =', (exoffset, eyoffset))

        # Sometimes the calculated or stored Y offset position lands outside
        # the limits of the axes, making it invisible. In such a case, we want to
        # recalculate the offset position.
        if (ynorm[timeIndex] + gluMult * eyoffset > maxDisplayHigh) or (ynorm[timeIndex] + gluMult * eyoffset < 0):
            if args.debug:
                print ('Event @ %s \'%s\' Y offset %f (%f + %f) is outside plotting area. Recalculating.' % (estime.astimezone(mytz), evtStr, ynorm[timeIndex] + gluMult * eyoffset, ynorm[timeIndex], gluMult * eyoffset))
            strawY = multY*(75+longTextBump)
            if ((ynorm[timeIndex] + gluMult * strawY) > maxDisplayHigh) or ((ynorm[timeIndex] + gluMult * strawY) < 0):
                eyoffset = -strawY
            else:
                eyoffset = strawY

            if ((ynorm[timeIndex] + gluMult * eyoffset) > maxDisplayHigh) or (ynorm[timeIndex] + gluMult * eyoffset < 0):
                if args.debug:
                    print ('Event @ %s \'%s\' recalculated Y offset %f (%f + %f) is outside plotting area.' % (estime.astimezone(mytz), evtStr, ynorm[timeIndex] + gluMult * eyoffset, ynorm[timeIndex], gluMult * eyoffset))
                eyoffset *= -1.5
            repositioned = True
            if args.debug:
                print ('    new offsets =', (exoffset, eyoffset))

        evt_annot = ax.annotate(evtStr,
                                xy=(mdates.date2num(estime), ynorm[timeIndex]), xycoords='data',
                                xytext=(exoffset, eyoffset), textcoords='offset pixels',
                                fontsize=16, color=evt_color,
                                arrowprops=dict(connectionstyle="arc3,rad=.3", facecolor=evt_color,
                                                shrink=0.10, width=2, headwidth=6.5, zorder=11), zorder=11)

        #if args.debug:
            #print ('After event annotation, count =',len(muppy.get_objects()))
        evt_annot.draggable()
        evtPlotList.append(evt_annot)

        # If we had to reposition the annotation, save the new location in the database
        if repositioned is True:
            saveAnnToDb(evt_annot)

        #if args.debug:
            #print ('After event append, count =',len(muppy.get_objects()))
        last_etime = estime
        # add this to the list of events which have already been annotated
        etimeSet.add(estime)

    #=======================================================
    # User Notes
    #=======================================================
    #if args.debug:
        #print ('After events, before Notes count =', len(muppy.get_objects()))
    notegen = (nt for nt in noteList if nt[0] not in noteTimeSet)
    for (estime, message, nxoffset, nyoffset) in notegen:
        #tod, gluc = (mdates.num2date(mouseevent.xdata,tz=mytz), mouseevent.ydata)
        timeIndex = getNearPos(xnorm, estime)

        repositioned = False

        # If the X offset is more than half the width of the screen, we'll override
        # with a small offset.
        if nxoffset < -ax_width / 2:
            if args.debug:
                print ('Note @ %s \'%s\' X offset %f < -half screen width (%f)' % (estime.astimezone(mytz), message, nxoffset, -ax_width / 2))
            nxoffset = -60.0
            repositioned = True
        elif nxoffset > ax_width / 2:
            if args.debug:
                print ('Note @ %s \'%s\' X offset %f > half screen width (%f)' % (estime.astimezone(mytz), message, nxoffset, ax_width / 2))
            nxoffset = 60.0
            repositioned = True

        # If the Y offset is more than half the height of the screen, we'll override
        # it with a small offset.
        if nyoffset < -ax_height / 2:
            if args.debug:
                print ('Note @ %s \'%s\' Y offset %f < -half screen height (%f)' % (estime.astimezone(mytz), message, nyoffset, -ax_height / 2))
            nyoffset = -60.0
            repositioned = True
        elif nyoffset > ax_height / 2:
            if args.debug:
                print ('Note @ %s \'%s\' Y offset %f > half screen height (%f)' % (estime.astimezone(mytz), message, nyoffset, ax_height / 2))
            nyoffset = 60.0
            repositioned = True

        if repositioned:
            if args.debug:
                print ('After repositioning, new offsets =', (nxoffset, nyoffset))

        # Sometimes the calculated or stored Y offset position lands outside
        # the limits of the axes, making it invisible. In such a case, we want to
        # recalculate the offset position.
        if (ynorm[timeIndex] + gluMult * nyoffset > maxDisplayHigh) or (ynorm[timeIndex] + gluMult * nyoffset < 0):
            if args.debug:
                print ('Note @ %s \'%s\' Y offset %f (%f + %f) is outside plotting area. Recalculating.' % (estime.astimezone(mytz), message, ynorm[timeIndex] + gluMult * nyoffset, ynorm[timeIndex], gluMult * nyoffset))
            strawY = multY*(75+longTextBump)
            if ((ynorm[timeIndex] + strawY) > maxDisplayHigh) or ((ynorm[timeIndex] + strawY) < 0):
                nyoffset = -strawY
            else:
                nyoffset = strawY

            if ((ynorm[timeIndex] + gluMult * nyoffset) > maxDisplayHigh) or (ynorm[timeIndex] + gluMult * nyoffset < 0):
                if args.debug:
                    print ('Note @ %s \'%s\' recalculated Y offset %f (%f + %f) is outside plotting area.' % (estime.astimezone(mytz), message, ynorm[timeIndex] + gluMult * nyoffset, ynorm[timeIndex], gluMult * nyoffset))
                nyoffset *= -1.5
            repositioned = True
            if args.debug:
                print ('    new offsets =', (nxoffset, nyoffset))

        #print ('Note: estime =', estime, ', gluc =', ynorm[timeIndex],'message =', message, 'xoffset =', nxoffset, 'yoffset =', nyoffset)
        noteAnn = ax.annotate(message,
                              xy=(mdates.date2num(estime), ynorm[timeIndex]), xycoords='data',
                              xytext=(nxoffset, nyoffset), textcoords='offset pixels',
                              color='black', fontsize=16,
                              arrowprops=dict(connectionstyle="arc3,rad=-0.3", facecolor='brown',
                                              shrink=0.10, width=2, headwidth=6.5, zorder=16), zorder=16)
        noteAnn.draggable()
        notePlotList.append(noteAnn)
        #print ('ShowOrHideEventsNotes note : X =',noteAnn.xy[0],'Y =',noteAnn.xy[1],'xytext[0] =',noteAnn.xytext[0],'xytext[1] =',noteAnn.xytext[1])
        #print ('ShowOrHideEventsNotes note : X =', noteAnn.xy[0], 'Y =', noteAnn.xy[1], 'datetime =', estime)

        # If we had to reposition the annotation, save the new location in the database
        if repositioned is True:
            saveAnnToDb(noteAnn)

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
    global sensorWarmupCountDown
    global gluUnits
    global gluMult
    global displayStartDate
    global meanPlot
    global highPercentText
    global midPercentText
    global lowPercentText
    global batt_text
    global lastPowerState
    global lastPowerLevel
    global curSqlMinTime
    global curSqlMaxTime
    global newRange
    global noteTimeSet

    #print ('plotGraph() entry\n++++++++++++++++++++++++++++++++++++++++++++++++')
    if firstPlotGraph == 1:
        if args.debug:
            tr = tracker.SummaryTracker()

        ax = fig.add_subplot(1, 1, 1)
        # rotate labels a bit to use less vertical space
        plt.xticks(rotation=dayRotation)

        # mpl.dates.MinuteLocator(interval=15)
        ax.xaxis.set_major_locator(mpl.dates.DayLocator())
        ax.xaxis.set_minor_locator(mpl.dates.HourLocator())
        ax.xaxis.set_major_formatter(majorFormatter)
        ax.xaxis.set_minor_formatter(minorFormatter)
        ax.autoscale_view()
        ax.grid(True)
        ax.tick_params(direction='out', pad=10)
        ax.set_xlabel('Date & Time', labelpad=-3)
        ax.set_ylabel('Glucose (%s)'%gluUnits, labelpad=10)

        dis_annot = ax.annotate("", xy=(0, 0), xytext=(12, 12), textcoords="offset points",
                                bbox=dict(boxstyle="round", facecolor="w"),
                                arrowprops=dict(arrowstyle="->"), zorder=15)
        dis_annot.set_visible(False)

        # Don't move the following to plotInit() or Scale slider will be messed up
        plt.autoscale(True, 'both', None)

        displayRange = defaultDisplaySecs

        sScale.set_val(100.0*(displayRange-displayRangeMin)/(displayRangeMax-displayRangeMin))

        dispDate = displayStartDate.strftime("%Y-%m-%d")
        posText = axPos.text(0.50, 0.10, dispDate, horizontalalignment='center',
                             verticalalignment='bottom', weight='bold', transform=axPos.transAxes)
        scaleText = axScale.text(0.50, 0.10, SecondsToGeneralTimeString(displayRange),
                                 horizontalalignment='center', verticalalignment='bottom',
                                 weight='bold', transform=axScale.transAxes)

        readRangeFromSql()
        curSqlMaxTime = lastTestSysSecs
        curSqlMinTime = max(lastTestSysSecs - ninetyDaysInSeconds - bufferSeconds, firstTestSysSecs)

        firstPlotGraph = 0

    if restart is True:
        if args.debug:
            print ('Erasing plot data from previous device')
        # erase all previously plotted red calibration regions
        for redmark in redRegionList:
            redmark.remove()
        redRegionList = []
        redStartSet.clear()
        while inRangeRegionAnnotList:
            inRangeItem = inRangeRegionAnnotList.pop(0)
            inRangeItem.remove()
        inRangeRegionAnnotList = []
        while inRangeRegionList:
            inRangeRegionList.pop(0).remove()
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
        cfgDisplayLow = None
        cfgDisplayHigh = None
        restart = False

    #if args.debug:
        #tr.print_diff()

    readRangeFromSql()
    SetCurrentSqlSelectRange(True) # this may modify displayStartSecs, displayEndSecs, curSqlMinTime, curSqlMaxTime
    readDataFromSql(curSqlMinTime, curSqlMaxTime)
    #if position == 100.0:
        #print ('---> At the end position')

    displayStartDate = ReceiverTimeToUtcTime(displayStartSecs).astimezone(mytz)
    if posText:
        posText.set_text(displayStartDate.strftime("%Y-%m-%d"))

    if dbGluUnits != gluUnits:
        if dbGluUnits == 'mmol/L':
            # mmol/L = mg/dL x 0.0555
            gluMult = 0.0555
            scaleText.y = 7.0
        else:
            gluMult = 1.0
            scaleText.y = 70.0
        ax.set_ylabel('Glucose (%s)'%dbGluUnits)
        tgtLowBox.set_val('%g' % round(displayLow * gluMult, tgtDecDigits))
        tgtHighBox.set_val('%g' % round(displayHigh * gluMult, tgtDecDigits))
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

    if newRange is True:
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
        for redmark in redRegionList:
            redmark.remove()
        redRegionList = []
        redStartSet.clear()
        inRangeRegionList = []
        while inRangeRegionAnnotList:
            inRangeItem = inRangeRegionAnnotList.pop(0)
            inRangeItem.remove()
        inRangeRegionAnnotList = []
        inRangeStartSet.clear()

    # mark the desirable glucose region
    if desirableRange:
        # Only redraw desirable range if it has changed since the last drawing
        if (displayLow != cfgDisplayLow) or (displayHigh != cfgDisplayHigh) or (dbGluUnits != gluUnits):

            # Need to clear in target annotations, since the target size has changed
            while inRangeRegionAnnotList:
                inRangeItem = inRangeRegionAnnotList.pop(0)
                inRangeItem.remove()
            inRangeRegionAnnotList = []
            while inRangeRegionList:
                inRangeRegionList.pop(0).remove()
            inRangeRegionList = []
            inRangeStartSet.clear()

            #print ('High/Low value(s) changed')
            cfgDisplayLow = displayLow
            cfgDisplayHigh = displayHigh
            desirableRange.remove()
            desirableRange = plt.axhspan(gluMult * displayLow, gluMult * displayHigh, facecolor='khaki', alpha=1.0)

            # Re-plot percentages high, middle, and low
            highPercentText.remove()
            midPercentText.remove()
            lowPercentText.remove()
            highPercentText = plt.figtext(0.95, ((maxDisplayHigh - displayHigh) / 2.0 + displayHigh) / maxDisplayHigh * graphHeightInFigure + graphBottom,
                                          '%4.1f' %highPercent, style='italic', size=percentFontSize, weight='bold', color='red')
            midPercentText = plt.figtext(0.95, ((displayHigh - displayLow) / 2.0 + displayLow) / maxDisplayHigh * graphHeightInFigure + graphBottom,
                                         '%4.1f' %midPercent, style='italic', size=percentFontSize, weight='bold', color='cornflowerblue')
            lowPercentText = plt.figtext(0.95, displayLow / 2.0 / maxDisplayHigh * graphHeightInFigure + graphBottom,
                                         '%4.1f' %lowPercent, style='italic', size=percentFontSize, weight='bold', color='magenta')
    else:
        #print ('Setting initial High/Low values')
        if cfgDisplayLow is not None:
            displayLow = cfgDisplayLow
        if cfgDisplayHigh is not None:
            displayHigh = cfgDisplayHigh
        desirableRange = plt.axhspan(gluMult * displayLow, gluMult * displayHigh, facecolor='khaki', alpha=1.0)

    #if args.debug:
        #print ('plotGraph() :  After desirableRange() count =', len(muppy.get_objects()))
        #print ('++++++++++++++++++++++++++++++++++++++++++++++++\n')
        #tr.print_diff()

    gluUnits = dbGluUnits

    calcStats()

    if sys.platform == "win32":
        # fig.canvas.set_window_title() hangs forever under Windows, so don't try to use it
        pass
        # The code below writes the string near the top of the window, but not in the window
        # title bar.
        #if gluUnits == 'mmol/L':
            #plt.suptitle('%5.2f %c DexcTrack: %s' % (gluMult * lastRealGluc, trendChar, serialNum))
        #else:
            #plt.suptitle('%u %c DexcTrack: %s' % (lastRealGluc, trendChar, serialNum))
    else:
        # Under some window managers, e.g. MATE, a minimized application
        # will still display the window title, or at least the beginning
        # portion of the window title. We want to include critical
        # information at the beginning of that title, so the user can see
        # the current glucose level and trend.
        # For example, if the current glucose level is 93 and falling, the
        # window title will begin with '93 \'.
        try:
            # During shutdown, set_window_title() can fail with
            # "AttributeError: 'NoneType' object has no attribute 'wm_title'"
            if lastRealGluc == 0:
                fig.canvas.set_window_title('DexcTrack: %s' % (serialNum))
            elif gluUnits == 'mmol/L':
                fig.canvas.set_window_title('%5.2f %c DexcTrack: %s' % (gluMult * lastRealGluc, trendChar, serialNum))
            else:
                fig.canvas.set_window_title('%u %c DexcTrack: %s' % (lastRealGluc, trendChar, serialNum))
        except AttributeError as e:
            #if args.debug:
                #print ('fig.canvas.set_window_title: Exception =', e)
            if sys.version_info < (3, 0):
                sys.exc_clear()

    if egvList:
        data = np.array(egvList)
        xx = []
        yy = []
        xx = data[:, 0] # ReceiverTimeToUtcTime(sysSeconds)
        yy = data[:, 1] # glucose
        #print ('sizeof(data) =',len(data),'sizeof(xx) =',len(xx),'sizeof(yy) =',len(yy))

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
                print ('2 hour prediction : at', predx.astimezone(mytz), 'glucose =', predy)

        # create subset of normal (non-calib) data points
        # and a subset of calibration data points
        cx = []
        cy = []
        cz = []
        cxnorm = []
        cynorm = []
        cznorm = []

        xnorm = xx[yy > 12]
        ynorm = yy[yy > 12] * gluMult

        calibdata = np.array(calibList)
        #print ('sizeof(calibdata) =',len(calibdata))
        if calibdata.size != 0:
            cx = calibdata[:, 0] # sysSeconds
            cy = calibdata[:, 1] # glucose
            cz = calibdata[:, 2] # calibration
            cxnorm = cx[cy > 12]
            #print ('sizeof(xnorm) =',len(xnorm),'sizeof(cx) =',len(cx),'sizeof(cy) =',len(cy),'sizeof(cxnorm) =',len(cxnorm))
            cynorm = cy[cy > 12] * gluMult
            cznorm = cz[cy > 12] * gluMult
            #print ('len(xx) =',len(xx),' len(yy) =',len(yy),' len(cx) =',len(cx),' len(cy) =',len(cy),' len(cxnorm) =',len(cxnorm),' len(cynorm) =',len(cynorm))

        #-----------------------------------------------------
        # Find ranges where we're out of calibration.
        # This implementation only adds new calibration regions.
        # The only one we might need to erase and redraw is a
        # partial region which is increasing in size.
        #-----------------------------------------------------
        calibZoneList = []
        lastx = ReceiverTimeToUtcTime(curSqlMinTime)
        lasty = sqlEarliestGluc
        startOfZone = lastx
        tempRangeEnd = startOfZone
        for pointx, pointy in zip(xx, yy):
            if (lasty <= 12) and (pointy > 12):
                # we've transitioned out of a calib zone
                #print ('calibZoneList[] adding ',startOfZone,'to',pointx)
                calibZoneList.append([startOfZone, pointx])
            elif (lasty > 12) and (pointy <= 12):
                # we've transitioned into a calib zone
                startOfZone = pointx
            lastx = pointx
            lasty = pointy

        #if args.debug:
            #print ('plotGraph() :  After calibZoneList() count =', len(muppy.get_objects()))
            #print ('++++++++++++++++++++++++++++++++++++++++++++++++\n')
            #tr.print_diff()

        # Check for SENSOR_NOT_CALIBRATED or SENSOR_NOT_ACTIVE at the end
        # of the SQL selection.
        if (lasty == 5) or (lasty == 1):
            calibZoneList.append([startOfZone, lastx])
            tempRangeEnd = lastx

        # Check for SENSOR_NOT_CALIBRATED or SENSOR_NOT_ACTIVE as the latest value
        if (lastTestGluc == 5) or (lastTestGluc == 1):
            # We reached the end of the data points while still in
            # an uncalibrated range, so add this final range.
            secsSinceWarmupStart = max(0, lastTestSysSecs - latestSensorInsertTime)
            if secsSinceWarmupStart < sensorWarmupPeriod:
                if args.debug:
                    print ('Sensor Warm-up Time =', secsSinceWarmupStart, 'out of', sensorWarmupPeriod, 'seconds')
                timeLeftSeconds = sensorWarmupPeriod - secsSinceWarmupStart
                timeLeftString = 'Sensor Warm-up Time Left = %u minutes' % (timeLeftSeconds // 60)
                if sensorWarmupCountDown:
                    sensorWarmupCountDown.set_text(timeLeftString)
                else:
                    sensorWarmupCountDown = plt.figtext(.500, .18, timeLeftString,
                                                        backgroundcolor='pink',
                                                        size='xx-large', weight='bold',
                                                        horizontalalignment='center')

                if sys.platform != "win32":
                    # Under some window managers, e.g. MATE, a minimized application
                    # will still display the window title, or at least the beginning
                    # portion of the window title. We want to include critical
                    # information at the beginning of that title, so the user can see
                    # the remaining sensor warm-up time.
                    try:
                        # During shutdown, set_window_title() can fail with
                        # "AttributeError: 'NoneType' object has no attribute 'wm_title'"
                        fig.canvas.set_window_title('%u mins left DexcTrack: %s' % (timeLeftSeconds // 60, serialNum))
                    except AttributeError as e:
                        #if args.debug:
                            #print ('fig.canvas.set_window_title: Exception =', e)
                        if sys.version_info < (3, 0):
                            sys.exc_clear()

                # Say we only have 80 seconds left. We don't want to wait 5 minutes
                # before telling the user that we're ready for calibration, so we'll
                # restart the device reading sequence, with an initial delay of 80 seconds.
                if timeLeftSeconds < meterSamplingPeriod:
                    if rthread is not None:
                        if args.debug:
                            print ('calling restartDelay(firstDelaySecs=%u)' % timeLeftSeconds)
                        rthread.restartDelay(firstDelaySecs=timeLeftSeconds)
                    else:
                        if args.debug:
                            print ('rthread is None')
            elif sensorWarmupCountDown:
                if args.debug:
                    print ('Writing Ready for calibrations message')
                sensorWarmupCountDown.set_text('Ready for calibrations')
        else:
            if sensorWarmupCountDown:
                if args.debug:
                    print ('done with sensorWarmupCountDown')
                sensorWarmupCountDown.remove()
                sensorWarmupCountDown = None

        # Highlight any new out-of-calibration ranges
        redgen = (sr for sr in calibZoneList if mdates.date2num(sr[0]) not in redStartSet)
        for specRange in redgen:
            if temp_red_patch:
                #print ('deleting temp_red_patch ending at', tempRangeEnd)
                temp_red_patch.remove()
                temp_red_patch = None
            #print ('Highlighting out of calibration range',specRange[0],' to',specRange[1])
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
        lastx = ReceiverTimeToUtcTime(curSqlMinTime)
        lasty = sqlEarliestGluc
        startOfZone = lastx
        tempRangeEnd = startOfZone
        for pointx, pointy in zip(xnorm, ynorm):
            if (glucInRange(lasty) is True) and (glucInRange(pointy) is False):
                # we've transitioned out desirable range
                if pointx - startOfZone >= datetime.timedelta(hours=24):
                    #print ('inRangeList[] adding ',startOfZone,'to',pointx)
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
                #print ('inRangeList[] adding ',startOfZone,'to',lastx)
                inRangeList.append([startOfZone, lastx])
            tempRangeEnd = lastx

        # Highlight any in region ranges >= 24 hours
        inRangegen = (sr for sr in inRangeList if mdates.date2num(sr[0]) not in inRangeStartSet)
        for specRange in inRangegen:
            if temp_inRange_patch:
                temp_inRange_patch.remove()
                temp_inRange_Arrow1.remove()
                temp_inRange_Arrow2.remove()
                temp_inRange_Arrow3.remove()
            #print ('Highlighting 24 hour or greater range', specRange[0], ' to', specRange[1])
            inRange_patch = ax.axvspan(mdates.date2num(specRange[0]),
                                       mdates.date2num(specRange[1]),
                                       0.0, 1.0, color='lightsteelblue',
                                       alpha=1.0, zorder=0)

            inRangeArrow1 = ax.annotate('', xy=(mdates.date2num(specRange[0]), gluMult * sqlMaximumGluc * 0.9),
                                        xytext=(mdates.date2num(specRange[1]), gluMult * sqlMaximumGluc * 0.9),
                                        xycoords='data', textcoords='data',
                                        arrowprops=dict(arrowstyle='|-|', color='red', linewidth=4),
                                        annotation_clip=False)
            inRangeArrow2 = ax.annotate('', xy=(mdates.date2num(specRange[0]), gluMult * sqlMaximumGluc * 0.9),
                                        xytext=(mdates.date2num(specRange[1]), gluMult * sqlMaximumGluc * 0.9),
                                        xycoords='data', textcoords='data',
                                        arrowprops=dict(arrowstyle='<->', color='red', linewidth=4),
                                        annotation_clip=False)

            xcenter = mdates.date2num(specRange[0]) + (mdates.date2num(specRange[1])-mdates.date2num(specRange[0]))/2
            inRangeDelta = specRange[1] - specRange[0]
            inRangeHours = inRangeDelta.days * 24 + inRangeDelta.seconds // 3600
            inRangeArrow3 = ax.annotate('%u hours in Target Range!' % inRangeHours,
                                        xy=(xcenter, gluMult * sqlMaximumGluc * 0.94), ha='center',
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

        if args.debug:
            print ('plotGraph() : Before plotting              count =', len(muppy.get_objects()))

        # Set higher zorder to place scatter points on top of line drawing
        # Setting 'picker' allows us to handle hover events later on.
        if egvScatter:
            egvScatter.remove()
        egvScatter = ax.scatter([mdates.date2num(jj) for jj in xnorm], ynorm, s=15, c=kcolor, zorder=8, marker='o', picker=True)
        #if args.debug:
            #print ('plotGraph() : new size(egvScatter) =', len(muppy.get_objects()))

        # Plot the calibration settings with a diamond marker and an errorbar
        if calibScatter:
            calibScatter.remove()
            calibScatter = None

        if calibdata.size != 0:
            # Get slices of negative and positive calibration offsets
            negSlice = np.array([-i for i in cznorm.clip(max=0)])
            posSlice = np.array(cznorm.clip(min=0))
            # Get a slice of absolute values
            absSlice = np.array([abs(i) for i in cznorm])

            # lower & upper limits of the errorbars
            lowerLims = np.array(posSlice, dtype=bool)
            upperLims = np.array(negSlice, dtype=bool)

            calibScatter = ax.errorbar([mdates.date2num(jj) for jj in cxnorm], cynorm,
                                       yerr=absSlice, lolims=lowerLims, uplims=upperLims,
                                       marker='D', linestyle='None', color='black',
                                       elinewidth=2, ecolor='deeppink', picker=True, zorder=10)

            calibZip = zip(cxnorm, cynorm, cznorm)
            for qq in calibZip:
                if qq[0] not in calibDict:
                    if qq[2] >= 0:
                        # plot the calibration value a little above an Up arrow
                        heightOffset = 6 * gluMult
                    else:
                        # plot the calibration value a little below a Down arrow
                        heightOffset = -14 * gluMult
                    # Save the reference to ax.text in a dictionary
                    if gluUnits == 'mmol/L':
                        calibDict[qq[0]] = ax.text(mdates.date2num(qq[0]), qq[1] + qq[2] + heightOffset,
                                                   '%5.2f' % (qq[1] + qq[2]), color='black', ha='center', zorder=18)
                    else:
                        calibDict[qq[0]] = ax.text(mdates.date2num(qq[0]), qq[1] + qq[2] + heightOffset,
                                                   '%d' % (qq[1] + qq[2]), color='black', ha='center', zorder=18)

            #if args.debug:
                #print ('plotGraph() : new size(calibScatter) =', len(muppy.get_objects()))

        if linePlot:
            linePlot.pop(0).remove()
        linePlot = ax.plot(xnorm, ynorm, color='cornflowerblue', zorder=7)
        #if args.debug:
            #print ('After linePlot count =', len(muppy.get_objects()))

        #========================================================================================
        # Plot a running mean as a dashed line

        del runningMean[:]
        runningMean = []
        for nn, gluc in enumerate(ynorm):
            if nn == 0:
                # There is no previous entry. The average, so far, is just this value.
                runningMean.append(float(gluc))
            else:
                runningMean.append(float(nn * runningMean[nn - 1] + gluc) / (nn + 1))
        if meanPlot:
            meanPlot.pop(0).remove()
        meanPlot = ax.plot(xnorm, runningMean, color='firebrick', linewidth=1.0, linestyle='dashed', zorder=3, alpha=0.6)
        #========================================================================================
        newRange = False

        #if args.debug:
            #print ('plotGraph() :  After plots count =', len(muppy.get_objects()))
            #print ('++++++++++++++++++++++++++++++++++++++++++++++++\n')
            #tr.print_diff()

        #=======================================================
        # Annotate the plot with user events and notes
        #=======================================================
        ShowOrHideEventsNotes()
        #if args.debug:
            #print ('After ShowOrHideEventsNotes count =', len(muppy.get_objects()))

    #if args.debug:
        #print ('Before legend count =', len(muppy.get_objects()))
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
                print ('Out of range Legend', (legPosX, legPosY), ' moved to', (legDefaultPosX, legDefaultPosY))
            legPosX = legDefaultPosX
            legPosY = legDefaultPosY

        if desirableRange and red_patch and calibScatter and egvScatter and meanPlot:
            # Add a legend. fontsize = [xx-small, x-small, small, medium, large, x-large, xx-large]
            leg = fig.legend((egvScatter, calibScatter, red_patch, desirableRange, meanPlot[0]),
                             ("Glucose values", "User Calibrations", "Sensor Uncalibrated", "Target Range", "Mean Glucose"),
                             scatterpoints=1, loc=(legPosX, legPosY), fontsize=smallFontSize)
            #if leg:
                ## set the legend as a draggable entity
                #leg.draggable(True)

    #if args.debug:
        #print ('After legend count =', len(muppy.get_objects()))

    #if args.debug:
        #print ('plotGraph() :  After legend count =', len(muppy.get_objects()))
        #print ('++++++++++++++++++++++++++++++++++++++++++++++++\n')
        #tr.print_diff()

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
    elif lastTrend == 0:   # none
        trendRot = 0.0
    else:                  # notComputable (8) | rateOutOfRange (9)
        trendRot = 360.0

    if trendRot < 360.0:
        trendArrow.set_rotation(trendRot)
    #+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

    if (powerState != lastPowerState) or (powerLevel != lastPowerLevel):
        if (batt_text is None) and (powerState is not None):
            batt_text = plt.figtext(battX, battY, '',
                                    backgroundcolor='springgreen', size=largeFontSize,
                                    horizontalalignment='center')
        if batt_text is not None:
            if powerState is None:
                batt_text.remove()
                batt_text = None
            else:
                if powerState == 'CHARGING':
                    if powerLevel == 100:
                        powerStateString = 'Charged'
                    else:
                        powerStateString = 'Charging'
                elif powerState == 'NOT_CHARGING':
                    powerStateString = 'Not Charging'
                elif powerState == 'NTC_FAULT':
                    powerStateString = 'NTC Fault'
                elif powerState == 'BAD_BATTERY':
                    powerStateString = 'Bad Battery'
                else:
                    powerStateString = 'Unknown'

                # Sometimes, even though you've plugged the Receiver into a USB
                # port, charging power is not being applied to that port. In such
                # a case, the power level will drop. When we detect this condition,
                # alert the user by switching to a crimson background, and switch
                # the text to "Draining". This way they will know to try to find
                # an alternate, powered port  to charge their Receiver.
                if powerLevel < lastPowerLevel:
                    # we're losing charge
                    batt_text.set_text('Draining\n%d%%' % powerLevel)
                    if powerLevel < 30:
                        batt_text.set_backgroundcolor('crimson')
                    elif powerLevel < 70:
                        batt_text.set_backgroundcolor('hotpink')
                    else:
                        batt_text.set_backgroundcolor('deeppink')
                else:

                    batt_text.set_text('%s\n%d%%' % (powerStateString, powerLevel))

                    if powerLevel < 30:
                        batt_text.set_backgroundcolor('lightcoral')
                    elif powerLevel < 70:
                        batt_text.set_backgroundcolor('teal')
                    elif powerLevel < 100:
                        batt_text.set_backgroundcolor('springgreen')
                    else:
                        batt_text.set_backgroundcolor('forestgreen')
                batt_text.draw(fig.canvas.get_renderer())

        lastPowerState = powerState
        lastPowerLevel = powerLevel
    #+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

    if args.debug:
        print ('plotGraph() : Before displayCurrentRange() count =', len(muppy.get_objects()))

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
                print ('Legend (X,Y) =', legxy, ', (W,H) =', legwh)

    if args.debug:
        print ('plotGraph() :  After displayCurrentRange() count =', len(muppy.get_objects()))
        print ('++++++++++++++++++++++++++++++++++++++++++++++++\n')
        tr.print_diff()

# end of plotGraph()

fig.canvas.mpl_connect('pick_event', onpick)
fig.canvas.mpl_connect('close_event', onclose)
fig.canvas.mpl_connect('axes_leave_event', leave_axes)


sqlite_file = getSqlFileName(None)
if args.debug:
    print ('sqlite_file =', sqlite_file)
firstPlotGraph = 1
plotInit()
# We need to call plotGraph() before launching the device seek thread because
# that thread could also end up calling plotGraph(). If the seek thread calls
# it first, matplotlib will generate error or warning messages, such as:
# Exception 'main thread is not in main loop', or 'Adding an axes using the
# same arguments as a previous axes currently reuses the earlier instance.
# In a future version, a new instance will always be created and returned.'
plotGraph()
PerodicDeviceSeek()  # launch thread to check for device presence periodically

plt.show()  # This hangs until the user closes the window
#print ('returned from plt.show()')

#-----------------------------------------------------
#
# |<-----------------maxRangeSecs----------------------->|
# |                                                      |
# firstTestSysSecs                                    lastTestSysSecs
#               +================================+
#               |                                |
#               |   <--displayRange-->           |
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
