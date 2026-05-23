# -*- coding: utf-8 -*-
"""Numpy-free compatibility shim for the small pyqtgraph API used by F4CP.

The real pyqtgraph package imports numpy at module import time. F4CP only needs
PlotWidget and mkPen in the power trend page, so this shim forwards those names
to the lightweight Qt-only renderer in App.Core.simple_plot.
"""

from App.Core.simple_plot import PlotWidget, mkPen

__all__ = ["PlotWidget", "mkPen"]
