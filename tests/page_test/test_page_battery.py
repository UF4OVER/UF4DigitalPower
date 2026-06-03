# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 01-08 12:30
#  @FileName: test_page_battery.py
#  @FileType: 自动化测试文件，用来守住关键功能行为
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact :
#  @Python  : 3.10
# -------------------------------

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.widgets.pages import BatteryPage, BatterySnapshot


class BatteryPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def test_snapshot_updates_visual_sections(self):
        page = BatteryPage()
        try:
            snapshot = BatterySnapshot(
                cell_soc=(77.1, 76.8, 78.2, 77.5),
                cell_voltage=(3.812, 3.806, 3.824, 3.818),
                input_online=True,
                output_online=False,
                charge_state="charging",
                charge_current_a=4.2,
                discharge_current_a=0.0,
                pack_soc=77.4,
                pack_voltage_v=15.26,
                pack_current_a=4.2,
                nominal_capacity_ah=24.0,
                remaining_capacity_ah=18.3,
                health_percent=94.5,
                remaining_discharge_minutes=248,
                charged_in_ah=3.62,
                energy_in_wh=55.8,
                energy_out_wh=12.4,
            )

            page.updateSnapshot(snapshot)

            self.assertEqual(len(page.cellCards), 4)
            self.assertIn("77.4", page.packSocLabel.text())
            self.assertEqual(page.flowStateLabel.text(), "充电中")
            self.assertIn("输入: 已连接", page.inputBadge.text())
            self.assertIn("输出: 未使能", page.outputBadge.text())
            self.assertEqual(page.cellGrid.rowCount(), 1)
            self.assertEqual(page.cellGrid.columnCount(), 4)
            self.assertIn("电压：3.812", page.cellCards[0].voltageLabel.text())
            self.assertIn("容量：4575", page.cellCards[0].capacityLabel.text())
            self.assertEqual(page.cellCards[0].statusLabel.text(), "充电")
            self.assertEqual(page.cellCards[0].sohBar.value(), 94)
            self.assertIn("18.30", page.capacityTile.valueLabel.text())
            self.assertIn("94.5", page.healthTile.valueLabel.text())
            self.assertFalse(hasattr(page, "packSocBar"))
        finally:
            page.deleteLater()

    def test_connection_signal_uses_selected_mode(self):
        page = BatteryPage()
        try:
            requested_modes = []
            page.connectionRequested.connect(requested_modes.append)

            page.connectionModeCombo.setCurrentText("蓝牙")
            page.connectButton.click()

            self.assertEqual(requested_modes, ["蓝牙"])
            self.assertFalse(hasattr(page, "autoPollSwitch"))
        finally:
            page.deleteLater()


if __name__ == "__main__":
    unittest.main()
