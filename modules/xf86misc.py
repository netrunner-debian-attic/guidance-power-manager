#!/usr/bin/env python
###########################################################################
# xf86misc.py -                                                           #
# ------------------------------                                          #
# copyright : (C) 2004 by Simon Edwards                                   #
# email     : simon@simonzone.com                                         #
#                                                                         #
###########################################################################
#                                                                         #
#   This program is free software; you can redistribute it and/or modify  #
#   it under the terms of the GNU General Public License as published by  #
#   the Free Software Foundation; either version 2 of the License, or     #
#   (at your option) any later version.                                   #
#                                                                         #
###########################################################################
"""A simple interface for changing the current gamma setting under XFree86.
"""
import ixf86misc
import os, time

class XF86Screen(object):
    
    RR_Rotate_0 = 1
    RR_Rotate_90 = 2
    RR_Rotate_180 = 4
    RR_Rotate_270 = 8
    RR_Reflect_X = 16
    RR_Reflect_Y = 32
    
    def __init__(self,display,screenid):
        self.screenid = screenid
        self.display = display
        self.ssinfo = None
        self.starttime = time.time()
        self.resettime = 0
        self.lastidle = 0
        
        self.screenconfig = None
        self._load()

    def _load(self):
        # Check for the presence of the xrandr extension.
        try:
            (rc,x,y) = ixf86misc.XRRQueryExtension(self.display)
            if rc==0:
                return
        except AttributeError, errmsg:
            print "Trapped AttributeError:", errmsg, " - attempting to continue."
            return

        self.screenconfig = ixf86misc.XRRGetScreenInfo(self.display, ixf86misc.RootWindow(self.display, self.screenid))
        if self.screenconfig is not None:
            (self.currentsizeid,self.currentrotation) = ixf86misc.XRRConfigCurrentConfiguration(self.screenconfig)
            self.availablerotations = ixf86misc.XRRRotations(self.display, self.screenid)
            self.sizes = ixf86misc.XRRSizes(self.display, self.screenid)
            self.currentrefreshrate = ixf86misc.XRRConfigCurrentRate(self.screenconfig)

    def resolutionSupportAvailable(self):
        return self.screenconfig is not None
    
    def getScreenId(self):
        return self.screenid
    
    def getGamma(self):
        return ixf86misc.GetGamma(self.display,self.screenid)
        
    def setGamma(self,gammatuple):
        ixf86misc.SetGamma(self.display,self.screenid,gammatuple[0],gammatuple[1],gammatuple[2])
    
    def getRotation(self):
        return self.currentrotation

    def getAvailableRotations(self):
        return self.availablerotations
        
    def getSize(self):
        return self.sizes[self.currentsizeid]
        
    def getSizeID(self):
        return self.currentsizeid

    def getAvailableSizes(self):
        return self.sizes[:]

    def getRefreshRate(self):
        return self.currentrefreshrate

    def getAvailableRefreshRates(self,sizeid):
        return ixf86misc.XRRRates(self.display,self.screenid,sizeid)

    def setScreenConfigAndRate(self, sizeid, rotation, refresh):
        rc = ixf86misc.XRRSetScreenConfigAndRate(self.display, self.screenconfig, \
            ixf86misc.RootWindow(self.display, self.screenid), sizeid, rotation, refresh) 
            #ixf86misc.XRRConfigTimes(self.screenconfig) \
            
        self._load()
        return rc # FIXME handle failures due to the timestamp.

    def getDimensions(self):
        return ixf86misc.DisplaySize(self.display,self.screenid)
        
    def getIdleSeconds(self):
        data = self.__getScreenSaverInfo()
        if data is None:
            return 0
            
        (state, kind, til_or_since, idle) = data
        idletime = idle/1000.0
        
        if (self.lastidle > idletime) or (self.resettime > idletime): # Something has moved in the meantime
            self.starttime = 0
            self.resettime = 0
        else:
            idletime = idletime - self.resettime
        self.lastidle = idletime
        return idletime
        
    def resetIdleSeconds(self):
        self.resettime = time.time() - self.starttime
    
    # See man XScreenSaver(3)
    def __getScreenSaverInfo(self):
        if self.ssinfo is None:
            if ixf86misc.XScreenSaverQueryExtension(self.display):
                self.ssinfo = ixf86misc.XScreenSaverAllocInfo()
            else:
                return 0    # Error actually.
                
        return ixf86misc.XScreenSaverQueryInfo(self.display,
                    ixf86misc.RootWindow(self.display, self.screenid), self.ssinfo)
    
        
class XF86Server(object):
    def __init__(self,displayname=None):
        if displayname==None:
            if 'DISPLAY' in os.environ:
                displayname = os.environ['DISPLAY']
            else:
                displayname = ":0.0"
        self.displayname = displayname
        self.display = ixf86misc.XOpenDisplay(displayname)
        if self.display is None:
            raise XF86Error, "Couldn't connect to X server."
            
        self._defaultscreen = ixf86misc.DefaultScreen(self.display)
        
        self.screens = []
        for i in range(ixf86misc.ScreenCount(self.display)):
             self.screens.append(XF86Screen(self.display,i))
        
    def getDefaultScreen(self):
        return self.screens[self._defaultscreen]

    def getDisplay(self):
        return self.display
        
    def getDisplayName(self):
        return self.displayname
        
    def getScreens(self):
        return self.screens[:]
    
    def resolutionSupportAvailable(self):
        return self.screens[0].resolutionSupportAvailable()
    
class XF86Error(Exception):
    """Just an exception when some goes wrong with X."""
        
if __name__=='__main__':
    xg = XF86Server()
    xs = xg.getDefaultScreen()
    print "Number of screens:",str(len(xg.screens))
    print "Idle seconds:",xs.getIdleSeconds()
    print
    print "Gamma:"+str(xs.getGamma())
    print
    if xg.resolutionSupportAvailable():
        print "SizeID:"+str(xs.getSizeID())
        print "Size:"+str(xs.getSize())
        sizes = xs.getAvailableSizes()
        print "Available Sizes:" + str(sizes)
        print
        print "Rotation:" + str(xs.getRotation())
        print "Available Rotations:" + str(xs.getAvailableRotations())
        print
        print "Refresh rate:" + str(xs.getRefreshRate())
        print "Refresh rates for the current screen:"+str(xs.getAvailableRefreshRates(xs.getSizeID()))
        
        for i in range(len(sizes)):
            print "All Refresh Rates:"+str(xs.getAvailableRefreshRates(i))
        xs.setScreenConfigAndRate(0,1,75)
        print "SizeID:"+str(xs.getSizeID())
        print "Size:"+str(xs.getSize())
        sizes = xs.getAvailableSizes()
        print "Available Sizes:" + str(sizes)
    else:
        print "(no resolution / randr support available)"
