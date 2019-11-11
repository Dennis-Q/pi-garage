#!/usr/bin/python3
# -*- coding: utf-8 -*-

import sys, re, argparse
import fcntl
import os
import locale
import time
import datetime
import ephem
import pigpio
import socket
import signal, atexit, traceback
import logging, logging.handlers
import threading

try:
    from myconfig import MyConfig
    from mylog import SetupLogger
    from mylog import MyLog
    from mymqtt import MQTT
    from shutil import copyfile
except Exception as e1:
    print("\n\nThis program requires the modules located from the same github repository that are not present.\n")
    print("Error: " + str(e1))
    sys.exit(2)


class Shutter(MyLog):
    def __init__(self, log = None, config = None):
        super(Shutter, self).__init__()
        self.lock = threading.Lock()
        if log != None:
            self.log = log
        if config != None:
            self.config = config

        if self.config.UPGPIO != None:
           self.UPGPIO=self.config.UPGPIO # relay to rise garage door
        else:   
           self.UPGPIO=18
        if self.config.DOWNGPIO != None:
           self.DOWNGPIO=self.config.DOWNGPIO # # relay to shut garage door
        else:   
           self.DOWNGPIO=4
        if self.config.MOVINGGPIO != None:
           self.MOVINGGPIO=self.config.MOVINGGPIO # Relay to check if garage door is moving
        else:   
           self.MOVINGGPIO=17
        if self.config.CLOSEDGPIO != None:
           self.CLOSEDGPIO=self.config.CLOSEDGPIO # Relay to check if garage door is closed
        else:   
           self.CLOSEDGPIO=24

        self.callback = []
        self.shutterState = {}

    def lower(self, shutterId):
        self.sendCommand(shutterId, "down")
        self.shutterState[shutterId] = 0
        for function in self.callback:
            function(shutterId, 0)

    def rise(self, shutterId):
        self.sendCommand(shutterId, "up")
        self.shutterState[shutterId] = 100
        for function in self.callback:
            function(shutterId, 100)

    # not used for garage ?
    def stop(self, shutterId):
        self.sendCommand(shutterId, "stop")
        
    def registerCallBack(self, callbackFunction):
        self.callback.append(callbackFunction)

    def getState(self, shutterId):
        if shutterId not in self.shutterState:
            self.shutterState[shutterId] = 0
        return self.shutterState[shutterId]

    def sendCommand(self, shutterId, button): #Sending a command
       self.LogDebug("sendCommand: Waiting for Lock")
       self.lock.acquire()
       try:
           self.LogDebug("sendCommand: Lock aquired")
                
           pi = pigpio.pi() # connect to Pi
        
           if not pi.connected:
              exit()
        
           if (button == "down"):
              pi.set_mode(self.DOWNGPIO, pigpio.OUTPUT)
              pi.write(self.DOWNGPIO, 0)
              time.sleep(1)
              pi.write(self.DOWNGPIO, 1)
           elif (button == "up"):
              pi.set_mode(self.UPGPIO, pigpio.OUTPUT)
              pi.write(self.UPGPIO, 0)
              time.sleep(1)
              pi.write(self.UPGPIO, 1)


#           pi.set_mode(self.CLOSEDGPIO, pigpio.INPUT)
#           pi.set_pull_up_down(self.CLOSEDGPIO, pigpio.PUD_UP)
#           self.LogInfo("25 gpio:")
#           pi.set_mode(25, pigpio.INPUT)
#           pi.set_pull_up_down(25, pigpio.PUD_DOWN)
#           self.LogInfo(str(pi.read(25)))
#           pi.set_pull_up_down(25, pigpio.PUD_UP)
#           self.LogInfo(str(pi.read(25)))
#
#           self.LogInfo("24 gpio:")
#           pi.set_mode(24, pigpio.INPUT)
#           pi.set_pull_up_down(24, pigpio.PUD_DOWN)
#           self.LogInfo(str(pi.read(24)))
#           pi.set_pull_up_down(24, pigpio.PUD_UP)
#           self.LogInfo(str(pi.read(24)))

#           self.LogInfo("closed gpio:")
#           pi.set_mode(self.CLOSEDGPIO, pigpio.INPUT)
#           pi.set_pull_up_down(self.CLOSEDGPIO, pigpio.PUD_DOWN)
#           self.LogInfo(str(pi.read(self.CLOSEDGPIO)))
#           pi.set_pull_up_down(self.CLOSEDGPIO, pigpio.PUD_UP)
#           self.LogInfo(str(pi.read(self.CLOSEDGPIO)))

#           self.LogInfo("moving gpio:")
#           pi.set_mode(self.MOVINGGPIO, pigpio.INPUT)
#           pi.set_pull_up_down(self.MOVINGGPIO, pigpio.PUD_DOWN)
#           self.LogInfo(str(pi.read(self.MOVINGGPIO)))
#           pi.set_pull_up_down(self.MOVINGGPIO, pigpio.PUD_UP)
#           self.LogInfo(str(pi.read(self.MOVINGGPIO)))
#           self.LogInfo("GPIO status door closed: " + str(pi.read(self.CLOSEDGPIO)))
#           self.LogInfo("GPIO status door moving: " + str(pi.read(self.MOVINGGPIO)))
        
        #    pi.set_mode(self.TXGPIO, pigpio.OUTPUT)

        #    self.LogInfo ("Button  :      " + "0x%0.2X" % button)
        #    self.LogInfo ("")

        
        
           pi.stop()
       finally:
           self.lock.release()
           self.LogDebug("sendCommand: Lock released")
           
class operateGarage(MyLog):

    def __init__(self, args = None):
        super(operateGarage, self).__init__()
        self.ProgramName = "operate Garage Shutters"
        self.Version = "Unknown"
        self.log = None
        self.IsStopping = False
        self.ProgramComplete = False
        
        if args.ConfigFile == None:
            self.ConfigFile = "/etc/operateGarage.conf"
        else:
            self.ConfigFile = args.ConfigFile

        self.console = SetupLogger("shutters_console", log_file = "", stream = True)
        
        ## should be re-enabled before actual production use
        # if os.geteuid() != 0:
        #     self.LogConsole("You need to have root privileges to run this script.\nPlease try again, this time using 'sudo'.")
        #     sys.exit(1)

        if not os.path.isfile(self.ConfigFile):
            self.LogConsole("Creating new config file : " + self.ConfigFile)
            defaultConfigFile = os.path.dirname(os.path.realpath(__file__))+'/defaultConfig.conf'
            print(defaultConfigFile)
            if not os.path.isfile(defaultConfigFile):
                self.LogConsole("Failure to create new config file: "+defaultConfigFile)
                sys.exit(1)
            else: 
                copyfile(defaultConfigFile, self.ConfigFile)

        # read config file
        self.config = MyConfig(filename = self.ConfigFile, log = self.console)
        result = self.config.LoadConfig()
        if not result:
            self.LogConsole("Failure to load configuration parameters")
            sys.exit(1)

        # log errors in this module to a file
        self.log = SetupLogger("shutters", self.config.LogLocation + "operateGarage.log")
        self.config.log = self.log
        
        if self.IsLoaded():
            self.LogWarn("operateGarage.py is already loaded.")
            sys.exit(1)

        if not self.startPIGPIO():
            self.LogConsole("Not able to start PIGPIO")
            sys.exit(1)
            
        self.shutter = Shutter(log = self.log, config = self.config)

        # atexit.register(self.Close)
        # signal.signal(signal.SIGTERM, self.Close)
        # signal.signal(signal.SIGINT, self.Close)

        self.mqtt = MQTT(kwargs={'log':self.log, 'shutter': self.shutter, 'config': self.config})

        self.ProcessCommand(args)

    #------------------------ operateGarage::IsLoaded -----------------------------
    #return true if program is already loaded
    def IsLoaded(self):

        file_path = '/var/lock/'+os.path.basename(__file__)
        global file_handle

        try:
           file_handle= open(file_path, 'w')
           fcntl.lockf(file_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
           return False
        except IOError:
           return True
	      
    #--------------------- operateGarage::startPIGPIO ------------------------------
    def startPIGPIO(self):
       if sys.version_info[0] < 3:
           import commands
           status, process = commands.getstatusoutput('pidof pigpiod')
           if status:  #  it wasn't running, so start it
               self.LogInfo ("pigpiod was not running")
               commands.getstatusoutput('sudo pigpiod -l -n localhost')  # try to  start it
               time.sleep(0.5)
               # check it again        
               status, process = commands.getstatusoutput('pidof pigpiod')
       else:      
           import subprocess
           status, process = subprocess.getstatusoutput('pidof pigpiod')
           if status:  #  it wasn't running, so start it
               self.LogInfo ("pigpiod was not running")
               subprocess.getstatusoutput('sudo pigpiod -l -n localhost')  # try to  start it
               time.sleep(0.5)
               # check it again        
               status, process = subprocess.getstatusoutput('pidof pigpiod')
       
       if not status:  # if it was started successfully (or was already running)...
           pigpiod_process = process
           self.LogInfo ("pigpiod is running, process ID is {} ".format(pigpiod_process))
       
           try:
               pi = pigpio.pi()  # local GPIO only
               self.LogInfo ("pigpio's pi instantiated")
           except Exception as e:
               start_pigpiod_exception = str(e)
               self.LogError ("problem instantiating pi: {}".format(start_pigpiod_exception))
       else:
           self.LogError ("start pigpiod was unsuccessful.")
           return False
       return True

    #--------------------- operateGarage::ProcessCommand -----------------------------------------------
    def ProcessCommand(self, args):
       if ((args.shutterName != "") and (args.down == True)):
             self.shutter.lower(self.config.ShuttersByName[args.shutterName])
       elif ((args.shutterName != "") and (args.up == True)): 
             self.shutter.rise(self.config.ShuttersByName[args.shutterName])
       elif ((args.shutterName != "") and (args.stop == True)):
             self.shutter.stop(self.config.ShuttersByName[args.shutterName])
       elif (args.mqtt == True):
             self.mqtt.setDaemon(True)
             self.mqtt.start()

       else:
          parser.print_help()

    #    if (args.mqtt == True):
    #        self.mqtt.setDaemon(True)
    #        self.mqtt.start()

       if (args.mqtt == True):
           self.mqtt.join()
       self.LogInfo ("Process Command Completed....")      
       self.Close()
    
    #---------------------operateGarage::Close----------------------------------------
    def Close(self, signum = None, frame = None):

        # we dont really care about the errors that may be generated on shutdown
        try:
            self.IsStopping = True
        except Exception as e1:
            self.LogErrorLine("Error Closing Monitor: " + str(e1))

        self.LogError("operateGarage Shutdown")
        
        try:
            self.ProgramComplete = True
            if (not self.mqtt == None):
                self.LogError("Stopping MQTT Listener. This can take up to 1 second...")
                self.mqtt.shutdown_flag.set()
                self.mqtt.join()
                self.LogError("MQTT Listener stopped. Now exiting.")
            sys.exit(0)
        except:
            pass

#------------------- Command-line interface for monitor ------------------------

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='operate Garage Shutters.')
    parser.add_argument('shutterName', nargs='?', help='Name of the Shutter')
    parser.add_argument('-config', '-c', dest='ConfigFile', default=os.getcwd()+'/operateGarage.conf', help='Name of the Config File (incl full Path)')
    parser.add_argument('-up', '-u', help='Raise the Shutter', action='store_true')
    parser.add_argument('-down', '-d', help='lower the Shutter', action='store_true')
    parser.add_argument('-stop', '-s', help='stop the Shutter', action='store_true')
    parser.add_argument('-mqtt', '-m', help='Enable MQTT integration', action='store_true')
    args = parser.parse_args()
    
    #Start things up
    MyShutter = operateGarage(args = args)

    try:
        while not MyShutter.ProgramComplete:
            time.sleep(0.01)
        sys.exit(0)
    except:
        sys.exit(1)



