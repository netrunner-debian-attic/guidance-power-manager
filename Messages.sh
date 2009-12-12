#!/bin/sh
$EXTRACTRC *.ui >> ./ui.py || exit 11
$XGETTEXT --language=Python *.py -o $podir/guidance-power-manager.pot
rm -f ui.py
