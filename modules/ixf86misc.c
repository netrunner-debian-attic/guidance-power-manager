/*#########################################################################
# ixf86misc.c -                                                           #
# ------------------------------                                          #
# copyright : (C) 2004-2007 by Simon Edwards                              #
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
# A small binding for playing with the gamma and RandR settings under     #
# XFree86.                                                                #
#                                                                         #
# Simon Edwards <simon@simonzone.com>                                     #
#########################################################################*/

#include "Python.h"
#include <X11/Xlib.h>
#include <X11/extensions/xf86vmode.h>
#include <X11/extensions/Xrandr.h>
#include <X11/extensions/scrnsaver.h>

/***************************************************************************
 XOpenDisplay(displayname)
 
 Args:
   displayname - String
 
 Returns:
   opaque display reference.
*/
static void ixf86misc_destroydisplay(void *ptr) {
  if(ptr!=NULL) {
    XCloseDisplay((Display *)ptr);
  }
}

static PyObject *ixf86misc_xopendisplay(PyObject *self, PyObject *args) {
  Display *dpy;
  char *displayname = NULL;
  
  if(!PyArg_ParseTuple(args, "z", &displayname)) {
    return NULL;
  }
  
  dpy = XOpenDisplay(displayname);
  if(dpy==NULL) {
    return Py_BuildValue("");
  } else {
    return PyCObject_FromVoidPtr((void *)dpy,ixf86misc_destroydisplay);
  }
}

/***************************************************************************
  DefaultScreen(display)
  
  Args:
    display - display object.
  Returns:
  
    screen number - integer
*/
static PyObject *ixf86misc_defaultscreen(PyObject *self, PyObject *args) {
  PyObject *pydisplay = NULL;
  int screen;
  
  if(!PyArg_ParseTuple(args, "O", &pydisplay)) {
    return NULL;
  }
  screen = DefaultScreen((Display *)PyCObject_AsVoidPtr(pydisplay));
  return Py_BuildValue("i", screen);
}

/***************************************************************************
  ScreenCount(display)
  
  Args:
    display - display object.
  Returns:
  
    number of screens - integer
*/
static PyObject *ixf86misc_screencount(PyObject *self, PyObject *args) {
  PyObject *pydisplay = NULL;
  int count;
  
  if(!PyArg_ParseTuple(args, "O", &pydisplay)) {
    return NULL;
  }
  count = ScreenCount((Display *)PyCObject_AsVoidPtr(pydisplay));
  return Py_BuildValue("i", count);
}

/***************************************************************************
  RootWindow(display,screennumber)
  
*/
static PyObject *ixf86misc_rootwindow(PyObject *self, PyObject *args) {
  PyObject *pydisplay = NULL;
  int screen = 0;
  Drawable pydrawable;

  if(!PyArg_ParseTuple(args, "Oi", &pydisplay, &screen)) {
    return NULL;
  }

  pydrawable = RootWindow((Display *)PyCObject_AsVoidPtr(pydisplay),screen);
  return Py_BuildValue("l",pydrawable);
}

/***************************************************************************

*/
static PyObject *ixf86misc_getgamma(PyObject *self, PyObject *args) {
  PyObject *pydisplay = NULL;
  int screen = 0;
  XF86VidModeGamma gamma;
  
  if(!PyArg_ParseTuple(args, "Oi", &pydisplay, &screen)) {
    return NULL;
  }

  if(!XF86VidModeGetGamma((Display *)PyCObject_AsVoidPtr(pydisplay), screen, &gamma)) {
    /* FIXME set an exception? */
    return NULL;
  }

  return Py_BuildValue("(fff)", gamma.red, gamma.green, gamma.blue);
}

/***************************************************************************

*/
static PyObject *ixf86misc_setgamma(PyObject *self, PyObject *args) {
  PyObject *pydisplay = NULL;
  Display *display;
  int screen = 0;
  XF86VidModeGamma gamma;
  float red,green,blue;
  
  if(!PyArg_ParseTuple(args, "Oifff", &pydisplay, &screen, &red, &green, &blue)) {
    return NULL;
  }
  
  display = (Display *)PyCObject_AsVoidPtr(pydisplay);
  
  if(!XF86VidModeGetGamma(display, screen, &gamma)) {
    return NULL;
  }
  
  gamma.red = red;
  gamma.green = green;
  gamma.blue = blue;
  if(!XF86VidModeSetGamma(display, screen, &gamma)) {
    /* FIXME set an exception? */
    return NULL;
  }
  XFlush(display);
  return Py_BuildValue("");
}

/***************************************************************************
  
XRRQueryExtension (Display *dpy,
            int *event_basep, int *error_basep);
*/
static PyObject *ixf86misc_xrrqueryextension(PyObject *self, PyObject *args) {
  PyObject *pydisplay = NULL;
  Display *display;
  int event_basep, error_basep;
  
  if(!PyArg_ParseTuple(args, "O", &pydisplay)) {
    return NULL;
  }
  display = (Display *)PyCObject_AsVoidPtr(pydisplay);

  Bool rc = XRRQueryExtension(display, &event_basep, &error_basep);
  return Py_BuildValue("(iii)",(int)rc, event_basep, error_basep);
}

/***************************************************************************
  XRRScreenConfiguration *XRRGetScreenInfo(Display *dpy,Drawable d)
*/
static void ixf86misc_destroyxrrscreenconfig(void *ptr) {
  if(ptr!=NULL) {
    XRRFreeScreenConfigInfo((XRRScreenConfiguration *)ptr);
  }
}
static PyObject *ixf86misc_xrrgetscreeninfo(PyObject *self, PyObject *args) {
  PyObject *pydisplay = NULL;
  Drawable pydrawable;
  XRRScreenConfiguration *xrrconfig;

  if(!PyArg_ParseTuple(args, "Ol", &pydisplay, &pydrawable)) {
    return NULL;
  }

  xrrconfig = XRRGetScreenInfo((Display *)PyCObject_AsVoidPtr(pydisplay), pydrawable);

  if(xrrconfig==NULL) {
    return Py_BuildValue("");
  } else {
    return PyCObject_FromVoidPtr((void *)xrrconfig,ixf86misc_destroyxrrscreenconfig);
  }
}

/***************************************************************************
  SizeID XRRConfigCurrentConfiguration(XRRScreenConfiguration *config)
*/
static PyObject *ixf86misc_xrrconfigcurrentconfiguration(PyObject *self, PyObject *args) {
  PyObject *pyconfig = NULL;
  Rotation currentrotation;
  SizeID currentsize;

  if(!PyArg_ParseTuple(args, "O", &pyconfig)) {
    return NULL;
  }
  currentsize = XRRConfigCurrentConfiguration((XRRScreenConfiguration *)PyCObject_AsVoidPtr(pyconfig), &currentrotation);
  return Py_BuildValue("(ll)", (long)currentsize, (long)currentrotation);
}

/***************************************************************************
  XRRRotations(display,screen)
*/
static PyObject *ixf86misc_xrrrotations(PyObject *self, PyObject *args) {
  PyObject *pydisplay = NULL;
  Display *display;
  int screen = 0;
  Rotation currentrotation,availablerotations;
  
  if(!PyArg_ParseTuple(args, "Oi", &pydisplay, &screen)) {
    return NULL;
  }
  display = (Display *)PyCObject_AsVoidPtr(pydisplay);
  availablerotations = XRRRotations(display, screen, &currentrotation);
  return Py_BuildValue("l", (long)availablerotations);
}

/***************************************************************************
  XRRSizes(display,screen)
*/
static PyObject *ixf86misc_xrrsizes(PyObject *self, PyObject *args) {
  PyObject *pydisplay = NULL;
  PyObject *sizelist,*item;
  Display *display;
  XRRScreenSize *sizes;
  int screen = 0;
  int numSizes;
  int i;
  
  if(!PyArg_ParseTuple(args, "Oi", &pydisplay, &screen)) {
    return NULL;
  }
  display = (Display *)PyCObject_AsVoidPtr(pydisplay);
  
  sizelist = PyList_New(0);
  sizes = XRRSizes(display, screen, &numSizes);
  for(i = 0; i < numSizes; i++) {
    item = Py_BuildValue("(iiii)",sizes[i].width, sizes[i].height,sizes[i].mwidth, sizes[i].mheight);
    PyList_Append(sizelist, item);
  }

  return sizelist;
}

/***************************************************************************
  short XRRConfigCurrentRate(config)
*/
static PyObject *ixf86misc_xrrconfigcurrentrate(PyObject *self, PyObject *args) {
  PyObject *pyconfig = NULL;
  int rate;

  if(!PyArg_ParseTuple(args, "O", &pyconfig)) {
    return NULL;
  }
  rate = XRRConfigCurrentRate((XRRScreenConfiguration *)PyCObject_AsVoidPtr(pyconfig));
  return Py_BuildValue("i", (int)rate);
}

/***************************************************************************

*/
static PyObject *ixf86misc_xrrrates(PyObject *self, PyObject *args) {
  PyObject *pydisplay = NULL;
  PyObject *ratelist,*item;
  Display *display;
  int numrates;  
  int size;
  int screen = 0;
  int i;
  short *rates;
  
  if(!PyArg_ParseTuple(args, "Oii", &pydisplay, &screen,&size)) {
    return NULL;
  }
  display = (Display *)PyCObject_AsVoidPtr(pydisplay);
  rates = XRRRates(display, screen, (SizeID)size, &numrates);

  ratelist = PyList_New(0);
  for(i = 0; i < numrates; i++) {
    item = Py_BuildValue("i",(int)rates[i]);
    PyList_Append(ratelist, item);
  }
  return ratelist;  
}

/***************************************************************************
Time XRRConfigTimes( XRRScreenConfiguration *config, Time *config_timestamp )
*/

static PyObject *ixf86misc_xrrconfigtimes(PyObject *self, PyObject *args) {
  PyObject *pyconfig = NULL;
  int rate;
  Time ts,ts2;
  
  if(!PyArg_ParseTuple(args, "O", &pyconfig)) {
    return NULL;
  }
  ts2 = XRRConfigTimes((XRRScreenConfiguration *)PyCObject_AsVoidPtr(pyconfig),&ts);
  return Py_BuildValue("l", (long)ts);
}

/***************************************************************************
status = XRRSetScreenConfigAndRate(display, config, window, newsize, newrotation, newrefresh, currenttime)
*/
static PyObject *ixf86misc_xrrsetscreenconfigandrate(PyObject *self, PyObject *args) {
  PyObject *pydisplay = NULL;
  Display *display = NULL;
  PyObject *pyconfig = NULL;
  Drawable pydrawable;
  Rotation newrotation;
  long newrefresh;
  /*  Time currenttime;*/
  Status status;
  long newsize;
  
  if(!PyArg_ParseTuple(args, "OOllll", &pydisplay, &pyconfig, &pydrawable, &newsize, &newrotation, &newrefresh /*, &currenttime*/ )) {
    return NULL;
  }
  display = (Display *)PyCObject_AsVoidPtr(pydisplay);

  status = XRRSetScreenConfigAndRate(display, (XRRScreenConfiguration *)PyCObject_AsVoidPtr(pyconfig), pydrawable,
      (SizeID)newsize, newrotation, newrefresh, CurrentTime);

  return Py_BuildValue("i", (int)status);
}

/***************************************************************************
  (dotclock,hdisplay,hsyncstart,hsyncend,htotal,vdisplay,vsyncstart,vsyncend,vtotal,flags) = \
        ixf86misc_vidmodegetmodeline(display,screen)

*/

static PyObject *ixf86misc_vidmodegetmodeline(PyObject *self, PyObject *args) {
  PyObject *pydisplay = NULL;
  Display *display = NULL;
  long screen;
  int dotclock_return;
  XF86VidModeModeLine modeline;
  PyObject *returnvalue;
    
  if(!PyArg_ParseTuple(args, "Ol", &pydisplay, &screen)) {
    return NULL;
  }
  display = (Display *)PyCObject_AsVoidPtr(pydisplay);

  if(XF86VidModeGetModeLine(display,screen,&dotclock_return,&modeline)) {
    returnvalue = Py_BuildValue("(iiiiiiiiii)",
                    dotclock_return,
                    modeline.hdisplay,   /* Number of display pixels horizontally */
                    modeline.hsyncstart, /* Horizontal sync start */
                    modeline.hsyncend,   /* Horizontal sync end */
                    modeline.htotal,     /* Total horizontal pixels */
                    modeline.vdisplay,   /* Number of display pixels vertically */
                    modeline.vsyncstart, /* Vertical sync start */
                    modeline.vsyncend,   /* Vertical sync start */
                    modeline.vtotal,     /* Total vertical pixels */
                    modeline.flags      /* Mode flags */);
    if(modeline.private!=NULL) {
        XFree(modeline.private);
    }
    return returnvalue;
  } else {
    return Py_BuildValue("");
  }

}

/***************************************************************************
   
  DisplaySize(display,screen_num)
  
  Args:
    display - display object.
    screen_num - screen number
  Returns:
  
    dimensions - a tuple consisting of 4 integers (width_pixels, height_pixels,
        width_mm, height_mm)
*/
static PyObject *ixf86misc_displaysize(PyObject *self, PyObject *args) {
  PyObject *pydisplay = NULL;
  Display *display = NULL;
  int screennum = 0;
    
  if(!PyArg_ParseTuple(args, "Oi", &pydisplay,&screennum)) {
    return NULL;
  }
  display = (Display *)PyCObject_AsVoidPtr(pydisplay);
  
  return Py_BuildValue("(iiii)",
    DisplayWidth(display,screennum),
    DisplayHeight(display,screennum),
    DisplayWidthMM(display,screennum),
    DisplayHeightMM(display,screennum));
}

/***************************************************************************

*/
static PyObject *ixf86misc_xscreensaverqueryextension(PyObject *self, PyObject *args) {
  PyObject *pydisplay = NULL;
  Display *display;
  
  if(!PyArg_ParseTuple(args, "O", &pydisplay)) {
    return NULL;
  }
  display = (Display *)PyCObject_AsVoidPtr(pydisplay);
  int event_base, error_base;
  
  int rc = XScreenSaverQueryExtension(display, &event_base, &error_base);
  return Py_BuildValue("i", rc);
}

/***************************************************************************

*/
static void ixf86misc_destroyscreensaver(void *ptr) {
  if(ptr!=NULL) {
    XFree(ptr);
  }
}

static PyObject *ixf86misc_xscreensaverallocinfo(PyObject *self, PyObject *args) {
  XScreenSaverInfo *ss_info;
  ss_info = XScreenSaverAllocInfo();
  return PyCObject_FromVoidPtr((void *)ss_info,ixf86misc_destroyscreensaver);
}

/***************************************************************************

*/

static PyObject *ixf86misc_xscreensaverqueryinfo(PyObject *self, PyObject *args) {
  PyObject *pydisplay;
  Display *display;
  Drawable window;  
  PyObject *pyscreensaverinfo;
  XScreenSaverInfo *screensaverinfo;
    
if(!PyArg_ParseTuple(args, "OlO", &pydisplay, &window, &pyscreensaverinfo)) {
    return NULL;
  }
  display = (Display *)PyCObject_AsVoidPtr(pydisplay);
  screensaverinfo = (XScreenSaverInfo *)PyCObject_AsVoidPtr(pyscreensaverinfo);
  
  int state = 0;
  int kind = 0;
  unsigned long idle = 0;
  unsigned long til_or_since = 0;
  if(XScreenSaverQueryInfo(display, window, screensaverinfo)) {
    state = screensaverinfo->state;
    kind = screensaverinfo->kind;
    til_or_since = screensaverinfo->til_or_since;
    idle = screensaverinfo->idle;
  }
 
  return Py_BuildValue("(iikk)", state, kind ,til_or_since, idle);
}

/***************************************************************************

*/

static struct PyMethodDef ixf86misc_methods[] = {
  { "XOpenDisplay", ixf86misc_xopendisplay, METH_VARARGS },
  { "DefaultScreen", ixf86misc_defaultscreen, METH_VARARGS },
  { "ScreenCount", ixf86misc_screencount, METH_VARARGS },
  { "GetGamma", ixf86misc_getgamma, METH_VARARGS },
  { "SetGamma", ixf86misc_setgamma, METH_VARARGS },
  { "RootWindow", ixf86misc_rootwindow, METH_VARARGS },
  { "XRRGetScreenInfo", ixf86misc_xrrgetscreeninfo, METH_VARARGS },
  { "XRRConfigCurrentConfiguration", ixf86misc_xrrconfigcurrentconfiguration, METH_VARARGS },
  { "XRRRotations", ixf86misc_xrrrotations, METH_VARARGS },
  { "XRRSizes", ixf86misc_xrrsizes, METH_VARARGS },
  { "XRRConfigCurrentRate", ixf86misc_xrrconfigcurrentrate, METH_VARARGS },
  { "XRRRates", ixf86misc_xrrrates, METH_VARARGS },
  { "XRRConfigTimes", ixf86misc_xrrconfigtimes, METH_VARARGS },
  { "XRRSetScreenConfigAndRate", ixf86misc_xrrsetscreenconfigandrate, METH_VARARGS },
  { "XF86VidModeGetModeLine", ixf86misc_vidmodegetmodeline, METH_VARARGS },
  { "DisplaySize", ixf86misc_displaysize, METH_VARARGS },
  { "XScreenSaverQueryExtension", ixf86misc_xscreensaverqueryextension, METH_VARARGS },
  { "XScreenSaverAllocInfo", ixf86misc_xscreensaverallocinfo, METH_VARARGS },
  { "XScreenSaverQueryInfo", ixf86misc_xscreensaverqueryinfo, METH_VARARGS },
  { "XRRQueryExtension", ixf86misc_xrrqueryextension, METH_VARARGS },
  { NULL, NULL }
};

void initixf86misc(void) {
  PyObject *ixf86misc = Py_InitModule3("ixf86misc",ixf86misc_methods,"Bindings for some XFree86 config functions.");

}
