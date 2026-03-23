from __future__ import annotations

from datetime import date
from datetime import datetime
import re

from storage import normalize_entry, normalize_text


def merge_entry(existing: dict | None, incoming: dict | None, *, pragmatics: str = "") -> dict:
    entry = normalize_entry(existing or {})
    if incoming:
        entry.update(normalize_entry(incoming))
    if pragmatics:
        entry["pragmatics"] = pragmatics
    entry["is_favorite"] = bool((existing or {}).get("is_favorite", entry.get("is_favorite", False)))
    return entry


def upsert_word_entry(
    words: dict,
    word: str,
    incoming: dict | None,
    *,
    pragmatics: str = "",
) -> dict | None:
    normalized_word = normalize_text(word)
    if not normalized_word:
        return None

    payload = dict(incoming or {})
    payload["word"] = normalized_word
    if normalized_word not in words and not payload.get("added_at"):
        payload["added_at"] = datetime.utcnow().replace(microsecond=0).isoformat()
    merged = merge_entry(words.get(normalized_word, {}), payload, pragmatics=pragmatics)
    words[normalized_word] = merged
    return merged


def toggle_favorite_flag(words: dict, word: str) -> bool:
    if word not in words:
        return False
    current = bool(words[word].get("is_favorite", False))
    words[word]["is_favorite"] = not current
    return words[word]["is_favorite"]


def delete_word_entry(words: dict, word: str) -> bool:
    if word not in words:
        return False
    del words[word]
    return True


def favorite_word_entries(words: dict, selected_words) -> int:
    count = 0
    for word in selected_words:
        if word in words and not words[word].get("is_favorite", False):
            words[word]["is_favorite"] = True
            count += 1
    return count


def delete_word_entries(words: dict, selected_words) -> int:
    count = 0
    for word in list(selected_words):
        if delete_word_entry(words, word):
            count += 1
    return count


def update_entry_field(words: dict, word: str, field: str, value: str) -> bool:
    normalized_word = normalize_text(word)
    if normalized_word not in words:
        return False

    cleaned = str(value or "").strip()
    if not cleaned:
        return False

    upsert_word_entry(words, normalized_word, {field: cleaned})
    return True


def parse_import_lines(raw_text: str) -> list[tuple[str, str | None]]:
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    parsed: list[tuple[str, str | None]] = []
    index = 0

    while index < len(lines):
        line = lines[index]
        match = re.search(r"(=|:| - |\t|\s{2,})", line)

        if match:
            word = normalize_text(line[: match.start()])
            meaning = line[match.end() :].strip()
            parsed.append((word, meaning or None))
            index += 1
            continue

        if index + 1 < len(lines) and not re.search(r"(=|:| - |\t|\s{2,})", lines[index + 1]):
            parsed.append((normalize_text(line), lines[index + 1].strip() or None))
            index += 2
            continue

        parsed.append((normalize_text(line), None))
        index += 1

    return [(word, meaning) for word, meaning in parsed if word]


def import_parsed_entries(
    words: dict,
    parsed_lines: list[tuple[str, str | None]],
    *,
    resolver=None,
) -> tuple[int, list[str]]:
    added_count = 0
    failed_lines: list[str] = []

    for word, meaning in parsed_lines:
        info = None
        if meaning is None and resolver is not None:
            info = resolver(word)
            if info:
                meaning = info.get("meaning") or info.get("eng_meaning")

        if not meaning:
            failed_lines.append(word)
            continue

        incoming = {"meaning": meaning}
        if info:
            incoming.update(info)
        upsert_word_entry(words, word, incoming)
        added_count += 1

    return added_count, failed_lines


def pick_word_of_day(words: dict, day: date | None = None) -> tuple[str, dict] | None:
    if not words:
        return None

    target_day = day or date.today()
    ordered_words = sorted(words)
    index = target_day.toordinal() % len(ordered_words)
    word = ordered_words[index]
    return word, normalize_entry(words[word])
