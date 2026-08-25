"""Bounded fuzzy matching for a small, explicit intent vocabulary.

The normalize, edit-distance, and guarded matching structure is adapted from
OpenClaw's MIT-licensed command suggestion and activation-name matching code.
See THIRD_PARTY_NOTICES.md for attribution and license details.
"""

from __future__ import annotations

import re
import unicodedata


_TURKISH_ASCII = str.maketrans({"ç": "c", "ğ": "g", "ı": "i", "ö": "o", "ş": "s", "ü": "u"})


def normalize_for_match(value: str) -> str:
    """Normalize case, Turkish diacritics, punctuation, and whitespace."""
    normalized = unicodedata.normalize("NFKC", value).casefold().translate(_TURKISH_ASCII)
    normalized = re.sub(r"[^a-z0-9\s-]", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def bounded_levenshtein(left: str, right: str, maximum: int) -> int | None:
    """Return edit distance up to ``maximum`` without unbounded work."""
    if maximum < 0 or abs(len(left) - len(right)) > maximum:
        return None
    if left == right:
        return 0
    if not left or not right:
        distance = max(len(left), len(right))
        return distance if distance <= maximum else None
    if len(left) > len(right):
        left, right = right, left

    previous = list(range(len(left) + 1))
    for row, right_char in enumerate(right, 1):
        current = [row]
        row_minimum = row
        for column, left_char in enumerate(left, 1):
            current.append(
                min(
                    current[column - 1] + 1,
                    previous[column] + 1,
                    previous[column - 1] + (left_char != right_char),
                )
            )
            row_minimum = min(row_minimum, current[column])
        if row_minimum > maximum:
            return None
        previous = current

    distance = previous[-1]
    return distance if distance <= maximum else None


def matches_any_phrase(value: str, phrases: tuple[str, ...]) -> bool:
    """Match exact phrases first, then conservatively tolerate small token typos."""
    normalized = normalize_for_match(value)
    if not normalized:
        return False
    tokens = normalized.split()

    for phrase in phrases:
        candidate = normalize_for_match(phrase)
        if not candidate:
            continue
        if re.search(rf"(?:^|\s){re.escape(candidate)}(?:$|\s)", normalized):
            return True
        candidate_tokens = candidate.split()
        if all(any(_token_matches(token, expected) for token in tokens) for expected in candidate_tokens):
            return True
    return False


def _token_matches(token: str, expected: str) -> bool:
    if token == expected:
        return True
    if len(expected) <= 3:
        return False

    maximum = 1 if len(expected) <= 5 else min(2, max(1, len(expected) // 4))
    if abs(len(token) - len(expected)) <= maximum:
        if bounded_levenshtein(token, expected, maximum) is not None:
            return True

    # Turkish suffixes are common. Compare only a tightly bounded root and allow
    # at most four suffix characters, while preserving the same edit limit.
    suffix_length = len(token) - len(expected)
    if 1 <= suffix_length <= 4:
        return bounded_levenshtein(token[: len(expected)], expected, maximum) is not None
    return False
