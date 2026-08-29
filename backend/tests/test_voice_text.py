from app.services.voice import spoken_text


def test_turkish_tts_expands_common_number_forms():
    assert spoken_text("Saat 14:30, fiyat 1250 TL ve indirim %25.", "tr") == (
        "Saat on dört otuz, fiyat bin iki yüz elli Türk lirası ve indirim yüzde yirmi beş."
    )
    assert spoken_text("Sıcaklık -3,5 derece; tarih 29.08.2026.", "tr") == (
        "Sıcaklık eksi üç virgül beş derece; tarih yirmi dokuz Ağustos iki bin yirmi altı."
    )
    assert spoken_text("Saat 09:05.", "tr") == "Saat dokuz beş."
    assert spoken_text("Bakiye 1.250,50 TL.", "tr") == "Bakiye bin iki yüz elli virgül elli Türk lirası."


def test_azerbaijani_tts_expands_numbers_and_preserves_ids():
    assert spoken_text("Qiymət 2048, endirim 10%.", "az") == "Qiymət iki min qırx səkkiz, endirim faiz on."
    assert spoken_text("Kod 007 və versiya v2.", "az") == "Kod sıfır sıfır yeddi və versiya v2."


def test_other_locales_are_left_unchanged():
    assert spoken_text("Version 2 costs $10.", "en") == "Version 2 costs $10."
