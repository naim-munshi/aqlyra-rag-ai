"""Fail closed before importing the RTC worker or allocating provider resources.

The Docker entrypoint invokes this module directly with the LiveKit command:
`python -m app.voice.launch start`.
"""
from __future__ import annotations

import runpy
from app.voice.preflight import main as preflight_main


def main() -> int:
    result = preflight_main()
    if result != 0:
        return result
    # Preserve sys.argv (including LiveKit's "start" argument) while running
    # the existing worker module as __main__. No second AI brain is created.
    runpy.run_module("app.voice.worker", run_name="__main__", alter_sys=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
