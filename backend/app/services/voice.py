import re
import unicodedata


_NUMBER_WORDS = {
    "tr": {
        "ones": ("sıfır", "bir", "iki", "üç", "dört", "beş", "altı", "yedi", "sekiz", "dokuz"),
        "tens": ("", "on", "yirmi", "otuz", "kırk", "elli", "altmış", "yetmiş", "seksen", "doksan"),
        "scales": ("", "bin", "milyon", "milyar", "trilyon", "katrilyon"),
        "hundred": "yüz", "decimal": "virgül", "minus": "eksi", "percent": "yüzde",
        "months": ("", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"),
        "currency": {"₺": "Türk lirası", "TL": "Türk lirası", "$": "dolar", "€": "euro"},
        "time": "saat",
    },
    "az": {
        "ones": ("sıfır", "bir", "iki", "üç", "dörd", "beş", "altı", "yeddi", "səkkiz", "doqquz"),
        "tens": ("", "on", "iyirmi", "otuz", "qırx", "əlli", "altmış", "yetmiş", "səksən", "doxsan"),
        "scales": ("", "min", "milyon", "milyard", "trilyon", "katrilyon"),
        "hundred": "yüz", "decimal": "vergül", "minus": "mənfi", "percent": "faiz",
        "months": ("", "yanvar", "fevral", "mart", "aprel", "may", "iyun", "iyul", "avqust", "sentyabr", "oktyabr", "noyabr", "dekabr"),
        "currency": {"₺": "Türkiyə lirəsi", "TL": "Türkiyə lirəsi", "$": "dollar", "€": "avro"},
        "time": "saat",
    },
}


def _under_thousand(value: int, words: dict) -> str:
    parts = []
    hundreds, remainder = divmod(value, 100)
    if hundreds:
        if hundreds > 1:
            parts.append(words["ones"][hundreds])
        parts.append(words["hundred"])
    tens, ones = divmod(remainder, 10)
    if tens:
        parts.append(words["tens"][tens])
    if ones:
        parts.append(words["ones"][ones])
    return " ".join(parts)


def _integer_words(raw: str, words: dict) -> str:
    negative = raw.startswith("-")
    digits = raw.removeprefix("-")
    if len(digits) > 1 and digits.startswith("0"):
        spoken = " ".join(words["ones"][int(digit)] for digit in digits)
        return f'{words["minus"]} {spoken}' if negative else spoken
    value = int(digits or "0")
    if value == 0:
        spoken = words["ones"][0]
    elif value >= 1000 ** len(words["scales"]):
        spoken = " ".join(words["ones"][int(digit)] for digit in digits)
    else:
        groups = []
        scale = 0
        while value:
            value, group = divmod(value, 1000)
            if group:
                if scale == 1 and group == 1:
                    chunk = words["scales"][scale]
                else:
                    chunk = _under_thousand(group, words)
                    if words["scales"][scale]:
                        chunk = f'{chunk} {words["scales"][scale]}'
                groups.append(chunk)
            scale += 1
        spoken = " ".join(reversed(groups))
    return f'{words["minus"]} {spoken}' if negative else spoken


def _number_words(raw: str, words: dict) -> str:
    normalized = raw.replace(",", ".")
    if "." not in normalized:
        return _integer_words(normalized, words)
    whole, fraction = normalized.split(".", 1)
    if fraction.startswith("0") or len(fraction) > 2:
        fraction_words = " ".join(words["ones"][int(digit)] for digit in fraction)
    else:
        fraction_words = _integer_words(fraction, words)
    return f'{_integer_words(whole, words)} {words["decimal"]} {fraction_words}'


def spoken_text(text: str, locale: str = "tr") -> str:
    """Expand numeric tokens before TTS so speech models pronounce them naturally."""
    language = (locale or "tr").lower().split("-", 1)[0]
    words = _NUMBER_WORDS.get(language)
    if not words or not isinstance(text, str) or not re.search(r"\d", text):
        return text

    def localized_number(raw: str) -> str:
        if re.fullmatch(r"-?\d{1,3}(?:\.\d{3})+(?:,\d+)?", raw):
            raw = raw.replace(".", "")
        return _number_words(raw, words)

    def date(match):
        day, month, year = match.groups()
        month_index = int(month)
        if not 1 <= month_index <= 12:
            return match.group(0)
        return f'{_integer_words(str(int(day)), words)} {words["months"][month_index]} {_integer_words(str(int(year)), words)}'

    def clock(match):
        hour, minute = match.groups()
        if int(hour) > 23 or int(minute) > 59:
            return match.group(0)
        return f'{_integer_words(str(int(hour)), words)} {_integer_words(str(int(minute)), words)}'

    def currency_prefix(match):
        symbol, number = match.groups()
        return f'{localized_number(number)} {words["currency"][symbol]}'

    def currency_suffix(match):
        number, symbol = match.groups()
        return f'{localized_number(number)} {words["currency"][symbol.upper()]}'

    result = re.sub(r"(?<!\d)(\d{1,2})[./-](\d{1,2})[./-](\d{4})(?!\d)", date, text)
    result = re.sub(r"(?<!\d)([01]?\d|2[0-3]):([0-5]\d)(?!\d)", clock, result)
    number_token = r"-?(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d+)?"
    result = re.sub(rf"([₺$€])\s*({number_token})", currency_prefix, result)
    result = re.sub(rf"({number_token})\s*(TL|tl|₺|\$|€)(?!\w)", currency_suffix, result)
    result = re.sub(rf"%\s*({number_token})", lambda m: f'{words["percent"]} {localized_number(m.group(1))}', result)
    result = re.sub(rf"({number_token})\s*%", lambda m: f'{words["percent"]} {localized_number(m.group(1))}', result)
    result = re.sub(r"(?<![\w])-?\d{1,3}(?:\.\d{3})+(?:,\d+)?(?![\w])", lambda m: localized_number(m.group(0)), result)
    result = re.sub(r"(?<![\w])(-?\d+[.,]\d+)(?![\w])", lambda m: _number_words(m.group(1), words), result)
    result = re.sub(r"(?<![\w])(-?\d+)(?![\w])", lambda m: _integer_words(m.group(1), words), result)
    return re.sub(r"\s+", " ", result).strip()


def speech_text(value: object, max_length: int = 20000) -> str:
    """Remove provider non-speech annotations without amplitude-gating real speech."""
    text = value if isinstance(value, str) else ""
    text = text[:max_length].strip()
    if not text:
        return ""

    folded = text.casefold().replace("_", " ")
    folded = "".join(
        char
        for char in unicodedata.normalize("NFKD", folded)
        if unicodedata.category(char) != "Mn"
    )
    marker_wrapped = bool(re.fullmatch(r"\s*[\[({<♪♫].*[\])}>♪♫]\s*", text, re.DOTALL))
    normalized = re.sub(r"[^\wçğıöşüə]+", " ", folded, flags=re.UNICODE)
    normalized = re.sub(r"\d+", "", normalized).strip()
    non_speech = (
        "müzik", "muzik", "music", "blank audio", "blankaudio", "silence",
        "sessizlik", "applause", "alkış", "alkis", "background noise",
    )
    if marker_wrapped and (
        not normalized
        or any(term in normalized for term in non_speech)
        or re.fullmatch(r"x\s*", normalized)
    ):
        return ""

    lines = [re.sub(r"\s+", " ", line).strip().casefold() for line in text.splitlines() if line.strip()]
    repeated_hallucination = ("bu videonun", "izlediğiniz için teşekkür", "altyazı")
    if len(lines) >= 3 and len(set(lines)) == 1 and any(phrase in lines[0] for phrase in repeated_hallucination):
        return ""
    return text
