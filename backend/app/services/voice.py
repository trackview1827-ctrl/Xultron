import re
import unicodedata


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
