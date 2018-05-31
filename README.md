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

