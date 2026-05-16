import contextlib
from pathlib import Path

from gopro_overlay.common import temp_file_name
from gopro_overlay.execution import InProcessExecution


@contextlib.contextmanager
def do_execute(execution, cmd):
    yield from execution.execute(cmd)


def test_in_process_execution():
    filename = temp_file_name()
    execution = InProcessExecution(redirect=filename)
    with do_execute(execution, ["cat"]) as out:
        out.write("Hello".encode())

    assert Path(filename).read_text() == "Hello"


class FakeStdin:
    def __init__(self):
        self.closed = False

    def flush(self):
        pass

    def close(self):
        self.closed = True


class FakeProcess:
    def __init__(self):
        self.stdin = FakeStdin()
        self.wait_timeout = object()

    def wait(self, timeout=None):
        self.wait_timeout = timeout
        return 0


def test_in_process_execution_waits_without_timeout_by_default():
    process = FakeProcess()
    execution = InProcessExecution(popen=lambda *args, **kwargs: process)

    with do_execute(execution, ["cmd"]):
        pass

    assert process.wait_timeout is None


def test_in_process_execution_uses_configured_wait_timeout():
    process = FakeProcess()
    execution = InProcessExecution(popen=lambda *args, **kwargs: process, wait_timeout=10)

    with do_execute(execution, ["cmd"]):
        pass

    assert process.wait_timeout == 10
