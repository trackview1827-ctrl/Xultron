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


def test_tts_number_normalization_handles_non_prose_tokens_safely():
    assert spoken_text("Sürüm v1.2.3, IP 192.168.1.1.", "tr") == (
        "Sürüm versiyon bir nokta iki nokta üç, IP yüz doksan iki nokta yüz altmış sekiz nokta bir nokta bir."
    )
    assert spoken_text("Git: https://example.com/x?id=1250", "tr") == "Git: https://example.com/x?id=1250"
    assert spoken_text("Ara: +90 (555) 123 45 67.", "tr") == "Ara: +90 (555) 123 45 67."
    assert spoken_text("Geçersiz 31/02/2026 ve 00-12-2026.", "tr") == "Geçersiz 31/02/2026 ve 00-12-2026."
    assert spoken_text("Ücret $10.25.", "tr") == "Ücret on virgül yirmi beş dolar."
