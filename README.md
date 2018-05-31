# dexctrack
A program to graphically display information from Dexcom Continuous Glucose Monitor receivers

![image](https://user-images.githubusercontent.com/39347592/40751570-5ec24c90-6431-11e8-8490-58426198fcfc.png)

Many thanks to the dexcom_reader project, https://github.com/openaps/dexcom_reader, which provided code used to read information off of Dexcom G4 or G5 receivers.

This is a python program. I recommend installing the latest 2.7.* version from https://www.python.org/downloads/ for whatever operating system you are running on your computer. Mac OSX High Sierra includes python version 2.7.10 as a standard part of the OS, but that version is fairly old, and is missing the **style** which will provide the best looking graph, ***fivethirtyeight***.

You also need to make sure several Python libraries are available. This can be done from a command line with 'pip':

***pip install matplotlib serial pytz tzlocal numpy pympler***

To launch the program invoke ***python dexctrack.py***

To launch in debug mode invoke ***python dexctrack.py -d***

This will print debug text messages to the command line, including memory usage information.

Once the application is running, connect your Dexcom receiver device to your computer using the USB cable. The device will be detected within about 20 seconds, and all of the data on it will be read into an SQLITE database in your home directory. The name of that database includes the serial number of the Dexcom receiver, so if you have multiple users with separate Dexcom devices, their data will not conflict. Each will be written to their own database.

By default, glucose readings from the last day get displayed, and every 5 minutes a new reading is added to the graph.

Use arrow keys <- or -> to scroll the display Date and Time backwards or forwards. You can also hover over a position in the Start Date slider (in blue near the bottom of the screen). The hover position will show the target starting date in parentheses. Click the left mouse button to immediately move to that hover position.

The Scale slider (in green at the bottom of the screen) can be used to zoom the displayed time period in or out. Hover over the slider until the time period you desire is visible in parentheses. Click to set that period.

User added Events get plotted onto the graph. Some effort is taken to avoid collisions between multiple Events, but there will still be collisions fairly often. Each of the Event strings is draggable, so the user can click on a string with the left mouse button to grab a string, drag it to a better location, and then release the mouse button. For example, here you can see that the plotting position for "10 min light exercise" intersects with the plotted line.

![image](https://user-images.githubusercontent.com/39347592/40756240-f3256c3a-6447-11e8-8a65-6aee013b2d5f.png)

Grab it and drag it a bit higher, and we get ...

![image](https://user-images.githubusercontent.com/39347592/40756244-f7c68364-6447-11e8-9872-901a99ff2852.png)

This gives a cleaner image. The new position will get stored in the database, so after quitting and relaunching, this better position will be restored.
