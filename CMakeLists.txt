# search packages used by KDE
find_package(KDE4 REQUIRED)
include(KDE4Defaults)
include(MacroLibrary)

set(CMAKE_MODULE_PATH ${CMAKE_MODULE_PATH}  ${CMAKE_CURRENT_SOURCE_DIR}/cmake-modules )

MACRO(PYKDE4_ADD_EXECUTABLE _pyname _exename)
    INSTALL(CODE "EXECUTE_PROCESS(COMMAND ${CMAKE_COMMAND} -DTARGET=${DATA_INSTALL_DIR}/guidance-power-manager/${_pyname} -DLINK_NAME=${BIN_INSTALL_DIR}/${_exename} -P ${CMAKE_CURRENT_SOURCE_DIR}/cmake-modules/create_exe_symlink.cmake)" )
ENDMACRO(PYKDE4_ADD_EXECUTABLE)

macro_optional_find_package(PythonLibrary)
macro_optional_find_package(SIP)

find_package(PyQt4)
IF(NOT PYQT4_FOUND)
    macro_log_feature(PYQT4_FOUND "PyQt4" "PyQt4 was not found.  It is needed by guidance-power-manager to run. (Use -DINSTALL_POWER_MANAGER=TRUE to install anyway)" "http://www.riverbankcomputing.co.uk/pyqt/" FALSE)
ENDIF(NOT PYQT4_FOUND)

find_package(PyKDE)
IF(NOT PYKDE_FOUND)
    macro_log_feature(PYKDE_FOUND "PyKDE" "PyKDE was not found.  It is needed by guidance-power-manager to run.  (Use -DINSTALL_POWER_MANAGER=TRUE to install anyway)" "http://www.riverbankcomputing.co.uk/pykde/" FALSE)
ENDIF(NOT PYKDE_FOUND)

find_package(PyDBus)
IF(NOT PYDBUS_FOUND)
    macro_log_feature(PYDBUS_FOUND "PyDBus" "PyDBus was not found.  It is needed by guidance-power-manager to run.  (Use -DINSTALL_POWER_MANAGER=TRUE to install anyway)" "http://dbus.freedesktop.org/releases/dbus-python/" FALSE)
ENDIF(NOT PYDBUS_FOUND)

IF(PYQT4_FOUND AND PYKDE_FOUND AND PYDBUS_FOUND)
    SET(INSTALL_POWER_MANAGER TRUE)
ENDIF(PYQT4_FOUND AND PYKDE_FOUND AND PYDBUS_FOUND)

IF(INSTALL_POWER_MANAGER)
    install( FILES
        guidance-power-manager.py
        guidance-power-manager.ui
        powermanage.py
        DESTINATION ${DATA_INSTALL_DIR}/guidance-power-manager )
    PYKDE4_ADD_EXECUTABLE(guidance-power-manager.py guidance-power-manager)
    add_subdirectory(modules)
    install(FILES guidance-power-manager.desktop DESTINATION ${AUTOSTART_INSTALL_DIR})
ENDIF(INSTALL_POWER_MANAGER)
find_package(Msgfmt REQUIRED)
find_package(Gettext REQUIRED)
add_subdirectory( po )
add_subdirectory( doc-translations )
