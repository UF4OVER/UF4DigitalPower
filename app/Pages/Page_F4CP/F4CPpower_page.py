# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : dark
#  @Time    : 2026 - 02-10 18:39
#  @FileName: F4CPpower_page.py
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact : 
#  @Python  : 
# -------------------------------

from app.Config import SettingMangerInstance as SMI

from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QMainWindow
from .F4CPui import Ui_Frame

class F4CPowerPage(QWidget, Ui_Frame):
    def __init__(self, parent=None):
        super(F4CPowerPage, self).__init__()
        self.setupUi(self)




