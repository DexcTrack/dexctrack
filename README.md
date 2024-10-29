# dexctrack
A program to graphically display information from Dexcom Continuous Glucose Monitor receivers. This runs using Python on Linux, MacOS, or Windows. It has been tested with G5 and G6 receivers on Linux, MacOS High Sierra, and Windows 10.

</br>

All data read from your Receiver device is stored locally in a database file on your computer. Nothing is written to a remote server or sent to "the cloud". You have complete control and ownership of your private data.

</br>

![image](https://user-images.githubusercontent.com/39347592/116585291-dc2b5c00-a8dd-11eb-8429-72f26af2b536.png)

---
This application supports use of both mg/dL and mmol/L units. It displays using to the units configured on your receiver.

![image](https://user-images.githubusercontent.com/39347592/116585317-e3526a00-a8dd-11eb-9869-20a8d8b3a72e.png)

---

## Installing

>Install the latest version of 'python' for whatever operating system you are running on your computer. For MacOS or Windows, www.python.org/downloads has installation packages with built executables. For Linux, they only provide source code, so you are generally better off using your Linux package manager to install the latest built version.

>Also install 'pip', a tool for installing and managing Python packages. This is included in the installation packages from www.python.org, but if you use a Linux package manager such as 'apt', 'synaptic', 'rpm', or 'dnf' to install 'python', you may need to specify an additional package to get 'pip' installed.

</br>
</br>

- Linux

>1. Install 'python3' and 'pip3'

>>>On apt-based Linux systems (e.g. Mint, Ubuntu, or Debian):

>>>>***sudo apt-get install python3 python3-pip python3-tk***


>>>On rpm-based Linux systems (e.g. Fedora or Red Hat):

>>>>***sudo dnf install python3 python3-pip python3-tkinter***

>2. Install 'git'

>>On apt-based Linux systems (e.g. Mint, Ubuntu, or Debian):

>>>***sudo apt-get install git***

>>On rpm-based Linux systems (e.g. Fedora or Red Hat):

>>>***sudo dnf install git***

>3. Install dexctrack, using 'git'

>>>***git clone https://github.com/DexcTrack/dexctrack.git***

>4. Install required python libraries, using 'pip3'. There are two options.

>>>a) Use a Virtual Environment

>>>>***sudo apt install python3-venv***

</br>

```
$ cd dexctrack/
$ python3 -m venv env
$ source env/bin/activate
(env) $ pip3 install --upgrade setuptools
(env) $ pip3 install matplotlib pyserial pytz tzlocal numpy pympler
```
If you use this option, you'll need to remember to activate the virtual environment prior to launching dexctrack.py.


>>>b) Install required libraries globally
>>>>***sudo pip3 install --upgrade setuptools***

>>>>***sudo pip3 install matplotlib pyserial pytz tzlocal numpy pympler***

>5. Set up permissions to provide the user serial port access to a connected USB device. Implement one of the following options to accomplish this.

>>>a) Add the user account to the ***dialout*** group.

>>>>On Debian-based or Ubuntu-based Linux systems:
>>>>>***sudo addgroup \<username\> dialout***

>>>>On Fedora-based Linux systems:

>>>>>***sudo usermod -a -G \<username\> dialout***

>>>>You may need to log out and back in to make sure the group membership is updated.

>>>b) Install ***udev*** rules to get access to device.

>>>>>***sudo cp dexctrack/etc/udev/rules.d/80-dexcom.rules /etc/udev/rules.d/***

>>>>>***sudo udevadm control --reload-rules***

</br>
</br>

- MacOs

>1. Install 'python3' and 'pip3'

>Mac OSX High Sierra includes python version 2.7.10 as a standard part of the OS, but that version is quite old, and is missing the ***fivethirtyeight*** style which will provide the best looking graphs. Install the latest 3.* release under

>>>https://www.python.org/downloads/mac-osx/

The ***macOS 64-bit installer*** will update your PATH to include the newly installed versions of 'python3' and 'pip3', by adding a few lines to your ~/.bash_profile file.

>2. Install 'git'

>>>https://git-scm.com/downloads

>The following steps should be run from a Terminal. ***Finder -> Go -> Utilities -> Terminal***

>3. Install dexctrack, using 'git'

>>>***git clone https://github.com/DexcTrack/dexctrack.git***

>4. Install required python libraries, using 'pip3'. There are two options.

>>>a) Use a Virtual Environment

>>>>***pip3 install virtualenv***

</br>

```
$ cd dexctrack/
$ python3 -m venv env
$ source env/bin/activate
(env) $ pip3 install --upgrade setuptools
(env) $ pip3 install matplotlib pyserial tzlocal pytz numpy pympler pyobjc
```
If you use this option, you'll need to remember to activate the virtual environment prior to launching dexctrack.py.

>>>b) Install required libraries globally

>>>>***pip3 install --upgrade setuptools***

>>>>***pip3 install matplotlib pyserial tzlocal pytz numpy pympler pyobjc***

</br>
</br>

- Windows

>1. Install 'python' and 'pip'

>>>https://www.python.org/downloads/windows/

>>Update your ***Path*** environmental variable to include paths to the 'python' and 'pip' executables. Menu->Settings and then search for "Edit environment variables for your account". This will open an "Environment Variables" window. Click on the "Path" variable, and then the Edit button. For example, if you've installed into the directory C:\Python, then add

>>>>C:\Python
>>>>C:\Python\Scripts

>>to the ***Path*** variable.

>2. Install 'git'

>>>https://git-scm.com/downloads

>>Update your ***Path*** environmental variable to include a path to the 'git' executable.

>>>>C:\Program Files\Git\bin

>3. Install dexctrack, using 'git'

>>>***git clone https://github.com/DexcTrack/dexctrack.git***

>4. Install required python libraries, using 'pip'. There are two options.

>>>a) Use a Virtual Environment

>>>>***pip install virtualenv***

</br>

```
$ cd dexctrack
$ python -m venv env
$ env\bin\activate.bat
(env) $ pip install --upgrade setuptools
(env) $ pip install matplotlib pyserial tzlocal pytz numpy pympler
```
If you use this option, you'll need to remember to activate the virtual environment prior to launching dexctrack.py.


>>>b) Install required libraries globally

>>>>***pip install --upgrade setuptools***

>>>>***pip install matplotlib pyserial tzlocal pytz numpy pympler***

## Updating

After your initial git clone operation, you can update to the latest release, at any time, by running the following command from within your dexctrack directory.

>***git pull origin master***


## Running

To launch the program, move into the dexctrack/ directory and invoke

>>>***python3 dexctrack.py***

You can add a '-d' option on the end to run in Debug mode. This causes messages to be printed out to the terminal, which can help track down issues. For example ...

>>>***python3 dexctrack.py -d***

</br>

```
> python3 dexctrack.py -d

DexcTrack  Copyright (C) 2018  Steve Erlenborn
This program comes with ABSOLUTELY NO WARRANTY.

get_screen_size width = 1920 , get_screen_size height = 1080 , dispRatio = 1.8 
sys.platform = linux2
backend = TkAgg
matplotlib version = 3.1.1
sqlite_file = /home/steve/dexc_PL75130020.sqlite
rcParams[timezone] = America/Chicago
Latest glucose at 2020-06-02 10:43:36-05:00 = 90
```
</br>

A user reported that all of their time values were off by 8 hours. This may be due to a change in newer firmware releases of the Receiver, or possibly different hardware based on target region. To work around this issue, the '-t' option can be used to set a **time offset**. The general format is +/-hours:min:sec, but the sign, the minutes and the seconds parts are optional.
</br>
```
python3 dexctrack.py -t+8
```
will add eight hours to all of the data read from the Receiver.
</br>

```
python3 dexctrack.py -t-8
```
will subtract eight hours from all of the data read from the Receiver.
</br>

```
python3 dexctrack.py -t-0:30
```
will subtract 30 minutes from all of the data read from the Receiver.
</br>

```
python3 dexctrack.py -t0
```
will return to the default of no offset.
</br>

Setting this **time offset** only needs to be done once. The offset value will be stored into your database. The next time you launch, without a '-t' option, the previously specified offset will be used.
</br>

Once the application is running, a graphical window will be opened. In the lower left corner, the status of the connection to the Receiver device will be displayed.

![image](https://user-images.githubusercontent.com/39347592/40758362-91bbe2e8-6452-11e8-8139-1d99352ca79a.png)

Connect your Dexcom receiver device to your computer using the USB cable. The device will be detected within about 20 seconds, and all of the data on it will be read into an SQLITE database in your home directory.

>Note for the Windows 10 operating system, the USB serial port driver (Usbser.sys) does not properly support USB3 -> USB2 backwards compatibility, so you need to plug into to a USB2 port. Plugging into a USB2 or USB3 port will work fine on Linux or MacOS systems.

![image](https://user-images.githubusercontent.com/39347592/40758366-95861c18-6452-11e8-863b-b66917db71d8.png)

The name of that database includes the serial number of the Dexcom receiver, so if you have multiple users with separate Dexcom devices, their data will not conflict. Each will be written to their own database.

By default, glucose readings from the last day get displayed, and every 5 minutes a new reading is added to the graph.

In the upper right corner, the latest glucose value, the Average and Standard Deviation of glucose values over the last 90 days, and the Hemoglobin A1C value corresponding to the average is displayed. In addition, a Trend arrow indicates whether the glucose value is rising quickly, rising, flat, falling, or falling quickly. In the example below, the Trend is falling.

![image](https://user-images.githubusercontent.com/39347592/42004919-b5bd8c6e-7a37-11e8-911f-cf5cd82aec0e.png)

Use arrow keys <- (Left) or -> (Right) to scroll the display Date and Time backwards or forwards a screen width at a time. Use Alt+Left or Alt+Right to scroll one hour backwards or forwards. You can also hover over a position in the Start Date slider (in blue near the bottom of the screen). The hover position will show the target starting date in parentheses. Click the left mouse button to immediately move to that hover position.

![image](https://user-images.githubusercontent.com/39347592/40758666-1f45d3ca-6454-11e8-99a9-4824f611c793.png)

The Scale slider (in green at the bottom of the screen) can be used to zoom the displayed time period in or out. Hover over the slider until the time period you desire is visible in parentheses. Click to set that period.

![image](https://user-images.githubusercontent.com/39347592/40758670-21c15570-6454-11e8-8cf0-9f14a53fa882.png)

When you scale out to a large time period, the graph could get cluttered with a large number of Event or Note strings. When the number of such strings gets too large (> 30), they get dropped from the display.

![image](https://user-images.githubusercontent.com/39347592/82265795-7e506f00-992d-11ea-84b9-0b44f17562b8.png)

With a smaller time period, user added Events get plotted onto the graph. Some effort is taken to avoid collisions between multiple Events, but there will still be collisions fairly often. Each of the Event strings is draggable, so the user can click on a string with the left mouse button to grab a string, drag it to a better location, and then release the mouse button. For example, here you can see that the plotting position for "10 min light exercise" intersects with the plotted line.

![image](https://user-images.githubusercontent.com/39347592/40756240-f3256c3a-6447-11e8-8a65-6aee013b2d5f.png)

Grab it and drag it a bit higher, and we get ...

![image](https://user-images.githubusercontent.com/39347592/40756244-f7c68364-6447-11e8-9872-901a99ff2852.png)

This gives a cleaner image. The new position will get stored in the database, so after quitting and relaunching, this better position will be restored.

---

Usually, when the Receiver is connected to a USB port, its battery gets recharged. On rare occasions, a computer may stop providing power to a particular USB port. I had mine connected for many hours, but when I detached it to depart from home, I found it had no charge. That was frustrating, so I added a display of the current battery status in the lower right corner, above the "Set New Target Range" button. When the battery is currently charging, the percentage of full charge is displayed in a light green color.

![image](https://user-images.githubusercontent.com/39347592/82259282-e9e00f80-9920-11ea-836d-acf33546fd06.jpg)

When fully charged, this switches to a darker green.

![image](https://user-images.githubusercontent.com/39347592/82259295-f06e8700-9920-11ea-81b2-93bd006d27f6.jpg)

If no power is being provided, and battery charge is decreasing, the status will be labeled "Draining" with a red color.

![image](https://user-images.githubusercontent.com/39347592/82259271-e64c8880-9920-11ea-9ec4-737e04000270.jpg)

If you see such a condition, try disconnecting and reconnecting the USB cable. This usually fixes the problem. If not, you may want to try switching to a different USB port, if available.

---

On the far right side of the graph, there is a grey patch which projects from the current time to one hour in the future. The program uses recent data points to calculate polynomials which estimate the trend of future glucose values.

![image](https://user-images.githubusercontent.com/39347592/116629430-da31bf00-a916-11eb-8be8-46aed4501a14.jpg)

The red dashed line is a one-degree polynomial, also known as a linear equation. The green dashed line is a two-degree polynomial, also known as a quadratic equation. The two-degree polynomial is better at detecting the top or bottom of a parabola in values being mapped, but can swing wildly from one graph draw to the next. The one-degree polynomial is more stable, but is slower to respond to direction changes.

---

Sometimes the Receiver is off in its glucose estimates and you need to enter User Calibration values to nudge it into alignment. Calibrations show up as black diamonds in the graph. When the calibration value does not match the current estimated glucose, a pink arrow pointing to the User Calibration value shows the difference between the estimated glucose value and the entered calibration value. Below is an example of a scenario where the Receiver was estimating a glucose value of 88. A blood glucose test showed the actual value to be 107. A little while later, the Receiver estimated a value of 164. A blood glucose test revealed the actual value to be 138.

![image](https://user-images.githubusercontent.com/39347592/54171281-d34e4680-4447-11e9-96e9-e408319c1e87.png)

If you have many large differences between the estimated and actual blood glucose values, you may be having problems with your current Sensor.

---

You can also use User Calibrations to add data points to your graph. During a 2 hour Sensor warm-up period, the Receiver does not store any automatically detected glucose values, but it will store calibration values. If you  draw a drop of blood from your finger and measure your glucose using a test strip, you can enter that value as a User Calibration on your Receiver device. This value will be displayed as a data point in your Dexctrack graph.

![image](https://user-images.githubusercontent.com/39347592/116631897-82498700-a91b-11eb-8609-57802f4ad399.jpg)

If don't have a new Sensor available yet, you can use your test strips and User Calibrations to track your data over many hours or days.

![image](https://user-images.githubusercontent.com/39347592/116631905-85dd0e00-a91b-11eb-92f4-dc5401c4a0f6.jpg)

---

You can add a Note using the following procedure. First click within the Note box, and enter a string. Hit return when you are done.

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

By default, the Target range is 75 - 200 mg/dL. This range is displayed in the lower right corner of the screen. If you hover the mouse pointer over the low end or high end of the displayed range, the background color will switch to light salmon. This is a hint that the text value can be edited. If you want to set a different target range, use the left mouse button to click in the box showing the low end of the range. This will give you a text cursor which can be used to set a different value. For example, you can switch 75 to 95,

![image](https://user-images.githubusercontent.com/39347592/82259310-f5cbd180-9920-11ea-8e0e-0ea13e77dee6.jpg)

and then either click outside of that text box or hit the Enter key on your keyboard. After doing so, the horizontal gold bar showing the Target range will be adjusted to display the new low end of the range.

![image](https://user-images.githubusercontent.com/39347592/82266143-82c95780-992e-11ea-8e1e-e4a9e7d2d202.png)

Next, you can click within the box showing the high end of the Target Range, and switch that from 200 to 180.

![image](https://user-images.githubusercontent.com/39347592/82259325-fc5a4900-9920-11ea-9fab-dd31d866f38b.jpg)

Click outside of that text box or hit the Enter key on your keyboard. After doing so, the horizontal gold bar showing the Target range will be adjusted to display the new high end of the range.

![image](https://user-images.githubusercontent.com/39347592/82266174-98d71800-992e-11ea-8ea9-5529945c1d29.png)

Glucose values higher than the new range will be colored red and glucose values lower than the new range will be colored magenta.

The Target Range values are saved in your database, so if you quit, and relaunch later, your new Target Range values will be restored. For Receivers with glucose values in mg/dL units, the allowable range values are (40 - 400).

![image](https://user-images.githubusercontent.com/39347592/82266191-a4c2da00-992e-11ea-918c-b5beeb7b3468.png)

For Receivers with glucose values in mmol/L units, the allowable range values are (4.2 - 22.2).

![image](https://user-images.githubusercontent.com/39347592/82266207-ae4c4200-992e-11ea-8a13-002af5260fc0.png)

---

To the right of the graph there are 3 percentages displayed.

![image](https://user-images.githubusercontent.com/39347592/42005454-289a373a-7a3a-11e8-8762-c1e6007a5501.png)

The upper one, colored red shows the percentage of glucose values (in the last 90 days) which are above the Target range. The middle one, colored light blue, shows the percentage of values within the Target range. The lower one, colored magenta, shows the percentage of values below the Target range.

---

Your goal is to stay within your Target Range. If you can do so for at least one day, this accomplishment will be highlighted with a light blue background above and below the Target Range, and a display of the number of hours you've been in range.

![image](https://user-images.githubusercontent.com/39347592/82280040-9804ad00-9953-11ea-807f-54c8a09af202.png)

---

When you disconnect your Receiver device from the computer, say to go exercise, a display of the number of minutes disconnected will be shown.

![image](https://user-images.githubusercontent.com/39347592/82259226-d765d600-9920-11ea-8a7b-61127050233b.jpg)

When you reconnect, this time will be switched from black to grey for a short while, before disappearing.

![image](https://user-images.githubusercontent.com/39347592/82259248-de8ce400-9920-11ea-9751-988d980d23d4.jpg)

---

For some graph resolutions, the Legend is not placed in an ideal location. It is draggable, so you can move it to a better position. Click on the Legend

![image](https://user-images.githubusercontent.com/39347592/116638461-01df5200-a92c-11eb-8190-10b273312602.jpg)

and drag it to a new spot before releasing the mouse button.

![image](https://user-images.githubusercontent.com/39347592/116638469-04da4280-a92c-11eb-8b82-0f45d3bfca1e.jpg)

The new location will be saved to your database, and will be restored the next time you launch the program.

---

Many thanks to the dexcom_reader project, https://github.com/openaps/dexcom_reader, which provided code used to read information off of Dexcom G4 or G5 receivers, and to the developers of the awesome ***matplotlib*** library which is great for drawing graphs.
