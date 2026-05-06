import unittest

from PyQt5.QtCore import QCoreApplication

from App.Core.Session.session_daplink import (
    DaplinkProgrammerEventType,
    DaplinkPyocdSession,
)


class _CollectingSession(DaplinkPyocdSession):
    def __init__(self):
        super().__init__(_event_receiver=None)
        self.events = []

    def _post_event(self, evt) -> None:
        self.events.append(evt)


class DaplinkProcessOutputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self):
        self.session = _CollectingSession()
        self.session._reset_process_output_state()

    def _event_texts(self, event_type: DaplinkProgrammerEventType) -> list[str]:
        return [
            event.payload.text
            for event in self.session.events
            if event.type() == int(event_type)
        ]

    def _progress_values(self) -> list[int]:
        return [
            int(round(event.payload.percent))
            for event in self.session.events
            if event.type() == int(DaplinkProgrammerEventType.PROGRESS)
        ]

    def test_progress_fragments_are_not_logged_and_emit_incremental_progress(self):
        self.session._consume_process_output_chunk("0001794 I Erasing... [loader]\r\n")
        self.session._consume_process_output_chunk("[---|---|---|---|---|---|---|---|---|----]\r\n")
        for chunk in ["[", "=", "==", "=", "==", "=", "==", "==]", "\r\n"]:
            self.session._consume_process_output_chunk(chunk)
        self.session._consume_process_output_chunk("0005220 I Programming... [loader]\r\n")
        self.session._consume_process_output_chunk("[---|---|---|---|---|---|---|---|---|----]\r\n")
        for chunk in [
            "[",
            "=",
            "=",
            "==",
            "=",
            "==",
            "=",
            "==",
            "=",
            "==",
            "=",
            "==",
            "=",
            "==",
            "=",
            "==",
            "=",
            "==",
            "=",
            "==",
            "==]",
            "\r\n",
        ]:
            self.session._consume_process_output_chunk(chunk)

        logs = self._event_texts(DaplinkProgrammerEventType.LOG)
        progress_values = self._progress_values()

        self.assertEqual(
            logs,
            [
                "0001794 I Erasing... [loader]",
                "0005220 I Programming... [loader]",
            ],
        )
        self.assertFalse(any(log in {"[", "=", "==", "==]"} for log in logs))
        self.assertIn(0, progress_values)
        self.assertTrue(any(0 < value < 20 for value in progress_values))
        self.assertEqual(progress_values[-1], 100)

    def test_ansi_sequences_are_ignored_and_partial_line_flushes_cleanly(self):
        self.session._consume_process_output_chunk("\x1b[0m\r\n")
        self.session._consume_process_output_chunk(
            "\x1b[0m0000858 W Board ID UF40 is not recognized [mbed_board]"
        )
        self.session._flush_process_line_buffer()

        logs = self._event_texts(DaplinkProgrammerEventType.LOG)
        self.assertEqual(
            logs,
            ["0000858 W Board ID UF40 is not recognized [mbed_board]"],
        )


if __name__ == "__main__":
    unittest.main()

