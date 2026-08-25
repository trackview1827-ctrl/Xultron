from app.services.text_intent import bounded_levenshtein, matches_any_phrase, normalize_for_match


def test_normalization_handles_turkish_diacritics_and_punctuation():
    assert normalize_for_match("  ŞARJIM, kaç? ") == "sarjim kac"


def test_bounded_edit_distance_stops_outside_limit():
    assert bounded_levenshtein("saaat", "saat", 1) == 1
    assert bounded_levenshtein("terminal", "tamamen", 1) is None


def test_guarded_phrase_matching_accepts_small_typos_but_not_unrelated_words():
    assert matches_any_phrase("Saaat kac?", ("saat kac",)) is True
    assert matches_any_phrase("termuks api iznin varmi", ("termux",)) is True
    assert matches_any_phrase("tamamen farkli", ("terminal",)) is False
    assert matches_any_phrase("sil bunu", ("pil",)) is False
