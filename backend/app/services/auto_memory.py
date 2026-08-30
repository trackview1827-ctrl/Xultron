import re
import unicodedata

from app.extensions import db
from app.models import MemoryItem, utcnow
from app.security.redaction import redact

MAX_AUTO_MEMORY_CHARS = 1200

# Automatic memory is intentionally conservative. It keeps durable facts and
# outcomes, not a transcript of every message.
_SENSITIVE = re.compile(
    r"(?i)\b(password|parola|şifre|sifre|passcode|pin|otp|api[_ -]?key|secret|token|"
    r"access[_ -]?key|credit card|kredi kartı|kart numarası|cvv|iban|"
    r"tc kimlik|social security|ssn|private key|özel anahtar|telefon|phone|mobile|"
    r"adres|address|street|sokak|cadde|mahalle|teşhis|teshis|diagnosis|hastalığım|"
    r"hastaligim|medical|health|sağlık|saglik)\b"
)
_CONTACT_VALUE = re.compile(r"(?:\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b|(?:\+?\d[\d ()-]{7,}\d))")
_QUESTION_START = re.compile(
    r"(?i)^\s*(kim|ne|neden|niçin|nasil|nasıl|hangi|kaç|nerede|when|what|why|how|who|where|can|could|should|is|are|do|does)\b"
)

_PATTERNS = (
    ("personal", "Kullanıcı adı", re.compile(r"(?i)^(?:benim\s+)?(?:adım|adim|ismim)\s+([\wÇĞİÖŞÜçğıöşü][\wÇĞİÖŞÜçğıöşü .'-]{1,78}?)(?=\s+(?:ve|ama|projem|tercihim)\b|$)"), "Kullanıcının adı: {value}"),
    ("personal", "User name", re.compile(r"(?i)^(?:my name is|call me)\s+([a-z][a-z .'-]{1,78}?)(?=\s+(?:and|but|my project|I prefer)\b|$)"), "User's name: {value}"),
    ("personal", "Aktif proje", re.compile(r"(?i)\b(?:projemin adı|proje adı|üzerinde çalıştığım proje)\s*[:=-]?\s*([^.!?\n]{2,120})"), "Aktif proje: {value}"),
    ("personal", "Aktif proje", re.compile(r"(?i)\b([^.!?\n]{2,80}?)\s+projesi(?:nin)?\s+(?:üzerinde\s+)?çalış(?:ıyorum|iyoruz)\b"), "Aktif proje: {value}"),
    ("personal", "Active project", re.compile(r"(?i)\b(?:I am|I'm|we are|we're) working on (?:the )?([^.!?\n]{2,100}?)(?: project)?(?:[.!?]|$)"), "Active project: {value}"),
    ("important", "Alınan karar", re.compile(r"(?i)\b(?:karar verdim|kararlaştırdık|kararımız|bundan sonra)\s*[:=-]?\s*([^?\n]{3,500})"), "Karar: {value}"),
    ("important", "Decision", re.compile(r"(?i)\b(?:I decided|we decided|the decision is)\s+(?:to\s+)?([^?\n]{3,500})"), "Decision: {value}"),
    ("important", "Çözülen sorun", re.compile(r"(?i)\b((?:sorunu|problemi|hatayı)\s+[^?\n]{3,500}?\s+çözd(?:üm|ük))\b"), "Çözüm: {value}"),
    ("important", "Çözülen sorun", re.compile(r"(?i)\b(?:çözüm|cozum)\s*[:=-]\s*([^?\n]{3,500})"), "Çözüm: {value}"),
    ("important", "Solved problem", re.compile(r"(?i)\b((?:I|we) (?:fixed|solved)\s+[^?\n]{3,500})"), "Solution: {value}"),
    ("preferences", "Kullanıcı tercihi", re.compile(r"(?i)\b(?:tercih ederim|tercihim|hep kullanırım)\s*[:=-]?\s*([^?\n]{3,300})"), "Tercih: {value}"),
    ("preferences", "User preference", re.compile(r"(?i)\b(?:I prefer|my preference is|always use)\s+([^?\n]{3,300})"), "Preference: {value}"),
)


def _clean(value: str) -> str:
    value = re.sub(r"\s+", " ", value).strip(" \t\r\n.,;:!\"'")
    return value[:MAX_AUTO_MEMORY_CHARS]


def _key(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).casefold()
    return re.sub(r"[^a-z0-9çğıöşü]+", " ", value).strip()


def extract_durable_memories(message: str) -> list[dict[str, str]]:
    """Return only explicit, durable, non-sensitive facts from a user message."""
    text = _clean(redact(message))
    if not text or "[REDACTED]" in text or _SENSITIVE.search(text) or _CONTACT_VALUE.search(text):
        return []
    if text.endswith("?") or _QUESTION_START.search(text) or text.startswith(('"', "'", "“", "‘")):
        return []

    found = []
    seen = set()
    for category, title, pattern, template in _PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        groups = [_clean(part) for part in match.groups() if part]
        value = " | ".join(groups)
        if not value or len(value) < 2:
            continue
        if re.search(r"(?i)\b(eğer|eger|belki|düşünüyorum|dusunuyorum|if|maybe|might|may)\b", value):
            continue
        content = template.format(value=value)
        fingerprint = (category, _key(content))
        if fingerprint not in seen:
            found.append({"title": title, "content": content, "category": category})
            seen.add(fingerprint)
    return found[:3]


def remember_from_message(user_id: str, message: str) -> list[MemoryItem]:
    """Upsert selectively extracted memories into the user's durable memory."""
    saved = []
    for candidate in extract_durable_memories(message):
        existing = MemoryItem.query.filter_by(
            user_id=user_id,
            category=candidate["category"],
            title=candidate["title"],
        ).all()
        exact = next((item for item in existing if _key(item.content) == _key(candidate["content"])), None)
        if exact:
            exact.updated_at = utcnow()
            saved.append(exact)
            continue
        # A person's current name is a single evolving slot. Projects,
        # preferences, decisions and solutions may legitimately have many items.
        if candidate["title"] in {"Kullanıcı adı", "User name"} and existing:
            item = existing[0]
            item.content = candidate["content"]
            item.updated_at = utcnow()
        else:
            item = MemoryItem(user_id=user_id, **candidate)
            db.session.add(item)
        saved.append(item)
    return saved
