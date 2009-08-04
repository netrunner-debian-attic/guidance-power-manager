#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Copyright 2006-2008 Sebastian Kügler, Canonical Ltd, Luka Renko

Authors:
    Sebastian Kügler <sebas@kde.org>
    Jonathan Riddell <jriddell@ubuntu.com>
    Luka Renko <lure@kubuntu.org>

This program is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License as
published by the Free Software Foundation; either version 2 of
the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""

import sys
import time

from PyKDE4.kdecore import KAboutData, KCmdLineArgs, KConfig, i18n, i18nc, i18np, ki18n, ki18nc, KGlobal, KStandardDirs, KLocalizedString
from PyKDE4.kdeui import KUniqueApplication, KApplication,KSystemTrayIcon, UserIcon, KDialog, SmallIcon, KAboutApplicationDialog, KPassivePopup, KMenu, KAction, BarIcon, KShortcut, KXmlGuiWindow, KActionCollection

from PyQt4.QtGui import *
from PyQt4.QtCore import *
from PyQt4 import uic

from powermanage import *

POLL_INTERVAL = 5000 # in milliseconds

class PowerManager(QWidget):
    """ Our configuration dialog. """

    def __init__(self, parent):

        def powerstart(self):
            try:
                self.powermanager = PowerManage()
            except Exception,e:
                print "Is Hal running? Failed with error: ", e
                print "Will try again to connect to HAL in 30 seconds."
                time.sleep(30)
                powerstart(self)

        QWidget.__init__(self, parent)

        #Use local files if in current directory
        if os.path.exists("guidance-power-manager.ui"):
            APPDIR = QDir.currentPath()
        else:
            file =  KStandardDirs.locate("appdata", "guidance-power-manager.ui")
            APPDIR = file.left(file.lastIndexOf("/"))

        uic.loadUi(APPDIR + "/" + "guidance-power-manager.ui", self)

        # The systray icon should show and hide the KDialogBase, not only this widget,
        # therefore, it gets our parent as parent.
        self.systray = SystemTrayIcon(parent)
        self.icon = "battery-charging"
        self.systray.setIcon(QIcon(BarIcon(self.icon)))

        # Configuration file
        app = KApplication.kApplication()
        config = KGlobal.config()
        self.config = config.group("power-manager")

        powerstart(self)

    def prepare(self):
        """ Prepare UI. """
        self._initBrightness()
        self._initLid()
        self._initBattery()
        self.lastidlesec = 0

        self._initConfigKeywords()

        self._initUI(self.parent())

        self.configToUi()

        # Polling: evil.  can't receive signals in python-dbus unless we have a glib mainloop,
        # so we need to poll
        self.pollTimer = QTimer(self)
        self.connect(self.pollTimer, SIGNAL("timeout()"), self.poll)
        self.pollTimer.start(POLL_INTERVAL) # 5 second poll, maybe make this configurable
        self.poll(False)

        # check CPU freq policy and notify if it was changed
        msg = self.checkCpuFreq()
        if msg != "":
            self.notify(msg)

        self.systray.show()

    def _initBrightness(self):
        """ Check for brightness support and disable widgets if it's not there. """
        if not self.powermanager.hasBrightness:
            self.PoweredBrightnessLabel.hide()
            self.PoweredBrightnessSlider.hide()
            self.BatteryBrightnessLabel.hide()
            self.BatteryBrightnessSlider.hide()

    def _initLid(self):
        """ Check for lid support and disable widgets if it's not there. """
        if not self.powermanager.hasLid:
            self.LaptopLidRadios.setEnabled(False)

    def _initCB(self, combo, options, values):
        """ Initialize QComboBox with proper values from provided options. """
        combo.clear()
        for option in options:
            combo.insertItem(999, values[option])

    def _getCB(self, combo, options):
        """ Get current item from QComboBox from config file (string) value. """
        try:
            return options[combo.currentIndex()]
        except IndexError:
            return ""

    def _setCB(self, combo, options, default, value):
        """ Set current item in QComboBox from string value. """
        try:
            num = options.index(value)
        except ValueError:
            num = default
            pass
        combo.setCurrentIndex(num)

    def _getRB(self, radios, options):
        """ Get current item from QRadioButton from config file (string) value. """
        try:
            for button in self.radioButtonIndex:
                if button.isChecked():
                    selected = button
            return options[self.radioButtonIndex.index(selected)]
        except IndexError:
            return ""

    def _setRB(self, radios, options, default, value):
        """ Set current item in QRadioButton from string value. """
        try:
            num = options.index(value)
        except ValueError:
            num = default
            pass
        button = self.radioButtonIndex[num]
        button.setChecked(True)

    def _checkOldConfig(self, value, blank):
        """ Convert old numerical values to keywords. """
        try:
            num_val = value.toInt()[0]
        except ValueError:
            return value
        if blank:
            if num_val == 0: return 'nothing'
            if num_val == 1: return 'blank'
            if num_val == 2: return 'suspend'
            if num_val == 3: return 'hibernate'
            if num_val == 4: return 'shutdown'
        else:
            if num_val == 0: return 'nothing'
            if num_val == 1: return 'suspend'
            if num_val == 2: return 'hibernate'
            if num_val == 3: return 'shutdown'
        return value

    def _initConfigKeywords(self):
        """ Define helper maps used with config file keywords. """
        # map action keyword to displayed name (l10n)
        self.act_name = {}
        self.act_name['nothing'] = i18n("Do nothing")
        self.act_name['blank'] = i18n("Blank screen")
        self.act_name['suspend'] = i18n("Suspend")
        self.act_name['hibernate'] = i18n("Hibernate")
        self.act_name['shutdown'] = i18n("Shutdown")

        # map action keyword to action methods
        self.act_call = {}
        self.act_call['nothing'] = None
        self.act_call['blank'] = self.blankScreen
        self.act_call['suspend'] = self.suspend
        self.act_call['hibernate'] = self.hibernate
        self.act_call['shutdown'] = self.shutdown

        # map action keyword to action icon used in notification window
        self.act_icon = {}
        self.act_icon['nothing'] = None
        self.act_icon['blank'] = None
        self.act_icon['suspend'] = SmallIcon("system-suspend")
        self.act_icon['hibernate'] = SmallIcon("system-suspend-hibernate")
        self.act_icon['shutdown'] = SmallIcon("system-shutdown")

        # map policy keyword to displayed name (l10n)
        self.freq_name = {}
        self.freq_name['dynamic'] = i18nc("CPU policy", "Dynamic")
        self.freq_name['powersave'] = i18nc("CPU policy", "Powersave")
        self.freq_name['performance'] = i18nc("CPU policy", "Performance")

        # map policy keyword to policy change methods
        self.freq_call = {}
        self.freq_call['dynamic'] = self.setCpuPolicyDynamic
        self.freq_call['powersave'] = self.setCpuPolicyPowersave
        self.freq_call['performance'] = self.setCpuPolicyPerformance

    def _initUI(self, parent):
        """ Build dynamic parts of the UI: context menu and tooltip. """
        disableSuspend = self.config.readEntry("disableSuspend", QVariant(False)).toBool()
        disableHibernate = self.config.readEntry("disableHibernate", QVariant(False)).toBool()
        self.canSuspend = self.powermanager.canSuspend and not disableSuspend
        self.canHibernate = self.powermanager.canHibernate and not disableHibernate

        # Connect some signals.  Updates in the dialogue apply instantly
        self.connect(self.PoweredBrightnessSlider, SIGNAL("valueChanged(int)"), self.changePoweredBrightness)
        self.connect(self.BatteryBrightnessSlider, SIGNAL("valueChanged(int)"), self.changeBatteryBrightness)

        self.tooltip = QFrame()
        self.tooltip.setFrameStyle(QFrame.Box | QFrame.Plain)
        #set widget to use tooltip colours
        palette = self.tooltip.palette()
        palette.setColor(QPalette.Window, palette.color(QPalette.ToolTipBase))
        palette.setColor(QPalette.WindowText, palette.color(QPalette.ToolTipText))
        self.tooltip.setLayout(QVBoxLayout())
        self.systray.setToolTip(self.tooltip)

        self._addBatteryWidgets()

        self._addCpuWidgets()

        # fill actions for LID
        self.lid_act = ['nothing', 'blank', 'suspend', 'hibernate', 'shutdown']
        self.lid_act_def = 0
        # hide LID close actions that are not supported
        if not self.canSuspend:
            self.laptopClosedSuspend.hide()
        if not self.canHibernate:
            self.laptopClosedHibernate.hide()

        # fill in only CPU policies that are supported by HW
        self.cb_freq = []       # list of supported cpu freq policies
        self.cb_freq_def = 0    # always use first policy as default
        if self.powermanager.hasCpuFreqGovernors:
            self.cb_freq = self.powermanager.getSupportedCpuPolicies()
        if len(self.cb_freq) > 0:
            self._initCB(self.PoweredFreqCombo, self.cb_freq, self.freq_name)
            self._initCB(self.BatteryFreqCombo, self.cb_freq, self.freq_name)
        else:
            self.PoweredFreqLabel.hide()
            self.PoweredFreqCombo.hide()
            self.BatteryFreqLabel.hide()
            self.BatteryFreqCombo.hide()

        # fill actions in Idle/Critical battery combo boxes
        self.cb_act = ['nothing']       # list of supported actions (keywords)
        self.cb_act_def_critical = 0    # default action when critical battery
        if self.canSuspend:
            self.cb_act.append('suspend')
        if self.canHibernate:
            self.cb_act.append('hibernate')
            self.cb_act_def_critical = len(self.cb_act) - 1 # hibernate
        self.cb_act.append('shutdown')
        if self.cb_act_def_critical == 0:
            self.cb_act_def_critical = len(self.cb_act) - 1  # shutdown
        self._initCB(self.PoweredIdleCombo, self.cb_act, self.act_name)
        self._initCB(self.BatteryIdleCombo, self.cb_act, self.act_name)
        self._initCB(self.BatteryCriticalCombo, self.cb_act, self.act_name)

        self.connect(self.PoweredIdleCombo,SIGNAL("activated(int)"),self.slotPoweredIdleActivated)
        self.connect(self.BatteryIdleCombo,SIGNAL("activated(int)"),self.slotBatteryIdleActivated)
        self.connect(self.BatteryCriticalCombo,SIGNAL("activated(int)"),self.slotBatteryCriticalActivated)

        # add suspend/hibernate to tray's context menu
        menu = self.systray.contextMenu()
        if self.canSuspend:
            suspendAction = self.systray.actionCollection().addAction("suspend")
            suspendAction.setText(i18n("Suspend"))
            suspendAction.setIcon(QIcon(self.act_icon['suspend']))
            self.connect(suspendAction, SIGNAL("triggered()"), self.suspend)
            menu.addAction(suspendAction)
        if self.canHibernate:
            hibernateAction = self.systray.actionCollection().addAction("hibernate")
            hibernateAction.setText(i18n("Hibernate"))
            hibernateAction.setIcon(QIcon(self.act_icon['hibernate']))
            self.connect(hibernateAction, SIGNAL("triggered()"), self.hibernate)
            menu.addAction(hibernateAction)

        # In KDE 4 it seems we can't attach to X keysyms, only Qt keys.
        # For no good reason whatsoever Qt turns XF86Launch4 into Qt::Key_Launch6, see qt4-x11-4.4.1/gui/kernel/qkeymapper_x11.cpp
        # and does not map XF86LaunchE or XF86Sleep etc.
        # In Kubuntu we map keys using a custom xmodmap file from the kubuntu-default-settings package which is loaded on starting X, 
        # other distros will need to do something similar.
        brightnessUpAction = self.systray.actionCollection().addAction("brightness_up")
        brightnessUpAction.setText("Brightness Up")
        brightnessUpAction.setShortcut(KShortcut(Qt.Key_Launch6))
        brightnessUpAction.setGlobalShortcut(KShortcut(Qt.Key_Launch6))
        self.connect(brightnessUpAction, SIGNAL("triggered(bool)"), self.setBrightnessUp)

        brightnessUpAction = self.systray.actionCollection().addAction("brightness_down")
        brightnessUpAction.setText("Brightness Down")
        brightnessUpAction.setShortcut(KShortcut(Qt.Key_Launch5))
        brightnessUpAction.setGlobalShortcut(KShortcut(Qt.Key_Launch5))
        self.connect(brightnessUpAction, SIGNAL("triggered(bool)"), self.setBrightnessDown)

        standbyAction = self.systray.actionCollection().addAction("standby")
        standbyAction.setText("Standby")
        standbyAction.setShortcut(KShortcut(Qt.Key_Standby))
        standbyAction.setGlobalShortcut(KShortcut(Qt.Key_Standby))
        self.connect(standbyAction, SIGNAL("triggered(bool)"), self.suspend)

        # add list of cpu frequency governors
        if self.powermanager.hasCpuFreqGovernors and len(self.cb_freq) > 0:
            submenu = KMenu(menu)
            actionGroup = QActionGroup(self)
            actionGroup.setExclusive(True)
            currentPolicy = self.powermanager.getCpuPolicy()
            self.policyActions = {}
            for policy in self.cb_freq:
                action = KAction(self.freq_name[policy], actionGroup)
                action.setCheckable(True)
                self.policyActions[policy] = action
                self.connect(action, SIGNAL("triggered()"), self.freq_call[policy])
                submenu.addAction(action)
                if policy == currentPolicy:
                    action.setChecked(True)

            submenu.setTitle(i18n("CPU policy"))
            menu.addMenu(submenu)

        # KGlobalAccel crashes the application in pykde
        # see http://mats.gmd.de/pipermail/pykde/2006-May/013224.html
        #self.globalActions = KGlobalAccel(self)
        #self.suspendShortcut = KShortcut("XF86Sleep")
        #self.hibernateShortcut = KShortcut("XF86Standby")
        #self.hshutdownShortcut = KShortcut("XF86PowerOff")
        #self.globalActions.insert("suspend", i18n("Suspend"), i18n("what's this?"), self.suspendShortcut, #self.suspendShortcut, self.suspend)
        #self.globalActions.updateConnections()

        self.radioButtonIndex = [self.laptopClosedNone, self.laptopClosedBlank, self.laptopClosedSuspend, self.laptopClosedHibernate, self.laptopClosedShutdown]

    def setBrightness(self):
        print "setbrightness"

    def _initBattery(self):
        """ Remove non-battery-related widgets if there's no battery bay. """
        if not self.powermanager.hasBattery:
            # Disable the Batterybox in the config dialogue,
            self.BatteryBox.setEnabled(False)
            # And change the icon in the systray, remove the restore option
            # This way, we're basically becoming a systray applet, you can
            # hibernate and suspend from
            self.systray.setIcon(QIcon(BarIcon(self.icon)))
        if self.powermanager.hasAC:
            self.wasOnBattery = self.powermanager.onBattery()

    def configToUi(self):
        """ Setup the the values from the config file in the UI."""
        # brightness.
        if self.powermanager.hasBrightness:
            brightness_high = self.powermanager.brightness_levels
            self.BatteryBrightnessSlider.setMaximum(self.powermanager.brightness_levels-1)
            self.PoweredBrightnessSlider.setMaximum(self.powermanager.brightness_levels-1)
            batteryBrightness = self.config.readEntry("batteryBrightness", QVariant(int(brightness_high/2)))
            batteryBrightness = batteryBrightness.toInt()
            batteryBrightness = batteryBrightness[0]
            poweredBrightness = self.config.readEntry("poweredBrightness", QVariant(brightness_high))
            poweredBrightness = poweredBrightness.toInt()
            poweredBrightness = poweredBrightness[0]
            self.BatteryBrightnessSlider.setValue(batteryBrightness) #default middle
            self.PoweredBrightnessSlider.setValue(poweredBrightness) #default highest

            tt_text = "Every step increases or decreases the brightness by %i%%" % int(100/brightness_high)
            self.BatteryBrightnessSlider.setToolTip(tt_text)
            self.PoweredBrightnessSlider.setToolTip(tt_text)

        lockOnResume = self.config.readEntry("lockOnResume", QVariant(True))
        lockOnResume = lockOnResume.toBool()
        self.lockScreenOnResume.setChecked(lockOnResume)

        # Idletime-related configuration
        self._setCB(self.PoweredIdleCombo, self.cb_act, 0, str(self.config.readEntry("poweredIdleAction")))
        poweredIdleTime = self.config.readEntry("poweredIdleTime", QVariant(60))
        poweredIdleTime = poweredIdleTime.toInt()
        poweredIdleTime = poweredIdleTime[0]
        self.PoweredIdleTime.setValue(poweredIdleTime)
        self._setCB(self.BatteryIdleCombo, self.cb_act, 0, str(self.config.readEntry("batteryIdleAction")))
        batteryIdleTime = self.config.readEntry("batteryIdleTime", QVariant(10))
        batteryIdleTime = batteryIdleTime.toInt()
        batteryIdleTime = batteryIdleTime[0]
        self.BatteryIdleTime.setValue(batteryIdleTime)

        self._setCB(self.PoweredFreqCombo, self.cb_freq, self.cb_freq_def, str(self.config.readEntry("poweredFreqPolicy")))
        self._setCB(self.BatteryFreqCombo, self.cb_freq, self.cb_freq_def, str(self.config.readEntry("batteryFreqPolicy")))

        batteryIdleTime = self.config.readEntry("batteryIdleTime", QVariant(10))
        batteryIdleTime = batteryIdleTime.toInt()
        batteryIdleTime = batteryIdleTime[0]
        self.BatteryIdleTime.setValue(batteryIdleTime) # default Do nothing
        # battery critical and lid actions.
        self._setCB(self.BatteryCriticalCombo, self.cb_act, self.cb_act_def_critical, self._checkOldConfig(self.config.readEntry("batteryCriticalAction", ""), False))
        self._setRB(self.LaptopLidRadios, self.lid_act, self.lid_act_def, self._checkOldConfig(self.config.readEntry("laptopLidAction", ""), True))
        criticalRemainTime = self.config.readEntry("criticalRemainTime", QVariant(BATTERY_CRITICAL_MINUTES))
        criticalRemainTime = criticalRemainTime.toInt()
        criticalRemainTime = criticalRemainTime[0]
        self.CriticalRemainTime.setValue(criticalRemainTime)
        self.criticalLevel = self.CriticalRemainTime.value()

        # Call some slots to disable various spinboxes if necessary
        self.slotBatteryCriticalActivated()
        self.slotPoweredIdleActivated()
        self.slotBatteryIdleActivated()

    def uiToConfig(self):
        """ Read all values from the UI and write them to the config file. """
        self.config.writeEntry("poweredBrightness", QVariant(self.PoweredBrightnessSlider.value()))
        self.config.writeEntry("batteryBrightness", QVariant(self.BatteryBrightnessSlider.value()))

        self.config.writeEntry("poweredIdleTime", QVariant(self.PoweredIdleTime.value()))
        self.config.writeEntry("poweredIdleAction", QVariant(self._getCB(self.PoweredIdleCombo, self.cb_act)))
        self.config.writeEntry("batteryIdleTime", QVariant(self.BatteryIdleTime.value()))
        self.config.writeEntry("batteryIdleAction", QVariant(self._getCB(self.BatteryIdleCombo, self.cb_act)))
        self.config.writeEntry("poweredFreqPolicy", QVariant(self._getCB(self.PoweredFreqCombo, self.cb_freq)))
        self.config.writeEntry("batteryFreqPolicy", QVariant(self._getCB(self.BatteryFreqCombo, self.cb_freq)))

        self.config.writeEntry("batteryCriticalAction", QVariant(self._getCB(self.BatteryCriticalCombo, self.cb_act)))
        self.config.writeEntry("criticalRemainTime", QVariant(self.CriticalRemainTime.value()))

        self.config.writeEntry("laptopLidAction", QVariant(self._getRB(self.LaptopLidRadios, self.lid_act)))
        self.config.writeEntry("lockOnResume", QVariant(self.lockScreenOnResume.isChecked()))

        self.criticalLevel = self.CriticalRemainTime.value()

        self.config.sync()

    def showBrightnessPopup(self):
        if self.powermanager.onBattery():
            value=self.BatteryBrightnessSlider.value()*100/self.BatteryBrightnessSlider.maximum()
        else:
            value=self.PoweredBrightnessSlider.value()*100/self.PoweredBrightnessSlider.maximum()
        self.brightnessPopup = KPassivePopup.message('<b>Brightness:</b> '+str(value)+'%', self.systray)
        """pop.setTimeout(3000)"""
        self.brightnessPopup.show()

    def setBrightnessUp(self):
        """Increments slider value by 5%"""
        if self.powermanager.onBattery():
            self.BatteryBrightnessSlider.setValue(float(self.BatteryBrightnessSlider.value())+max(float(self.BatteryBrightnessSlider.maximum())/float(10),1))
        else:
            self.PoweredBrightnessSlider.setValue(float(self.PoweredBrightnessSlider.value())+max(float(self.PoweredBrightnessSlider.maximum())/float(10),1))
        self.showBrightnessPopup()

    def setBrightnessDown(self):
        """Decrements slider value by 5%"""
        if self.powermanager.onBattery():
            self.BatteryBrightnessSlider.setValue(float(self.BatteryBrightnessSlider.value())-max(float(self.BatteryBrightnessSlider.maximum())/float(10),1))
        else:
            self.PoweredBrightnessSlider.setValue(float(self.PoweredBrightnessSlider.value())-max(float(self.PoweredBrightnessSlider.maximum())/float(10),1))
        self.showBrightnessPopup()

    #def getBrightness(self):
    #  """Work with percentages - it's a bit nicer"""
    #  if self.powermanager.onBattery():
    #    value=self.BatteryBrightnessSlider.value()*100/self.BatteryBrightnessSlider.maxValue()
    #  else:
    #    value=self.PoweredBrightnessSlider.value()*100/self.PoweredBrightnessSlider.maxValue()
    #  return QString(str(value))

    def lockScreen(self):
        """ locks the screen using dbus """
        # init dbus session bus
        bus = dbus.SessionBus()
        # assign screensaver object
        dbus_screensaver = bus.get_object('org.freedesktop.ScreenSaver',
        '/ScreenSaver')
        # make screensaver methods available: Lock(), GetActive(), SetActive(bool),
        ScreenSaver = dbus.Interface(dbus_screensaver, 'org.freedesktop.ScreenSaver')
        # Lock the Screen or print a warning.
        # No return value when successful, not sure otherwise.
        try:
            ScreenSaver.Lock()
        except:
            print "Unable to lock the screen. There is a problem with the dbus connection to org.freedesktop.ScreenSaver.Lock()"

    def suspend(self):
        """ Lock the screen and initiate a suspend to RAM (S3). """
        if self.config.readEntry("lockOnResume", QVariant(True)).toBool():
            self.lockScreen()
        try:
            self.warningPopup.hide()
        except AttributeError:
            pass # No warningpopup, that's OK.
        self.powermanager.suspend()
        self.powermanager.resetIdleSeconds()

    def hibernate(self):
        """ Lock the screen and initiate a suspend to disk (S4). """
        if self.config.readEntry("lockOnResume", QVariant(True)).toBool():
            self.lockScreen()
        try:
            self.warningPopup.hide()
        except AttributeError:
            pass # No warningpopup, that's OK.
        self.powermanager.hibernate()
        self.powermanager.resetIdleSeconds()

    def shutdown(self):
        """ Perform system shutdown. """
        self.powermanager.shutdown()

    def _policyChangeMessage(self, policy):
        """ Properly localized text notification for policy change. """
        if policy == "dynamic":
            return i18n("CPU frequency policy changed to dynamic.")
        elif policy == "performance":
            return i18n("CPU frequency policy changed to performance.")
        elif policy == "powersave":
            return i18n("CPU frequency policy changed to powersave.")
        else:
            return i18n("CPU frequency policy changed to %1.", policy)

    def setCpuPolicyDynamic(self):
        """Change frequ for all cpu"""
        self.powermanager.setCpuPolicy('dynamic')
        self.notify(self._policyChangeMessage('dynamic'))

    def setCpuPolicyPerformance(self):
        """Change frequ for all cpu"""
        self.powermanager.setCpuPolicy('performance')
        self.notify(self._policyChangeMessage('performance'))

    def setCpuPolicyPowersave(self):
        """Change frequ for all cpu"""
        self.powermanager.setCpuPolicy('powersave')
        self.notify(self._policyChangeMessage('powersave'))
        self.blankScreen()

    #for if/when we add a DBus interface
    def trySuspend(self):
        """ If supported, lock the screen and initiate a suspend to RAM (S3). """
        if self.canSuspend:
           self.suspend()
        else:
           print "Warning: DBUS suspend() called, but not supported."

    def tryHibernate(self):
        """ If supported, lock the screen and initiate a suspend to disk (S4). """
        if self.canHibernate:
           self.hibernate()
        else:
           print "Warning: DBUS hibernate() called, but not supported."

    def blankScreen(self):
        """ Lock and blank screen. """
        if self.config.readEntry("lockOnResume", QVariant(True)).toBool():
            self.lockScreen()
        self.powermanager.blankScreen()

    def _getIcon(self):
        """ Set systray icon depending on battery status/level. """
        if self.powermanager.hasBattery:
            if self.batt_state == "not present":
                self.icon = "battery-missing"
            if self.batt_state == "charged":
                self.icon = "battery-charging"
            elif self.batt_state == "discharging":
                if self.batt_level >= 95:
                    self.icon = "battery-100"
                elif self.batt_level < 95 and self.batt_level >= 85:
                    self.icon = "battery-080"
                elif self.batt_level < 85 and self.batt_level >= 75:
                    self.icon = "battery-080"
                elif self.batt_level < 75 and self.batt_level >= 60:
                    self.icon = "battery-060"
                elif self.batt_level < 65 and self.batt_level >= 45:
                    self.icon = "battery-060"
                elif self.batt_level < 45 and self.batt_level >= 30:
                    self.icon = "battery-040"
                elif self.batt_level < 30 and self.batt_level >= 20:
                    self.icon = "battery-040"
                elif self.batt_level < 20 and self.batt_level >= 10:
                    self.icon = "battery-caution"
                elif self.batt_level < 10 and self.batt_level >= 5:
                    self.icon = "battery-low"
                else:
                    self.icon = "battery-low"
            elif self.batt_state == "charging":
                if self.batt_level >= 95:
                    self.icon = "battery-charging"
                elif self.batt_level < 95 and self.batt_level >= 85:
                    self.icon = "battery-charging-080"
                elif self.batt_level < 85 and self.batt_level >= 75:
                    self.icon = "battery-charging-080"
                elif self.batt_level < 75 and self.batt_level >= 60:
                    self.icon = "battery-charging-060"
                elif self.batt_level < 65 and self.batt_level >= 45:
                    self.icon = "battery-charging-060"
                elif self.batt_level < 45 and self.batt_level >= 30:
                    self.icon = "battery-charging-040"
                elif self.batt_level < 30 and self.batt_level >= 20:
                    self.icon = "battery-charging-040"
                elif self.batt_level < 20 and self.batt_level >= 10:
                    self.icon = "battery-charging-caution"
                elif self.batt_level < 10 and self.batt_level >= 5:
                    self.icon = "battery-charging-low"
                else:
                    self.icon = "battery-charging-low"
        else:
            self.icon = "battery-missing"
        return self.icon

    def getIcon(self):
        """ Return current icon."""
        return BarIcon(self.icon)

    def setIcon(self):
        """ Change the systray/tooltip icon."""
        oldIcon = self.icon
        self.icon = self._getIcon()
        if self.icon != oldIcon:
            icon = BarIcon(self.icon)
            self.systray.setIcon(QIcon(icon))
            self.BattPixmap.setPixmap(icon)
            self.parent().setWindowIcon(QIcon(icon))
            menu = self.systray.contextMenu() #hmm, doesn't work?
            menu.setIcon(QIcon(icon))

    def notify(self, msg, icon=None):
        """ Send a notification popup. """
        if icon:
            icon = QPixmap(icon)
        else:
            icon = QPixmap(SmallIcon("dialog-information"))
        try:
            del self.warningPopup
        except:
            pass
        KPassivePopup.message("Power Manager", msg, icon, self.systray)

    def poll(self,notify=True):
        """ Check for changes in plugged in status, battery status and laptop lid closed status. """
        debug( "------------ POLL ---------------")

        try:
            self.powermanager.checkHAL()
            # Battery stuff:
            # check for last state, and run plugged / unplugged message if the state changed.
            if self.powermanager.hasBattery:
                plugged_num = 0
                self.batt_state = "not present" # unknown yet
                self.batt_level = self.batt_remain = 0
                self.batt_rate = self.batt_charge = self.batt_full = 0
                for batt in self.powermanager.batteries:
                    state, level, remain, rate, current, full = self.powermanager.getBatteryState(batt)
                    self._updateBatteryWidget(batt, state, level, remain, rate)

                    # notify plugged/unplugged batteries
                    if state == "not present":
                        if self.powermanager.batteryIsPresent[batt]:
                            print "been removed"
                            self.notify(i18n("The battery has been removed."))
                            self.powermanager.batteryIsPresent[batt] = False
                    else: # battery present
                        if not self.powermanager.batteryIsPresent[batt]:
                            print "inserted"
                            self.notify(i18n("The battery has been inserted."))
                            self.powermanager.batteryIsPresent[batt] = True

                        # get cumulative charge levels/rate
                        self.batt_rate += rate
                        self.batt_charge += current
                        self.batt_full += full

                        # calculate overall level (average of present batteries)
                        self.batt_remain += remain
                        self.batt_level += level
                        plugged_num += 1

                        # calculate overall state (charging/discharging/charged)
                        if state in ("charging","discharging"):
                            self.batt_state = state
                        elif not self.batt_state in ("charging, discharging"):
                            self.batt_state = state

                # if we know charge and full -> recalculate overall level
                if self.batt_full > 0 and self.batt_charge > 0:
                    self.batt_level = 100 * self.batt_charge / self.batt_full
                else:
                    # if more than one battery present, we need to calculate average level
                    if plugged_num > 1:
                        self.batt_level /= plugged_num

                # if rate is reported, calculate remaining time on our own
                if self.batt_rate > 0:
                    if self.batt_state == "charging":
                        self.batt_remain = 3600 * (float(self.batt_full - self.batt_charge) / self.batt_rate)
                    if self.batt_state == "discharging":
                        self.batt_remain = 3600 * (float(self.batt_charge) / self.batt_rate)

                remain_h = self.batt_remain/3600
                remain_m = (self.batt_remain/60)%60

                blabel = i18n("<b>Battery:</b>")
                if self.batt_state == "charged":
                    blabel += i18n(" fully charged")
                elif self.batt_state == "charging":
                    blabel += ki18nc("hours:minutes", " %1:%2h to charge").subs(remain_h).subs(remain_m, 2).toString()
                elif self.batt_state == "discharging":
                    blabel += ki18nc("hours:minutes", " %1:%2h remaining").subs(remain_h).subs(remain_m, 2).toString()
                self.BattMainLabel.setText(blabel)

                # update tray icon if needed
                self.setIcon()

                # check battery state
                self.checkBatteryCritical()

                # check Idletime
                self.checkIdletime()

            # CPU stuff
            self._updateCpuWidgets()

            if self.powermanager.hasBattery:
                on_battery = self.powermanager.onBattery()
                if self.powermanager.wasOnBattery != on_battery:
                    self.powermanager.wasOnBattery = on_battery
                    debug("poll: states differ")
                    if not on_battery:
                        debug("poll: Now on AC")
                        if notify:
                            self.powerHasBeenPlugged()
                    else:
                        debug("poll: Now on battery")
                        if notify:
                            self.powerHasBeenUnplugged()
                else:
                    debug("poll: state is the same")

            # Lid stuff
            if self.powermanager.hasLid:
                if self.powermanager.getLidClosedState():
                    if not self.powermanager.lidClosedState:
                        self.powermanager.lidClosedState = True

                        action = self._getRB(self.LaptopLidRadios, self.lid_act)
                        if not self.act_name.has_key(action):
                            action = self.act_name[self.lid_act_def]

                        if self.act_call[action] != None:
                            if action == "nothing":
                                note = i18n("Laptop lid is closed, hibernating now.")
                            elif action == "blank":
                                note = i18n("Laptop lid is closed, blanking screen now.")
                            elif action == "suspend":
                                note = i18n("Laptop lid is closed, suspending now.")
                            elif action == "hibernate":
                                note = i18n("Laptop lid is closed, hibernating now.")
                            elif action == "shutdown":
                                note = i18n("Laptop lid is closed, shutting down now.")
                            self.notify(note, self.act_icon[action])
                            QTimer.singleShot(2000, self.act_call[action])
                else:
                    self.powermanager.lidClosedState = False
        except Exception,e:
                print "Is Hal running? Failed with error: ", e
                print "Will try again on the next polling attempt."

    def _addBatteryWidgets(self):
        """ Adds progressbars to show battery status to the tooltip."""
        BattLayout = QHBoxLayout(None)

        self.BattPixmap = QLabel(self.tooltip)
        self.BattPixmap.setSizePolicy(QSizePolicy(QSizePolicy.Fixed,QSizePolicy.Fixed))
        self.BattPixmap.setPixmap(BarIcon(self.icon))
        self.BattPixmap.setScaledContents(1)
        BattLayout.addWidget(self.BattPixmap)
        self.BattMainLabel = QLabel(self.tooltip)
        self.BattMainLabel.setText(i18n("<b>Battery:</b>"))
        BattLayout.addWidget(self.BattMainLabel)

        # Add to tooltip
        self.tooltip.layout().addLayout(BattLayout)

        # Create a progressbar and a label for every battery found, and add it to tooltip
        self.BattLabel = {}
        self.BattLayout = {}
        self.BattProgress = {}
        i = 1
        for batt in self.powermanager.batteries:
            self.BattLayout[batt] = QHBoxLayout(None)
            self.BattLabel[batt] = QLabel(self.tooltip)
            if len(self.powermanager.batteries) > 1:
                self.BattLabel[batt].setText(i18n("Battery %i" % i))
            self.BattLayout[batt].addWidget(self.BattLabel[batt])
            self.BattProgress[batt] = QProgressBar(self.tooltip)
            self.BattProgress[batt].setMinimumSize(QSize(200,0))
            self.BattLayout[batt].addWidget(self.BattProgress[batt])
            self.tooltip.layout().addLayout(self.BattLayout[batt])
            i += 1

    def _updateBatteryWidget(self, batt, state, level, remain, rate):
        """ Retrieve battery information and update the related widgets accordingly. """
        self.BattProgress[batt].setEnabled(True)
        self.BattProgress[batt].setMaximum(100)
        self.BattProgress[batt].setValue(level)
        if state == "not present":
            self.BattProgress[batt].setFormat(i18n("not present"))
        elif state == "charging":
            self.BattProgress[batt].setFormat(i18n("Charging (%p%)"))
        elif state == "discharging":
            if rate > 0:
                showrate = rate/1000
                self.BattProgress[batt].setFormat(ki18nc("%1 is discharge rate in Watts", "Discharging (%p%) - %1 W").subs(showrate).toString())
            else:
                self.BattProgress[batt].setFormat(i18n("Discharging (%p%)"))
        else:
            self.BattProgress[batt].setFormat(i18n("%p%"))

    def _addCpuWidgets(self):
        """ Adds progressbars to show CPU frequencies to the tooltip."""
        if not SHOW_CPUFREQ:
            return
        if len(self.powermanager.cpus) == 0:
            return

        LabelLayout = QHBoxLayout(None)

        self.CpuPixmap = QLabel(self.tooltip)
        self.CpuPixmap.setSizePolicy(QSizePolicy(QSizePolicy.Fixed,QSizePolicy.Fixed))
        self.CpuPixmap.setPixmap(BarIcon("cpu"))
        self.CpuPixmap.setScaledContents(1)
        LabelLayout.addWidget(self.CpuPixmap)
        self.CpuMainLabel = QLabel(self.tooltip)
        self.CpuMainLabel.setText(i18n("<b>CPU Frequency:</b>"))
        LabelLayout.addWidget(self.CpuMainLabel)

        # Add to tooltip
        self.tooltip.layout().addLayout(LabelLayout)

        # Create a progressbar and a label for every CPU found, and add it to tooltip
        self.CpuLabel = {}
        self.CpuLayout = {}
        self.CpuProgress = {}
        i = 1
        for cpu in self.powermanager.cpus:
            self.CpuLayout[cpu] = QHBoxLayout(None)
            self.CpuLabel[cpu] = QLabel(self.tooltip)
            if len(self.powermanager.cpus) > 1:
                self.CpuLabel[cpu].setText(i18n("Processor %1", i))
            self.CpuLayout[cpu].addWidget(self.CpuLabel[cpu])
            self.CpuProgress[cpu] = QProgressBar(self.tooltip)
            self.CpuProgress[cpu].setFormat("%v MHz")
            self.CpuLayout[cpu].addWidget(self.CpuProgress[cpu])
            self.tooltip.layout().addLayout(self.CpuLayout[cpu])
            i += 1

    def slotPoweredIdleActivated(self, index=False):
        """ Signal slot for activated powered idle action. """
        if not index:
            index = self.PoweredIdleCombo.currentIndex()
        self.PoweredIdleTime.setEnabled(index != 0)

    def slotBatteryIdleActivated(self, index=False):
        """ Signal slot for activated battery idle action. """
        if not index:
            index = self.BatteryIdleCombo.currentIndex()
        self.BatteryIdleTime.setEnabled(index != 0)

    def slotBatteryCriticalActivated(self, index=False):
        """ Signal slot for activated battery critical action. """
        if not index:
            index = self.BatteryCriticalCombo.currentIndex()
        self.CriticalRemainTime.setEnabled(index != 0)

    def _updateCpuWidgets(self):
        """ Retrieve CPU freq information and update the related widgets accordingly. """
        if not SHOW_CPUFREQ:
            return
        if len(self.powermanager.cpus) == 0:
            return

        policy = self.powermanager.getCpuPolicy()
        text = ""
        if self.freq_name.has_key(policy):
            policyString = unicode(self.freq_name[policy])
            text = i18nc("%1 is one of the CPU policies", "<b>CPU Frequency:</b> %1", policyString)
        else:
            text = i18nc("%1 is one of the CPU policies", "<b>CPU Frequency:</b> %1", policy)
        self.CpuMainLabel.setText(text)

        for cpu in self.powermanager.cpus:
            cpustate = self.powermanager.getCpuState(cpu)
            if not cpustate['online']:
                self.CpuProgress[cpu].setEnabled(False)
            else:
                self.CpuProgress[cpu].setEnabled(True)
                self.CpuProgress[cpu].setMaximum(cpustate['max'])
                self.CpuProgress[cpu].setValue(cpustate['cur'])
        if policy != "" or policy and self.cb_freq:
            self.policyActions[policy].setChecked(True)

    def changePoweredBrightness(self, level=None):
        """ Mains-powered brigthness slider has been moved. """
        # Check if the state applies and adjust brightness immediately.
        if not self.powermanager.onBattery() and self.powermanager.hasBrightness:
            if not level:
                level = self.PoweredBrightnessSlider.value()
            self.powermanager.adjustBrightness(level)

    def changeBatteryBrightness(self, level=None):
        """ Battery-powered brigthness slider has been moved. """
        # Check if the state applies and adjust brightness immediately.
        if self.powermanager.onBattery() and self.powermanager.hasBrightness:
            if not level:
                level = self.BatteryBrightnessSlider.value()
            self.powermanager.adjustBrightness(level)

    def checkCpuFreq(self):
        """ Adjust CPU frequency policy according to current state """
        if not self.powermanager.hasCpuFreqGovernors:
            return ""

        if self.powermanager.onBattery():
            policy = str(self.config.readEntry("batteryFreqPolicy"))
        else:
            policy = str(self.config.readEntry("poweredFreqPolicy"))
        if policy == "":
           policy = 'dynamic'

        # check if specified policy is supported by HW
        if not policy in self.cb_freq:
            print "Warning: policy from config file not supported: ", policy
            return ""

        current_policy = self.powermanager.getCpuPolicy()
        if current_policy != policy:
            debug("Switching CPU policy from %s to %s." % (current_policy, policy))
            self.powermanager.setCpuPolicy(policy)
            return self._policyChangeMessage(policy)
        elif current_policy == 'dynamic':
            debug("Dynamic policy -> update policy (conservative/ondemand)")
            self.powermanager.setCpuPolicy(policy)

        debug("CPU policy will stay %s" % current_policy)
        return ""

    def powerHasBeenUnplugged(self):
        """ Actions to perform when the plug has been pulled."""
        if self.powermanager.hasBrightness:
            self.powermanager.adjustBrightness(self.BatteryBrightnessSlider.value())
        self.powermanager.setPowerSave(True)
        self.checkBatteryCritical()
        self.changeBatteryBrightness()
        self.powermanager.setScreensaverBlankOnly(True)
        self.powermanager.resetIdleSeconds()
        msg = self.checkCpuFreq()
        if self.powermanager.hasAC:
            self.notify(i18n("The AC adapter has been unplugged, switching to battery mode.")+"\n"+msg, self.getIcon())

    def powerHasBeenPlugged(self):
        """ Actions to perform when AC adapter has been plugged in. """
        if self.powermanager.hasBrightness:
            self.powermanager.adjustBrightness(self.PoweredBrightnessSlider.value())
        self.powermanager.setPowerSave(False)
        self.changePoweredBrightness()
        self.powermanager.setScreensaverBlankOnly(False)
        msg = self.checkCpuFreq()
        self.powermanager.resetIdleSeconds()
        self.notify(i18n("The AC adapter has been plugged in, switching to AC mode.")+"\n"+msg, self.getIcon())

    def checkBatteryCritical(self):
        """ Check for warning and critical battery label and notify-warn or
            initiate the configured action. """

        if not self.powermanager.hasBattery:
            return

        if self.batt_state == "discharging":
            currentLevel = int(self.batt_remain/60)

            warningLevel = self.criticalLevel + 5 # warn five minutes before critical
            criticalLevel = self.criticalLevel

            debug("CurrentBat: %i, WarningBat: %i, CriticalBat: %i" % (currentLevel, warningLevel, criticalLevel))
            # We only want to suspend if the chargelevel is above a certain threshold,
            # it sometimes takes some time for HAL to report remaining time correctly
            if currentLevel <= criticalLevel and self.batt_level < CHARGE_LEVEL_THRESHOLD:
                if not self.powermanager.criticalBatteryState and self.powermanager.onBattery():
                    self.powermanager.criticalBatteryState = True

                    action = str(self.config.readEntry("batteryCriticalAction"))
                    if not self.act_name.has_key(action):
                        action = self.cb_act[self.cb_act_def_critical]

                    if action == "nothing":
                        note = i18n("You are about to run out of battery power, doing nothing now.")
                    elif action == "blank":
                        note = i18n("You are about to run out of battery power, blanking screen now.")
                    elif action == "suspend":
                        note = i18n("You are about to run out of battery power, suspending now.")
                    elif action == "hibernate":
                        note = i18n("You are about to run out of battery power, hibernating now.")
                    elif action == "shutdown":
                        note = i18n("You are about to run out of battery power, shutting down now.")
                    self.notify(note, self.act_icon[action])
                    if self.act_call[action] != None:
                        QTimer.singleShot(2000, self.act_call[action])
            else:
                self.powermanager.criticalBatteryState = False
                if currentLevel <= warningLevel and self.batt_level < CHARGE_LEVEL_THRESHOLD:
                    if not self.powermanager.warningBatteryState:
                        self.powermanager.warningBatteryState = True
                        self.notify(i18n("You are low on battery power."), self.getIcon())
                else:
                    self.powermanager.warningBatteryState = False

    def checkIdletime(self):
        """ Reads the idle time and does some action. """
        idlesec = round(self.powermanager.getIdleSeconds()/60, 2)

        disableSuspend = self.config.readEntry("disableSuspend", QVariant(False)).toBool()
        disableHibernate = self.config.readEntry("disableHibernate", QVariant(False)).toBool()

        if self.powermanager.onBattery():
            idleTime = self.config.readEntry("batteryIdleTime", QVariant(10)).toInt()
            action = str(self.config.readEntry("batteryIdleAction", QString("")))
        else:
            idleTime = self.config.readEntry("poweredIdleTime", QVariant(60)).toInt()
            action = str(self.config.readEntry("poweredIdleAction", QString("")))
        if not self.act_name.has_key(action):
            action = 'nothing'

        if idlesec - self.lastidlesec > 100:
            debug("last: %u" % (idlesec - self.lastidlesec))
            return # probably bogus idleseconds right after suspend
        self.lastidlesec = idlesec
        if self.act_call[action] == None:
            return # doing nothing anyway
        if idlesec > idleTime:
            if action == "nothing":
                note = i18np("System idle for at least %1 minute, doing nothing now.", "System idle for at least %1 minutes, doing nothing now.", idleTime)
            elif action == "blank":
                note = i18np("System idle for at least %1 minute, blanking screen now.", "System idle for at least %1 minutes, blanking screen now.", idleTime)
            elif action == "suspend":
                note = i18np("System idle for at least %1 minute, suspending now.", "System idle for at least %1 minutes, suspending now.", idleTime)
            elif action == "hibernate":
                note = i18np("System idle for at least %1 minute, hibernating now.", "System idle for at least %1 minutes, hibernating now.", idleTime)
            elif action == "shutdown":
                note = i18np("System idle for at least %1 minute, shutting down now.", "System idle for at least %1 minutes, shutting down now.", idleTime)
            self.notify(note, self.act_icon[action])
            QTimer.singleShot(2000, self.act_call[action])

class PowermanagerApp(KDialog):
    """ The KDialog providing the OK, Apply and Cancel buttons."""

    def __init__(self,parent=None):
        """ Initialise dialog and set mainwidget. """
        KDialog.__init__(self, parent)
        self.setButtons(KDialog.ButtonCode(KDialog.Ok | KDialog.Cancel | KDialog.Apply | KDialog.User1))
        self.pmwidget = PowerManager(self)
        self.setButtonText(KDialog.User1, i18n("About"))

        if not self.pmwidget.powermanager.isLaptop():
            print "This is not a laptop, quitting ... "
            sys.exit(1)

        self.pmwidget.prepare()

        self.setMainWidget(self.pmwidget)
        self.resize(0, 0)

        self.connect(self, SIGNAL("okClicked()"), self.slotOk)
        self.connect(self, SIGNAL("applyClicked()"), self.slotApply)
        self.connect(self, SIGNAL("cancelClicked()"), self.slotCancel)
        self.connect(self, SIGNAL("user1Clicked()"), self.slotUser1)
        self.aboutus = KAboutApplicationDialog(aboutData, self)
        self.setWindowTitle(i18n("Guidance Power Manager")) #KDialog doesn't use app name for some reason

    def slotOk(self):
        """ The OK button has been pressed, save configuration and pass on do whatever
            needs to be done by KDialog. """
        self.pmwidget.uiToConfig()
        self.pmwidget.checkCpuFreq()

    def slotApply(self):
        """ The Apply button has been pressed, save configuration and pass on do whatever
            needs to be done by KDialog. """
        self.pmwidget.uiToConfig()
        self.pmwidget.checkCpuFreq()

    def slotCancel(self):
        """ The Cancel button has been pressed, reset some values and hide dialogue. """
        # In case brightness has changed, we reset it to the configured value.
        if self.pmwidget.powermanager.hasBrightness:
            brightness_high = self.pmwidget.powermanager.brightness_levels
            if not self.pmwidget.powermanager.onBattery():
                poweredBrightness = self.pmwidget.config.readEntry("poweredBrightness", QVariant(brightness_high))
                level = poweredBrightness.toInt()
                level = level[0]
            else:
                batteryBrightness = self.pmwidget.config.readEntry("batteryBrightness", QVariant(int(brightness_high/2)))
                level = batteryBrightness.toInt()
                level = level[0]
            self.pmwidget.powermanager.adjustBrightness(level)
        self.pmwidget.configToUi()

    def slotUser1(self):
        self.aboutus.show()

class SystemTrayIcon(KSystemTrayIcon):
    """This class needed because we can't use a widget for a tooltip in Qt 4 (only text)
       Also we can't use a KPassivePopup because KSystemTrayIcon is not a QWidget """

    def setToolTip(self, toolTip):
        """ set the toolTip widget """
        self.toolTip = toolTip
        self.toolTip.setWindowFlags(Qt.ToolTip)

    def event(self, event):
        """ overloaded to pick up tooltip events and show our widget
            would be nice to hide it when the mouse leaves but systemtrayicons
            don't get that event so use a timer """
        if event.type() == QEvent.ToolTip:
            self.toolTip.show()
            x = self.geometry().x() - self.toolTip.width()
            y = self.geometry().y() - self.toolTip.height()
            if x < 0:
                x += self.geometry().width() + self.toolTip.width()
            if y < 0:
                y += self.geometry().height() + self.toolTip.height()
            self.toolTip.move(x, y)
            QTimer.singleShot(3000, self.hideToolTip)
            return True
        else:
            return KSystemTrayIcon.event(self, event)

    def hideToolTip(self):
        self.toolTip.hide()

# the old "not destroying KApplication last"
# make a real main(), and make app global. app will then be the last thing deleted (C++)
def main():
    mainWindow = PowermanagerApp(None)
    #mainWindow.show()
    app.setQuitOnLastWindowClosed(False) #else Qt 4 likes to quit when we close or hide the dialogue
    app.exec_()

#--------------- main ------------------
if __name__ == '__main__':

    appName     = "guidance-power-manager"
    catalog     = ""
    programName = ki18n("Guidance Power Manager")
    version     = "4.1.3"
    description = ki18n("Applet for battery info and setting brightness")
    license     = KAboutData.License_GPL
    copyright   = ki18n("Copyright 2006-2008 Sebastian Kügler, Canonical Ltd, Luka Renko")
    text        = KLocalizedString()
    homePage    = "https://launchpad.net/guidance"
    bugEmail    = ""

    aboutData   = KAboutData(appName, catalog, programName, version, description,
                                license, copyright, text, homePage, bugEmail)

    KCmdLineArgs.init(sys.argv, aboutData)

    app = KUniqueApplication()
    main()
