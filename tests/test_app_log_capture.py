"""Tests for app_log_capture.py — log file path, read_log_tail, TeeStream."""


from hotkey_transcriber.app_log_capture import _TeeStream, read_log_tail


class _FakeFile:
    def __init__(self):
        self.data = ""

    def write(self, text):
        self.data += text

    def flush(self):
        pass


def test_tee_stream_writes_to_logfile():
    logfile = _FakeFile()
    stream = _TeeStream(original=None, logfile=logfile)
    stream.write("hello")
    assert logfile.data == "hello"


def test_tee_stream_writes_to_original():
    logfile = _FakeFile()
    original = _FakeFile()
    stream = _TeeStream(original=original, logfile=logfile)
    stream.write("world")
    assert original.data == "world"
    assert logfile.data == "world"


def test_tee_stream_converts_non_string():
    logfile = _FakeFile()
    stream = _TeeStream(original=None, logfile=logfile)
    stream.write(42)  # type: ignore[arg-type]
    assert logfile.data == "42"


def test_tee_stream_returns_length():
    logfile = _FakeFile()
    stream = _TeeStream(original=None, logfile=logfile)
    result = stream.write("abc")
    assert result == 3


def test_tee_stream_handles_broken_original():
    class _BrokenFile:
        def write(self, text):
            raise OSError("broken")

        def flush(self):
            raise OSError("broken")

    logfile = _FakeFile()
    stream = _TeeStream(original=_BrokenFile(), logfile=logfile)
    # Should not raise
    stream.write("safe")
    stream.flush()
    assert logfile.data == "safe"


def test_read_log_tail_missing_file(tmp_path):
    missing = tmp_path / "nope.log"
    result = read_log_tail(missing)
    assert "Noch keine Logs" in result


def test_read_log_tail_returns_content(tmp_path):
    log = tmp_path / "test.log"
    log.write_text("line one\nline two\n", encoding="utf-8")
    result = read_log_tail(log)
    assert "line one" in result
    assert "line two" in result


def test_read_log_tail_truncates_large_file(tmp_path):
    log = tmp_path / "big.log"
    # Write more than max_bytes
    content = "x" * 300_000
    log.write_bytes(content.encode("utf-8"))
    result = read_log_tail(log, max_bytes=100)
    # Should only return the last 100 bytes
    assert len(result) == 100
