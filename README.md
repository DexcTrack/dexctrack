# dexctrack
A program to graphically display information from Dexcom Continuous Glucose Monitor receivers. This is implemented in python (2.7.*), so it will run on Linux, Macintosh OSX, and Windows operating systems. It has been tested with G5 and G6 receivers on Linux, Mac OSX High Sierra, and Windows 10.

![image](https://user-images.githubusercontent.com/39347592/42004451-8605b49e-7a35-11e8-9158-e3468ca495c3.png)

## Installing

>Install the latest 2.7.* version of 'python' for whatever operating system you are running on your computer.

>Also install 'pip', a tool for installing and managing Python packages. This is included in the installation packages from www.python.org, but if you instead, use a package manager such as 'apt', 'synaptic', 'rpm', or 'dnf' to install 'python', you may need to specify an additional package to get 'pip' installed.

- Linux

>1. Install 'python' and 'pip'

>>>On apt-based Linux systems (e.g. Mint, Ubuntu, or Debian):

>>>>***sudo apt-get install python python-pip python-tk python-wxtools libpython2.7-dev***

>>>On rpm-based Linux systems (e.g. Fedora or Red Hat):

>>>>***sudo dnf install redhat-rpm-config python2 python2-devel tkinter wxPython***

>2. Install 'git'

>>On apt-based Linux systems (e.g. Mint, Ubuntu, or Debian):

>>>***sudo apt-get install git***

>>>On rpm-based Linux systems (e.g. Fedora or Red Hat):

>>>***sudo dnf install git***

>3. Install dexctrack, using 'git'

>>>***git clone https://github.com/DexcTrack/dexctrack.git***

>4. Install required python libraries, using 'pip'

>>>***pip install --upgrade setuptools***

>>>***pip install matplotlib pyserial pytz tzlocal numpy pympler***



- MacOs

>1. Install 'python' and 'pip'

>Mac OSX High Sierra includes python version 2.7.10 as a standard part of the OS, but that version is quite old, and is missing the ***fivethirtyeight*** style which will provide the best looking graphs. So, install the latest 2.* release under

>>>https://www.python.org/downloads/

>>Update your PATH environmental variable to include paths to the 'python' and 'pip' executables. This can be done by ...

>>>***echo 'export PATH="/usr/local/opt/python@2/bin:$PATH"' >> ~/.bashrc***


>2. Install 'git'

>>>https://git-scm.com/downloads

>3. Install dexctrack, using 'git'

>>>***git clone https://github.com/DexcTrack/dexctrack.git***

>4. Install required python libraries, using 'pip'

>>>***pip install --upgrade setuptools***

>>>***pip install matplotlib pyserial pytz tzlocal numpy pympler***



- Windows

>1. Install 'python' and 'pip'

>>>https://www.python.org/downloads/

>>Update your ***Path*** environmental variable to include paths to the 'python' and 'pip' executables. Menu->Settings and then search for "Edit environment variables for your account". This will open an "Environment Variables" window. Click on the "Path" variable, and then the Edit button. Add

>>>>C:\Python27
>>>>C:\Python27\Scripts

>>to the ***Path*** variable.

>2. Install 'git'

>>>https://git-scm.com/downloads

>>Update your ***Path*** environmental variable to include a path to the 'git' executable.

>>>>C:\Program Files\Git\bin

>3. Install dexctrack, using 'git'

>>>***git clone https://github.com/DexcTrack/dexctrack.git***

>4. Install required python libraries, using 'pip'

>>>***pip install --upgrade setuptools***

>>>***pip install matplotlib pyserial pytz tzlocal numpy pympler wxpython***

## Running

To launch the program, move into the dexctrack/ directory and invoke

>>>***python dexctrack.py***

or

>>>***python dexctrack.py -d***

to run in Debug mode.

Once the application is running, 

![image](https://user-images.githubusercontent.com/39347592/40758362-91bbe2e8-6452-11e8-8139-1d99352ca79a.png)

connect your Dexcom receiver device to your computer using the USB cable. The device will be detected within about 20 seconds, and all of the data on it will be read into an SQLITE database in your home directory.

>Note for the Windows 10 operating system, the USB serial port driver (Usbser.sys) does not properly support USB3 -> USB2 backwards compatibility, so you need to plug into to a USB2 port. Plugging into a USB2 or USB3 port will work fine on Linux or MacOS systems.

![image](https://user-images.githubusercontent.com/39347592/40758366-95861c18-6452-11e8-863b-b66917db71d8.png)

The name of that database includes the serial number of the Dexcom receiver, so if you have multiple users with separate Dexcom devices, their data will not conflict. Each will be written to their own database.

By default, glucose readings from the last day get displayed, and every 5 minutes a new reading is added to the graph.

In the upper right corner, the latest glucose value, the Average and Standard Deviation of glucose values over the last 90 days, and the Hemoglobin A1C value corresponding to the average is displayed. In addition, a Trend arrow indicates whether the glucose value is rising quickly, rising, flat, falling, or falling quickly. In the example below, the Trend is falling.

![image](https://user-images.githubusercontent.com/39347592/42004919-b5bd8c6e-7a37-11e8-911f-cf5cd82aec0e.png)

Use arrow keys <- or -> to scroll the display Date and Time backwards or forwards. You can also hover over a position in the Start Date slider (in blue near the bottom of the screen). The hover position will show the target starting date in parentheses. Click the left mouse button to immediately move to that hover position.

![image](https://user-images.githubusercontent.com/39347592/40758666-1f45d3ca-6454-11e8-99a9-4824f611c793.png)

The Scale slider (in green at the bottom of the screen) can be used to zoom the displayed time period in or out. Hover over the slider until the time period you desire is visible in parentheses. Click to set that period.

![image](https://user-images.githubusercontent.com/39347592/40758670-21c15570-6454-11e8-8cf0-9f14a53fa882.png)

When you scale out to a large time period, the graph could get cluttered with a large number of Event or Note strings. When the number of such strings gets too large (> 30), they get dropped from the display.

![image](https://user-images.githubusercontent.com/39347592/42005343-818b5596-7a39-11e8-9871-36f07a6b4621.png)

With a smaller time period, user added Events get plotted onto the graph. Some effort is taken to avoid collisions between multiple Events, but there will still be collisions fairly often. Each of the Event strings is draggable, so the user can click on a string with the left mouse button to grab a string, drag it to a better location, and then release the mouse button. For example, here you can see that the plotting position for "10 min light exercise" intersects with the plotted line.

![image](https://user-images.githubusercontent.com/39347592/40756240-f3256c3a-6447-11e8-8a65-6aee013b2d5f.png)

Grab it and drag it a bit higher, and we get ...

![image](https://user-images.githubusercontent.com/39347592/40756244-f7c68364-6447-11e8-9872-901a99ff2852.png)

This gives a cleaner image. The new position will get stored in the database, so after quitting and relaunching, this better position will be restored.

The user can add a Note using the following procedure. First click within the Note box, and enter a string. Hit return when you are done.

![image](https://user-images.githubusercontent.com/39347592/40761833-f9df4634-6462-11e8-9087-4d8388936262.png)

Next, click on a point in the graph with the right or middle mouse button. The string from the Note box will be transferred to that location.

![image](https://user-images.githubusercontent.com/39347592/40761838-ffee91e2-6462-11e8-84a6-032fc44c01c3.png)

Later on, say you want to either remove or edit that Note. Select the graph point with your right or middle mouse button.

![image](https://user-images.githubusercontent.com/39347592/40761846-105defb4-6463-11e8-9f7d-cff6e99b895e.png)

The note is removed from the graph, and placed back into the Note box. You can now click in the Note box, and backspace over the string until it is empty before hitting Return to remove the Note, or you can edit the note string

![image](https://user-images.githubusercontent.com/39347592/40761851-147a9048-6463-11e8-89cd-f0d173c1d88d.png)

and hit Return to place the new Note string into the graph.

![image](https://user-images.githubusercontent.com/39347592/40761853-18f70dc2-6463-11e8-8445-55bc92edba85.png)

Like Events, Notes are draggable, so you can click on the string with your left mouse button, drag it to a better location and then release the mouse button. The updated position will be saved into the database.

![image](https://user-images.githubusercontent.com/39347592/40762389-5cc3f954-6466-11e8-81bd-1d7af4715751.png)

By default, the Target range is 75 - 200 mg/dL. If you want to set a different target range, use the left mouse button to click the 'Set New Target Range' button in the bottom right corner of the screen. This will switch the color of that button from yellow to red.

![image](https://user-images.githubusercontent.com/39347592/40806452-1fcbb222-64e7-11e8-8102-e3a5297ab7d3.png)

Next, use the left mouse button to select a new range. Move the mouse into the plotting area and press the mouse button at the start of the desired vertical range. Hold that button down while moving vertically up or down. Release the button at the end of the desired range. In the example below, the new range is set from 97 to 205 mg/dL.

![image](https://user-images.githubusercontent.com/39347592/40806464-26598006-64e7-11e8-93f8-2540b9b26c4c.png)

The Target range (highlighted in gold color) will then move to the new range. Glucose values higher than this range will be colored read and glucose values lower than this range will be colored magenta.

![image](https://user-images.githubusercontent.com/39347592/40806472-2c8f2ec6-64e7-11e8-9fa0-3201445c371f.png)

---

To the right of the graph there are 3 percentages displayed.

![image](https://user-images.githubusercontent.com/39347592/42005454-289a373a-7a3a-11e8-8762-c1e6007a5501.png)

The upper one, colored red shows the percentage of glucose values (in the last 90 days) which are above the Target range. The middle one, colored light blue, shows the percentage of values within the Target range. The lower one, colored magenta, shows the percentage of values below the Target range.

---

This application supports use of mmol/L units. If your receiver is configured to use those units, that's the way the information will be displayed.

![image](https://user-images.githubusercontent.com/39347592/42004458-8781a38c-7a35-11e8-8adf-f3363759d903.png)

---

Many thanks to the dexcom_reader project, https://github.com/openaps/dexcom_reader, which provided code used to read information off of Dexcom G4 or G5 receivers, and to the developers of the awesome ***matplotlib*** library which is great for drawing graphs.
