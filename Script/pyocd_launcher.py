# -*- coding: utf-8 -*-
"""Entry point for pyOCD CLI bundled inside a cx_Freeze frozen application.

This script is packaged as a ``console`` executable separate from the main
F4CP GUI so that the Daplink page can invoke ``pyocd flash ...`` via QProcess
without spawning a second GUI window.
"""

import sys

if __name__ == "__main__":
    from pyocd.__main__ import main as pyocd_main

    # The first argument is the exe path; shift so pyOCD sees "flash ..."
    sys.argv[0] = "pyocd"
    sys.exit(pyocd_main())
