# Find PyDBus
# ~~~~~~~~~~
# Copyright (c) 2008, Jonathan Riddell <jriddell@ubuntu.com>
# Redistribution and use is allowed according to the terms of the BSD license.
# For details see the accompanying COPYING-CMAKE-SCRIPTS file.
#
# Python DBus website: http://dbus.freedesktop.org/releases/dbus-python/
#
# Find the installed version of Python DBus

IF(PYDBUS_FOUND)
  # Already in cache, be silent
  SET(PYDBUS_FOUND TRUE)
ELSE(PYDBUS_FOUND)

  GET_FILENAME_COMPONENT(_cmake_module_path ${CMAKE_CURRENT_LIST_FILE}  PATH)

  EXECUTE_PROCESS(COMMAND ${PYTHON_EXECUTABLE} ${_cmake_module_path}/FindPyDBus.py OUTPUT_VARIABLE pydbus)
  IF(pydbus)
    SET(PYDBUS_FOUND TRUE)
  ENDIF(pydbus)

  IF(PYDBUS_FOUND)
    IF(NOT PYDBUS_FIND_QUIETLY)
      MESSAGE(STATUS "Found PyDBus")
    ENDIF(NOT PYDBUS_FIND_QUIETLY)
  ELSE(PYDBUS_FOUND)
    IF(PYDBUS_FIND_REQUIRED)
      MESSAGE(FATAL_ERROR "Could not find PyDBus")
    ENDIF(PYDBUS_FIND_REQUIRED)
  ENDIF(PYDBUS_FOUND)

ENDIF(PYDBUS_FOUND)
