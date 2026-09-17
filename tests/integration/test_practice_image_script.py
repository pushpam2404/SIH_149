"""scripts/make_practice_image.py: the image it builds must give the photo back byte-exact."""
import sys

import pytest

from app.core.recovery.tsk_engine import TskEngine
from scripts import make_practice_image

pytestmark = pytest.mark.skipif(not TskEngine().is_available(), reason="pytsk3 is not installed")


def test_practice_image_photo_is_recoverable(tmp_path, monkeypatch):
    photo = tmp_path / "holiday.jpg"
    photo.write_bytes(b"\xFF\xD8\xFF\xE0" + bytes(range(256)) * 400 + b"\xFF\xD9")
    out = tmp_path / "practice.img"
    monkeypatch.setattr(sys, "argv", ["make_practice_image", str(photo), "--out", str(out)])

    assert make_practice_image.main() == 0

    candidates = TskEngine().scan(str(out), str(tmp_path / "recovered"))
    recovered = [c for c in candidates if open(c.recovered_path, "rb").read() == photo.read_bytes()]
    assert len(recovered) == 1
    assert recovered[0].suggested_name.endswith("HOTO1.JPG")


def test_practice_image_rejects_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["make_practice_image", str(tmp_path / "nope.jpg")])
    assert make_practice_image.main() == 1
