"""Streaming speech boundaries preserve numbers, titles and early complete clauses."""

import pytest

from alojan_agent.phrases import phrase_end


@pytest.mark.parametrize(
    "text", ["Saat 12.", "Saat 12.30", "Tutar 1,25", "Dr. Deniz", "12. toplantı"]
)
def test_incomplete_numeric_or_title_boundary_is_not_spoken(text):
    assert phrase_end(text) is None


def test_long_clause_starts_before_the_rest_of_the_sentence_arrives():
    text = "Burhan Bey için bıraktığınız mesajı not alabilirim, "
    assert phrase_end(text) == len(text.rstrip())
    assert phrase_end("Merhaba, ") is None
    assert phrase_end("Doğru mu?") == 9
    assert phrase_end("Notunuzu kaydettim.") == 19
    assert phrase_end("Dr.") is None


def test_large_chunks_remain_bounded_without_spaces_or_with_late_punctuation():
    assert phrase_end("a" * 300 + ". ") == 240
    assert 0 < phrase_end("mesaj " * 60 + ". ") <= 240
