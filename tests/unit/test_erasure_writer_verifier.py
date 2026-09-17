from app.core.erasure.verifier import verify_pass
from app.core.erasure.writer import write_pass


def _roundtrip(tmp_path, fill, size=2 * 1024 * 1024):
    path = tmp_path / "target.bin"
    path.write_bytes(b"\xAA" * size)  # pre-fill with something that is NOT the wipe pattern

    with open(path, "r+b") as f:
        write_pass(f, size, fill, chunk_size=64 * 1024)

    with open(path, "rb") as f:
        result = verify_pass(f, size, fill, block_size=64 * 1024)
    return result


def test_zero_fill_pass_verifies_ok(tmp_path):
    result = _roundtrip(tmp_path, "zero")
    assert result.ok
    assert result.fill_mode == "zero"


def test_ones_fill_pass_verifies_ok(tmp_path):
    result = _roundtrip(tmp_path, "ones")
    assert result.ok


def test_random_fill_pass_verifies_ok(tmp_path):
    result = _roundtrip(tmp_path, "random")
    assert result.ok


def test_verify_detects_unwiped_data(tmp_path):
    path = tmp_path / "target.bin"
    size = 1024 * 1024
    path.write_bytes(b"\xAA" * size)  # never wiped

    with open(path, "rb") as f:
        result = verify_pass(f, size, "zero", block_size=64 * 1024)

    assert not result.ok
    assert len(result.failures) > 0
