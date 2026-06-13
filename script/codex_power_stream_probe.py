from __future__ import annotations

import sys
import time
from pathlib import Path

from PyQt5.QtCore import QCoreApplication

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.session.session_power import F4CPPowerClient
from app.session.session_serial import SerialConfig, SerialSession


def pump(app: QCoreApplication, seconds: float) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.005)


def main() -> int:
    app = QCoreApplication.instance() or QCoreApplication([])

    logs: list[str] = []
    errors: list[str] = []
    statuses: list[object] = []

    client = F4CPPowerClient()
    client.log.connect(logs.append)
    client.error.connect(errors.append)
    client.statusUpdated.connect(statuses.append)

    session = SerialSession(SerialConfig(port="COM10", baudrate=921600, read_timeout_s=0.2))
    session.open()
    try:
        client.attach_session(session)
        pump(app, 0.2)

        print("STEP report")
        status = client.read_status(timeout_ms=1000)
        print(f"REPORT vin={status.vin_v:.3f} iin={status.iin_a:.3f} vout={status.vout_v:.3f} iout={status.iout_a:.3f}")

        print("STEP stream_start")
        client.start_streaming(interval_ms=500, timeout_ms=1000)
        pump(app, 1.5)
        print(f"STREAM statuses={len(statuses)} errors={len(errors)}")

        print("STEP stream_stop")
        client.stop_streaming(timeout_ms=1000)
        pump(app, 0.2)

        print("LOG_TAIL_BEGIN")
        for item in logs[-40:]:
            print(item)
        print("LOG_TAIL_END")

        if errors:
            print("ERRORS_BEGIN")
            for item in errors:
                print(item)
            print("ERRORS_END")
            return 2

        return 0
    finally:
        try:
            client.detach_session()
        except Exception:
            pass
        try:
            session.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
