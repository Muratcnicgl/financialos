"""
Confidence parser birim testleri (Wave-2 H1G3 Asama 3).
"""

from app.coach import _parse_confidence, _strip_confidence_marker


def test_basic_format():
    assert _parse_confidence("Yanit metni\n\n[CONFIDENCE: 0.85]") == 0.85


def test_case_insensitive():
    assert _parse_confidence("[Confidence: 0.7]") == 0.7
    assert _parse_confidence("[confidence: 0.6]") == 0.6
    assert _parse_confidence("[CONFIDENCE: 0.5]") == 0.5


def test_no_brackets():
    assert _parse_confidence("Yanit\n\nConfidence: 0.9") == 0.9


def test_percentage_normalization():
    assert _parse_confidence("[CONFIDENCE: 85]") == 0.85
    assert _parse_confidence("[CONFIDENCE: 100]") == 1.0


def test_missing_confidence():
    assert _parse_confidence("Sadece yanit, guven skoru yok.") is None
    assert _parse_confidence("") is None
    assert _parse_confidence(None) is None


def test_invalid_values():
    assert _parse_confidence("[CONFIDENCE: 1.5]") is None   # >1
    assert _parse_confidence("[CONFIDENCE: 200]") is None   # >100
    assert _parse_confidence("[CONFIDENCE: -0.5]") is None  # <0
    assert _parse_confidence("[CONFIDENCE: abc]") is None   # not number


def test_multiple_matches_last_wins():
    text = "Buradaki confidence onemli\n\n[CONFIDENCE: 0.9]"
    assert _parse_confidence(text) == 0.9


def test_strip_removes_marker():
    text = "Yanit metni\n\n[CONFIDENCE: 0.85]"
    assert _strip_confidence_marker(text) == "Yanit metni"


def test_strip_preserves_content():
    text = "Birinci satir\nIkinci satir\n[CONFIDENCE: 0.7]"
    result = _strip_confidence_marker(text)
    assert "Birinci satir" in result
    assert "Ikinci satir" in result
    assert "CONFIDENCE" not in result
    assert "0.7" not in result


def test_strip_no_marker():
    text = "Sadece yanit metni"
    assert _strip_confidence_marker(text) == "Sadece yanit metni"


def test_strip_empty():
    assert _strip_confidence_marker("") == ""
