"""No worker imports or provider connections should happen before preflight passes."""

from app.voice import launch


def test_failed_preflight_never_imports_worker(monkeypatch):
    monkeypatch.setattr(launch, "preflight_main", lambda: 1)

    def unexpected(*args, **kwargs):
        raise AssertionError("Worker imported despite failed preflight")

    monkeypatch.setattr(launch.runpy, "run_module", unexpected)
    assert launch.main() == 1


def test_successful_preflight_runs_existing_worker_with_start_args_intact(monkeypatch):
    observed = {}

    monkeypatch.setattr(launch, "preflight_main", lambda: 0)

    def record(module, *, run_name, alter_sys):
        observed.update(module=module, run_name=run_name, alter_sys=alter_sys)

    monkeypatch.setattr(launch.runpy, "run_module", record)
    assert launch.main() == 0
    assert observed == {
        "module": "app.voice.worker",
        "run_name": "__main__",
        "alter_sys": False,
    }
