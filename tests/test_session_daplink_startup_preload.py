import unittest

from PyQt5.QtCore import QCoreApplication

from App.Core.Session.session_daplink import (
    DaplinkProgrammerEventType,
    DaplinkPyocdSession,
    DaplinkRequestPayload,
)


class _DispatchSession(DaplinkPyocdSession):
    def __init__(self):
        super().__init__(_event_receiver=None)
        self.start_calls = []

    def _start_action(self, action: str, worker, silent: bool = False) -> None:
        self.start_calls.append((action, silent, worker is not None))


class _CollectingSession(DaplinkPyocdSession):
    def __init__(self):
        super().__init__(_event_receiver=None)
        self.events = []

    def _post_event(self, evt) -> None:
        self.events.append(evt)


class _LoadTargetsSession(_CollectingSession):
    @classmethod
    def discover_pack_targets(cls):
        return [], []


class DaplinkStartupPreloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QCoreApplication.instance() or QCoreApplication([])

    def test_load_targets_request_propagates_silent_flag(self):
        session = _DispatchSession()
        session._handle_request(DaplinkRequestPayload(action="load_targets", silent=True))

        self.assertEqual(session.start_calls, [("load_targets", True, True)])

    def test_silent_load_targets_posts_targets_without_log_noise(self):
        session = _LoadTargetsSession()
        session._load_targets_worker(silent=True)

        event_types = [event.type() for event in session.events]
        self.assertEqual(
            event_types,
            [int(DaplinkProgrammerEventType.TARGETS)],
        )

    def test_manual_load_targets_keeps_existing_log_behavior(self):
        session = _LoadTargetsSession()
        session._load_targets_worker(silent=False)

        event_types = [event.type() for event in session.events]
        self.assertEqual(
            event_types,
            [
                int(DaplinkProgrammerEventType.TARGETS),
                int(DaplinkProgrammerEventType.LOG),
            ],
        )


if __name__ == "__main__":
    unittest.main()

