from app.core.recovery.classifier import classify
from app.core.recovery.confidence import confidence_label, score_candidate
from app.core.recovery.engine_base import RecoveredFileCandidate
from app.core.recovery.signatures import match_header


def test_match_header_detects_jpeg():
    data = b"\xff\xd8\xff\xe0" + b"\x00" * 100 + b"\xff\xd9"
    sig = match_header(data)
    assert sig is not None
    assert sig.file_type == "JPEG"


def test_match_header_returns_none_for_unknown_data():
    assert match_header(b"not a known file type at all") is None


def test_classify_intact_jpeg(tmp_path):
    path = tmp_path / "f0001.jpg"
    path.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 200 + b"\xff\xd9")

    result = classify(str(path), suggested_name="f0001.jpg")

    assert result.file_type == "JPEG"
    assert result.header_matched
    assert result.footer_matched


def test_classify_truncated_jpeg_has_no_footer_match(tmp_path):
    path = tmp_path / "f0002.jpg"
    path.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 200)  # no JPEG footer marker

    result = classify(str(path), suggested_name="f0002.jpg")

    assert result.file_type == "JPEG"
    assert result.header_matched
    assert not result.footer_matched


def test_confidence_score_higher_for_complete_file_than_truncated(tmp_path):
    complete = tmp_path / "complete.jpg"
    complete.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 200 + b"\xff\xd9")
    truncated = tmp_path / "truncated.jpg"
    truncated.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 200)

    complete_classification = classify(str(complete), "complete.jpg")
    truncated_classification = classify(str(truncated), "truncated.jpg")

    complete_candidate = RecoveredFileCandidate(
        source_engine="photorec", recovered_path=str(complete), suggested_name="complete.jpg", size_bytes=206
    )
    truncated_candidate = RecoveredFileCandidate(
        source_engine="photorec", recovered_path=str(truncated), suggested_name="truncated.jpg", size_bytes=204
    )

    complete_score, _ = score_candidate(complete_classification, complete_candidate)
    truncated_score, _ = score_candidate(truncated_classification, truncated_candidate)

    assert complete_score > truncated_score
    assert confidence_label(complete_score) in ("high", "medium")


def test_fragmented_candidate_scores_lower_than_contiguous(tmp_path):
    path = tmp_path / "f0003.jpg"
    path.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 200 + b"\xff\xd9")
    classification = classify(str(path), "f0003.jpg")

    contiguous = RecoveredFileCandidate(
        source_engine="photorec", recovered_path=str(path), suggested_name="f0003.jpg",
        size_bytes=206, is_fragmented=False,
    )
    fragmented = RecoveredFileCandidate(
        source_engine="photorec", recovered_path=str(path), suggested_name="f0003.jpg",
        size_bytes=206, is_fragmented=True,
    )

    contiguous_score, _ = score_candidate(classification, contiguous)
    fragmented_score, _ = score_candidate(classification, fragmented)

    assert contiguous_score > fragmented_score


def test_cross_engine_agreement_increases_score(tmp_path):
    path = tmp_path / "f0004.jpg"
    path.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 200 + b"\xff\xd9")
    classification = classify(str(path), "f0004.jpg")
    candidate = RecoveredFileCandidate(
        source_engine="photorec", recovered_path=str(path), suggested_name="f0004.jpg", size_bytes=206
    )

    solo_score, _ = score_candidate(classification, candidate, cross_engine_agreement=False)
    confirmed_score, _ = score_candidate(classification, candidate, cross_engine_agreement=True)

    assert confirmed_score > solo_score
