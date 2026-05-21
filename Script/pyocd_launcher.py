# -*- coding: utf-8 -*-
"""Entry point for pyOCD CLI bundled inside a cx_Freeze frozen application.

This script is packaged as a ``console`` executable separate from the main
F4CP GUI so that the Daplink page can invoke ``pyocd flash ...`` via QProcess
without spawning a second GUI window.
"""

import sys


def _install_pyocd_filters():
    """Filter pyOCD entry-point plugins to only the ones F4CP needs.

    Must be called *before* any pyOCD import, otherwise pyOCD's plugin
    discovery will fail on modules that aren't bundled by cx_Freeze.
    """
    import importlib_metadata

    if getattr(importlib_metadata, "_f4cp_filters_installed", False):
        return

    _original = importlib_metadata.entry_points
    _allowed_probes = {"cmsisdap"}
    _allowed_rtos: set[str] = set()  # F4CP doesn't need RTOS plugins

    def _filtered(*args, **kwargs):
        groups = kwargs.pop("groups", None)
        group = kwargs.get("group")
        if group is None and groups:
            group = groups[0] if isinstance(groups, (list, tuple, set)) else groups
            kwargs["group"] = group

        eps = _original(*args, **kwargs)
        if group == "pyocd.probe":
            eps = [e for e in eps if e.name.lower() in _allowed_probes]
        elif group == "pyocd.rtos":
            eps = [e for e in eps if e.name.lower() in _allowed_rtos]
        return eps

    importlib_metadata.entry_points = _filtered
    importlib_metadata._f4cp_filters_installed = True


if __name__ == "__main__":
    _install_pyocd_filters()

    from pyocd.__main__ import main as pyocd_main

    sys.argv[0] = "pyocd"
    sys.exit(pyocd_main())
