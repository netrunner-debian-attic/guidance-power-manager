#!/usr/bin/python
# -*- coding: UTF-8 -*-
###########################################################################
#    Copyright (C) 2006 by Sebastian Kügler                                      
#    <sebas@kde.org>                                                             
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of 
# the License, or (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
###########################################################################
# An API for changing the powerstate of a notebook

import dbus
import dbus.glib
import os, time
##from dcopext import DCOPClient, DCOPApp # Used for kscreensaver
import xf86misc

DEBUG = False

def debug(msg):
    """ Print debug message to terminal. """
    if DEBUG:
        print msg

# Default values for actions when battery runs out.
BATTERY_CRITICAL_MINUTES=5

# Only do an emergency suspend if charge level percentage is below ...
CHARGE_LEVEL_THRESHOLD = 10

isroot = os.environ["USER"] == "root"

# Send suspend / hibernate commands to HAL or use Sx_COMMANDS
SUSPEND_USE_HAL = True

# Show the cpu frequency widgets in the tooltip?
SHOW_CPUFREQ = True


# Command to initiate suspend-to-disk when not using HAL
S4_COMMAND = "/usr/local/bin/hibernate"
# Command to initiate suspend-to-ram when not using HAL
S3_COMMAND = "/usr/local/bin/s2ram"

# Override isLaptop method
#IS_LAPTOP = True

def _readValue(filename, line=0):
    """ Reads a single value from the first line of a file. """
    fhandle = open(filename)
    value = fhandle.readlines()[line][:-1]
    fhandle.close()
    return value

class PowerManage:
    """ Class providing low-level power managerment functionality. """

    def __init__(self):
        # (En|Dis)able using hdparm to set disk timeout
        self.USE_HDPARM = True
        # (En|Dis)able using laptop_mode to make the disk spin up less often        
        self.USE_LAPTOP_MODE = True
        # (En|Dis)able using cpufreq to control cpu frequency scaling
        self.USE_CPUFREQ = True
        # (En|Dis)able using wireless adapter powermanagement (causes lag in network connection)
        self.USE_WI_PM = True
        # (En|Dis)able using display powermanagement
        self.USE_DPMS = True
        # (En|Dis)able using display brightness switching
        self.USE_DISPLAY = True
        # (En|Dis)able screensaver blankonly
        self.SCREENSAVER_BLANKONLY = True


        try:
            xg = xf86misc.XF86Server()
            self.xscreen = xg.getDefaultScreen()
        except xf86misc.XF86Error:
            print "Problem connecting to X server for idletime detection."
        # Currently only used in the test method
        self.display_dark = 0.5
        self.display_light = 1

        # Some status initialisations
        self.lowBatteryState = False
        self.warningBatteryState = False
        self.criticalBatteryState = False

        self.criticalBatteryState = False
        self.lidClosedState = False

        # What does HAL support on this machine
        self.hasBrightness = False
        self.hasAC = False
        self.hasLid = False
        self.hasBattery = False
        self.hasCpuFreqGovernors = False

        # Used to track if the previous check reported a battery to determine
        # if we want to fire a notice "battery removed|plugged in"
        self.wasOnBattery = False
        self._initHAL()
        self._initBrightness()
        self._initBattery()
        self._initAc()
        self._initLid()
        self._checkSuspend()
        self._checkCpuCapabilities()
        self._findDisks()

    def checkHAL(self):
        """ Handle HAL and DBus restarts """
        try:
            self.hal_manager.FindDeviceByCapability("")
        except dbus.DBusException, e:
            if str(e) == 'org.freedesktop.DBus.Error.Disconnected: Connection is closed' \
            or str(e) == 'org.freedesktop.DBus.Error.Disconnected: Connection was disconnected before a reply was received':
                # DBus doesn't support on-the-fly restart
                print "connection with DBus lost, please restart the display manager"
                return

            if os.system("ps aux|grep [h]ald-runner") == 0:
                print "connection with HAL lost, trying to reconnect"
                self._initHAL()
                self._initBrightness()
                self._initBattery()
                self._initAc()
                self._initLid()
                self._checkSuspend()
                self._checkCpuCapabilities()
            else:
                print "HAL is not running"

    def isLaptop(self):
        """ Detect if system is laptop. """
        try:
            return IS_LAPTOP
        except NameError:
            pass
        self.computerObject = self.bus.get_object("org.freedesktop.Hal", 
                                                            u'/org/freedesktop/Hal/devices/computer')
        properties = self.computerObject.GetAllProperties(dbus_interface="org.freedesktop.Hal.Device")
        # formfactor sometimes (ppc) also reports "unknown" for laptops
        # workaround: consider laptop anything with primary battery (see LP #64053)
        return properties["system.formfactor"] == "laptop" or self.hasBattery

    def _findDisks(self):
        """ Scan /sys/block for non-removable and non-ramdisks, used for hdparm actions, 
            currently not implemented in the powermanager frontend. """
        self.disks = []
        blk_path = "/sys/block/"
        for d in os.listdir(blk_path):
            # No RAM disks, no DM-RAID
            if d.startswith("ram") or d.startswith("dm"):
                continue
            fhandle = open(blk_path+d+"/removable")
            if fhandle.readlines()[0][:-1] == "0":
                self.disks.append(d)
        debug("Detected disks: "+" ".join(self.disks))

    def onBattery(self):
        """ Find out if we're on AC or on battery using HAL. """
        if not self.hasAC:
            print "No AC adapter found - assume that we are on batteries."
            return False
        try:
            properties = self.acObject.GetAllProperties(dbus_interface="org.freedesktop.Hal.Device")
            if properties.has_key("ac_adapter.present"):
                return not properties['ac_adapter.present']
            else:
                print "Error: ac_adapter has no property \"present\""
                return False
        except dbus.exceptions.DBusException, msg:
            print "Error: HAL not running"
            return False

    def _initBattery(self):
        """ Looks for a battery in HAL. """
        batteryDevices = self.hal_manager.FindDeviceByCapability("battery")
        self.batteries = {}
        self.batteryIsPresent = {}

        numBatt = 0
        for batt in batteryDevices:
            battObj = self.bus.get_object("org.freedesktop.Hal", batt)
            properties = battObj.GetAllProperties(dbus_interface="org.freedesktop.Hal.Device")
            if properties['battery.type'] != "primary":
                continue
            self.batteries[numBatt] = battObj
            self.batteryIsPresent[numBatt] = properties['battery.present']
            numBatt += 1

        if numBatt > 0:
            self.hasBattery = True
        else:
            self.hasBattery = False
            print "No battery found."

    def getBatteryState(self,batt):
        """ Read battery status from HAL and return 
            (battery state, charge percentage, remaining seconds). 
        """
        try:
            properties = self.batteries[batt].GetAllProperties(dbus_interface="org.freedesktop.Hal.Device")
        except dbus.DBusException:
            print "problem getting battery state from dbus."
            return "not present", 0, 0, 0, 0, 0
        
        if not properties['battery.present']:
            return "not present", 0, 0, 0, 0, 0
        else:
            current = full = level = remain = rate = 0
            if properties.has_key("battery.charge_level.current"):
                current = properties["battery.charge_level.current"]
            if properties.has_key("battery.charge_level.last_full"):
                full = properties["battery.charge_level.last_full"]

            if properties["battery.rechargeable.is_charging"]:
                state = "charging"
            elif properties["battery.rechargeable.is_discharging"]:
                if self.onBattery():
                    state = "discharging"
                else:
                    state = "charged"
            elif not properties["battery.rechargeable.is_discharging"] \
                 and not properties["battery.rechargeable.is_charging"]:
                if current == 0:
                    state = "empty"
                else:
                    state = "charged"
            else:
                print "Unknown battery state ..."

            # Sometimes, HAL doesn't report the percentage, but we can compute that ourselves anyway
            if properties.has_key("battery.charge_level.percentage"):
                level = properties["battery.charge_level.percentage"]
            elif current > 0 and full > 0:
                level = current / full

            if state in ("charging","discharging"):
                if properties.has_key("battery.remaining_time"):
                    remain = properties["battery.remaining_time"]
                if properties.has_key("battery.charge_level.rate"):
                    rate = properties["battery.charge_level.rate"]

            return state, level, remain, rate, current, full

    def showInfo(self):
        """ Outputs some random information to show that it does not work yet. """
        print "OnBattery:", self.onBattery()
        print "CPUs:", len(self.cpus)

    def _initHAL(self):
        """ Initialise HAL client to be used later. """
        self.bus = dbus.SystemBus()
        try:
            hal_manager_obj = self.bus.get_object("org.freedesktop.Hal", "/org/freedesktop/Hal/Manager")
        except dbus.DBusException, e:
            raise Exception('HALD_NOT_RUNNING')
        self.hal_manager = dbus.Interface(hal_manager_obj, "org.freedesktop.Hal.Manager")

    def _initLid(self):
        """ Find out if there's a Lid device. """
        lidDevice = self.hal_manager.FindDeviceStringMatch("button.type", "lid")
        if len(lidDevice) >= 1:
            self.hasLid = True
            self.lidObject = self.bus.get_object("org.freedesktop.Hal" ,lidDevice[0])

    def _initAc(self):
        """ Search HAL for detecting if power is plugged in. """
        acDevice = self.hal_manager.FindDeviceByCapability("ac_adapter")
        if len(acDevice) >= 1:
            self.hasAC = True
            self.acObject = self.bus.get_object("org.freedesktop.Hal" ,acDevice[0])

    def _checkSuspend(self):
        """ Ask HAL whether we can suspend / hibernate. """
        if SUSPEND_USE_HAL:
            self.computerObject = self.bus.get_object("org.freedesktop.Hal", 
                                                        u'/org/freedesktop/Hal/devices/computer')
            properties = self.computerObject.GetAllProperties(
                                                        dbus_interface="org.freedesktop.Hal.Device")
            self.canSuspend = properties["power_management.can_suspend"]
            self.canHibernate = properties["power_management.can_hibernate"]
        else:
            self.canSuspend = self.canHibernate = True

    def _initBrightness(self):
        """ Search HAL for a screen with brightness controls."""

        brightnessDevice = self.hal_manager.FindDeviceByCapability("laptop_panel")

        if len(brightnessDevice) >= 1:
            self.hasBrightness = True
            self.brightnessObject = self.bus.get_object("org.freedesktop.Hal", brightnessDevice[0])
            self.brightness_properties = self.brightnessObject.GetAllProperties(
                                                dbus_interface="org.freedesktop.Hal.Device")
            try: 
                self.brightness_levels = self.brightness_properties[u'laptop_panel.num_levels']
            except KeyError,e:
                self.hasBrightness = False
                return 0 # Really don't know what to do here, but don't crash in any case.
            try:
                self.old_b = self.brightness_levels[-1] # Setting cached brightness value to  brightest
            except TypeError,e:
                return 0 # Really don't know what to do here, but don't crash in any case.
                
    def getBrightness(self):
        """ Read brightness from HAL. """
        if not self.hasBrightness:
            debug("Brightness setting not supported.")
            return
        try:
            b = self.brightnessObject.GetBrightness(
                                            dbus_interface="org.freedesktop.Hal.Device.LaptopPanel")
        except dbus.DBusException, e:
            # Sometimes, right after resume, the HAL call 
            # fails, in that case, we return the last value
            # and hope that it goes well next time.
            print "Warning: in getBrightness(): ", e
            # try and return the old brightness setting, but don't die in any case:
            try:
                return self.old_b
            except AttributeError, errmsg:
                return
        self.old_b = b
        return b

    def adjustBrightness(self, level):
        """ Adjust the brightness via HAL. """
        if not self.hasBrightness:
            debug("Brightness setting not supported.")
            return
        try:
            self.brightnessObject.SetBrightness(level, 
                    dbus_interface="org.freedesktop.Hal.Device.LaptopPanel")
        except dbus.DBusException, e:
            print e

    def _checkCpuCapabilities(self):
        """ Find out the number of CPUs / cores, check which governors are avaible."""
        cpufreq_dir = "/sys/devices/system/cpu"
        self.cpus = []
        for cpu in os.listdir(cpufreq_dir):
            if cpu.startswith('cpu') and cpu != 'cpuidle':
                self.cpus.append(cpu)
        self.cpus.sort()

        # Map our policies to cpufreq governors.
        self.cpu_policy = {}
        self.cpu_policy['dynamic/ac'] = []
        self.cpu_policy['dynamic/battery'] = []
        self.cpu_policy['powersave'] = []
        self.cpu_policy['performance'] = []

        try:
            comp_obj = self.bus.get_object('org.freedesktop.Hal', '/org/freedesktop/Hal/devices/computer')
            self.cpufreq = dbus.Interface(comp_obj, 'org.freedesktop.Hal.Device.CPUFreq')
            self.governor_available = self.cpufreq.GetCPUFreqAvailableGovernors()
        except dbus.DBusException:
            return
        self.hasCpuFreqGovernors = True

        if 'ondemand' in self.governor_available:
            self.cpu_policy['dynamic/ac'].append('ondemand') 
            self.cpu_policy['dynamic/battery'].append('ondemand') 
        if 'conservative' in self.governor_available:
            self.cpu_policy['dynamic/ac'].append('conservative') 
            self.cpu_policy['dynamic/battery'].insert(0,'conservative') 
        if 'userspace' in self.governor_available:
            self.cpu_policy['dynamic/ac'].append('userspace') 
            self.cpu_policy['dynamic/battery'].append('userspace') 
        if 'powersave' in self.governor_available:
            self.cpu_policy['powersave'].append('powersave') 
        if 'performance' in self.governor_available:
            self.cpu_policy['performance'].append('performance') 

    def getSupportedCpuPolicies(self):
        """ Report a list of supported CPU policies """
        policies = []
        if len(self.cpu_policy['dynamic/ac']) > 0:
            policies.append('dynamic')
        if len(self.cpu_policy['powersave']) > 0:
            policies.append('powersave')
        if len(self.cpu_policy['performance']) > 0:
            policies.append('performance')
        return policies

    def getCpuPolicy(self):
        """ Translate current CPU frequency governor into policy """
        if not self.USE_CPUFREQ or not self.hasCpuFreqGovernors:
            return ""
        try:
            gov = self.cpufreq.GetCPUFreqGovernor()
            for policy in self.cpu_policy.keys():
                if gov in self.cpu_policy[policy]:
                    return policy.split('/')[0]   # strip ac or battery off
            return gov  ## return as-is - no conversion
        except dbus.exceptions.DBusException, msg:
            print "Error: HAL not running."
            gov = ''
            return gov

    def setCpuPolicy(self,policy):
        """ Using cpufreq governors. Mode is powersave, dynamic or performance. We're assuming that 
            the available governors are the same for all CPUs. This method changes the cpufreq 
            governor on all CPUs to a certain policy."""
        if not self.USE_CPUFREQ or not self.hasCpuFreqGovernors:
            return False

        if policy == "dynamic":
            if self.onBattery():
               policy = "dynamic/battery"
            else:
               policy = "dynamic/ac"

        for gov in self.cpu_policy[policy]:
            try:
                self.cpufreq.SetCPUFreqGovernor(gov)
                return True
            except dbus.DBusException:
                pass 
        return False # no of governor worked

    def cpuIsOnline(self,cpu):
        """ Check if cpu is online. CPU0 is always online, CPU1 might be unplugged. Since 
            /sys/devices/system/cpu/$cpu/cpufreq is not readable for normal users, we just 
            check for the cpufreq subdir (which is where it's really needed anyway).
        """
        if cpu == "cpu0": return True
        else: return os.path.isdir("/sys/devices/system/cpu/"+cpu+"/cpufreq")

    def getCpuState(self,cpu):
        """ Reads the status of a CPU from /sys. """
        state = {}
        state['online'] = self.cpuIsOnline(cpu)
        if not state['online']:
            debug("getCpuState: "+cpu+" is offline")
            return state
        try:
            state['cpu'] = cpu
            state['cur'] = int(_readValue("/sys/devices/system/cpu/"+cpu+"/cpufreq/scaling_cur_freq"))/1000
            state['governor'] = _readValue("/sys/devices/system/cpu/"+cpu+"/cpufreq/scaling_governor")
            state['driver'] = _readValue("/sys/devices/system/cpu/"+cpu+"/cpufreq/scaling_driver")
            state['steps'] = []
            freqs = _readValue("/sys/devices/system/cpu/"+cpu+"/cpufreq/scaling_available_frequencies")
        except IOError:
            # CPUFREQ has gone away, let's disable it.
            state['online'] = False
            return state
        for v in freqs.split():
            state['steps'].append(int(v)/1000)
        state['max'] = max(state['steps'])
        state['min'] = min(state['steps'])        
        debug(state)
        return state
        
    def getLidClosedState(self):
        """ Returns True if the lid is currently closed, or False if it isn't. """
        try:
            properties = self.lidObject.GetAllProperties(dbus_interface="org.freedesktop.Hal.Device")
            return properties["button.state.value"]
        except (KeyError, dbus.DBusException):
            return False
        
    def setPowerSave(self, state):
        # No SetPowerSave in Ubuntu's HAL
        try:
            self.computerObject.SetPowerSave(state, 
                                dbus_interface="org.freedesktop.Hal.Device.SystemPowerManagement")
        except dbus.DBusException, e:
            print "Warning: While setting SystemPowerManagement to ", state, ": ", 
            print e
        
    def blankScreen(self):
        """ Call dpms to switch off the screen immediately. """
        os.system('xset dpms force standby')

    def setScreensaverBlankOnly(self,blankonly):
        """ Switches a screensaver to blankonly, so cpu hungry screensavers will not drain the poor 
            battery."""
        """
        # create a new DCOP-Client:
        client = DCOPClient()
        # connect the client to the local DCOP-server:
        client.attach()
        # create a DCOP-Application-Object to talk to amarok:
        kdesktop = DCOPApp('kdesktop', client)
        # call a DCOP-function:
        ok, foo = kdesktop.KScreensaverIface.setBlankOnly(blankonly)
        if not ok:
            debug("Failed to set kdesktop screensaver to blankonly.")
            return False
        return True
        """
        print "FIXME setScreensaverBlankOnly"

    def getIdleSeconds(self):
        """ Get idle seconds from X server. """
        return self.xscreen.getIdleSeconds()
        
    def resetIdleSeconds(self):
        """ Reset idle seconds. """
        return self.xscreen.resetIdleSeconds()

    def test(self):
        """ Try all kinds of stuff and see what breaks."""
        print "Trying to adjust brightness ..."
        bright = self.getBrightness()
        self.adjustBrightness(2)
        time.sleep(1)
        self.adjustBrightness(bright)
        print " ... OK."

        if self.USE_CPUFREQ:
            print "Reading speeds from cpufreq..."
            for cpu in self.cpus:
                print self.getCpuState(cpu)
            print "Report supported cpufreq policies..."
            for policy in self.cpu_policy.keys():
                print "Policy:", policy, "=", self.cpu_policy[policy]

            print "Trying all cpufreq policies ..."
            orig_pol = self.getCpuPolicy()
            for pol in self.cpu_policy.keys():
                print ". ", pol
                self.setCpuPolicy(pol)
            self.setCpuPolicy(orig_pol)
            print "... OK."
        else:
            print "Skipping CPUFREQ: USE_CPUFREQ = False"

        if self.SCREENSAVER_BLANKONLY:
            if self.setScreensaverBlankOnly(True):
                debug("Manipulating screensaver seems to work well.")
            else:
                debug("Manipulating screensaver seems broken.")

        if isroot:
            print "Trying to use Disk powermanagement and laptop_mode"
            self.setDiskPM(True)
            time.sleep(1)
            self.setDiskPM(False)
            print "...OK"
        else:
            print "Skipping DiskPM, not root."
            
        if self.hasLid:
            if self.getLidClosedState():
                print "Lid is closed."
            else:
                print "Lid is currently open."

    def setDiskPM(self,on=True):
        """ Switches on laptop_mode and sets disks to advanced powermanagement."""
        if self.USE_LAPTOP_MODE:
            # Check if laptop_mode exists:
            laptop_mode = "/proc/sys/vm/laptop_mode"
            if not os.path.isfile(laptop_mode):
                self.USE_LAPTOP_MODE = False
                debug("Laptop mode not supported, no "+laptop_mode)
            else:
                fhandle = open(laptop_mode,"w")
                if on: val = 1
                else: val = 0
                fhandle.write(str(val))
                fhandle.close()

        if self.USE_HDPARM:
            # Set disks to advanced PM
            for disk in self.disks:
                if on:
                    # Switch on advanced powermanagement
                    cmd = "hdparm -B1 /dev/"+disk+" > /dev/null"
                else:
                    # Switch off advanced powermanagement
                    cmd = "hdparm -B255 /dev/"+disk+" > /dev/null"
                if os.system(cmd) != 0:
                    self.USE_HDPARM = False
                    print "Switching advanced powermanagement failed, not using hdparm anymore"

    def suspend(self):
        """ Run a suspend command, either via HAL or script. """
        if SUSPEND_USE_HAL:
            try:
                self.computerObject.Suspend(0, dbus_interface="org.freedesktop.Hal.Device.SystemPowerManagement")
            except dbus.DBusException:
                pass #we get a DBusException: No reply within specified time
        else:
            self._sleepMode(S3_COMMAND)

    def hibernate(self):
        """ Implements suspend to disk (S4). """
        if SUSPEND_USE_HAL:
            try: 
                self.computerObject.Hibernate(dbus_interface="org.freedesktop.Hal.Device.SystemPowerManagement")
            except dbus.DBusException:
                pass  #we get a DBusException: No reply within specified time
        else:
            self._sleepMode(S4_COMMAND)

    def _sleepMode(self, command):
        """ Send the system into S3 or S4 not using HAL. """
        debug("Initiating a sleep cycle")
        if os.system(command) != 0:
            print "sleepmode failed. ("+command+")"
            return False
        debug("Everything is dandy")
        return True

    def shutdown(self):
        """ Shutdown the system via HAL. """
        self.computerObject.Shutdown(dbus_interface="org.freedesktop.Hal.Device.SystemPowerManagement")


if __name__ == "__main__":
    """ Run some tests, used for debugging."""
    pman = PowerManage()
    pman.showInfo()
    pman.test()

