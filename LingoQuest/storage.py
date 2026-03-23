from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any


DEFAULT_ENTRY = {
    "meaning": "",
    "phonetic": "",
    "pronunciation": "",
    "ipa_uk": "",
    "ipa_us": "",
    "pos": "",
    "part_of_speech": "",
    "example": "",
    "eng_meaning": "",
    "pragmatics": "",
    "definitions": [],
    "tags": [],
    "direction": "en-vi",
    "added_at": "",
    "level": "",
    "is_favorite": False,
}

MOJIBAKE_MARKERS = ("Ã", "Â", "Ä", "Å", "Æ", "Ð", "áº", "á»", "â", "ð", "ï")
VALID_CEFR_LEVELS = ("A1", "A2", "B1", "B2", "C1", "C2")
EXPORT_FIELDS = (
    "word",
    "meaning",
    "phonetic",
    "pos",
    "example",
    "eng_meaning",
    "pragmatics",
    "level",
    "is_favorite",
)


def normalize_text(text: Any) -> str:
    return repair_text(str(text or "")).strip().lower()


def _mojibake_score(text: str) -> int:
    return sum(text.count(marker) for marker in MOJIBAKE_MARKERS)


def repair_text(value: Any) -> str:
    text = str(value or "")
    best = text
    best_score = _mojibake_score(best)

    if best_score == 0:
        return best

    for _ in range(2):
        improved = False
        for source_encoding in ("latin-1", "cp1252"):
            try:
                candidate = best.encode(source_encoding).decode("utf-8")
            except UnicodeError:
                continue

            candidate_score = _mojibake_score(candidate)
            if candidate_score < best_score:
                best = candidate
                best_score = candidate_score
                improved = True
                break

        if not improved:
            break

    return best


def normalize_cefr_level(level: Any) -> str:
    normalized = repair_text(level).strip().upper()
    return normalized if normalized in VALID_CEFR_LEVELS else ""


def normalize_tags(value: Any) -> list[str]:
    if isinstance(value, str):
        raw_tags = re.split(r"[;,|]", value)
    elif isinstance(value, (list, tuple, set)):
        raw_tags = list(value)
    else:
        raw_tags = []

    seen: set[str] = set()
    tags: list[str] = []
    for raw_tag in raw_tags:
        cleaned = repair_text(raw_tag).strip()
        normalized = cleaned.lower()
        if not cleaned or normalized in seen:
            continue
        seen.add(normalized)
        tags.append(cleaned)
    return tags


def normalize_definitions(value: Any, fallback_definition: str, fallback_example: str) -> list[dict[str, Any]]:
    definitions: list[dict[str, Any]] = []

    if isinstance(value, list):
        for item in value:
            if not isinstance(item, dict):
                continue
            definition_text = repair_text(item.get("definition", "")).strip()
            example_text = repair_text(item.get("example", "")).strip()
            synonyms = normalize_tags(item.get("synonyms", []))
            if definition_text or example_text or synonyms:
                definitions.append(
                    {
                        "definition": definition_text,
                        "example": example_text,
                        "synonyms": synonyms,
                    }
                )

    if definitions:
        return definitions

    if fallback_definition or fallback_example:
        return [
            {
                "definition": fallback_definition,
                "example": fallback_example,
                "synonyms": [],
            }
        ]

    return []


def estimate_cefr_level(word: Any, meaning: Any = "", pos: Any = "") -> str:
    normalized_word = normalize_text(word)
    normalized_meaning = repair_text(meaning).strip()
    normalized_pos = repair_text(pos).strip().lower()

    complexity = len(normalized_word.replace(" ", "").replace("-", ""))
    complexity += max(0, len(normalized_word.split()) - 1) * 2
    complexity += max(0, len(re.findall(r"\w+", normalized_meaning)) - 8) // 4

    if normalized_pos in {"idiom", "phrasal verb"}:
        complexity += 2

    if complexity <= 4:
        return "A1"
    if complexity <= 6:
        return "A2"
    if complexity <= 8:
        return "B1"
    if complexity <= 10:
        return "B2"
    if complexity <= 12:
        return "C1"
    return "C2"


def normalize_entry(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        raw_entry = {"meaning": value}
    elif isinstance(value, dict):
        raw_entry = dict(value)
    else:
        raw_entry = {}

    entry = DEFAULT_ENTRY.copy()
    entry.update(raw_entry)
    entry["meaning"] = repair_text(entry.get("meaning", "")).strip()
    entry["phonetic"] = repair_text(entry.get("phonetic", "")).strip()
    entry["pronunciation"] = repair_text(entry.get("pronunciation", "")).strip()
    entry["ipa_uk"] = repair_text(entry.get("ipa_uk", "")).strip()
    entry["ipa_us"] = repair_text(entry.get("ipa_us", "")).strip()
    entry["pos"] = repair_text(entry.get("pos", "")).strip()
    entry["part_of_speech"] = repair_text(entry.get("part_of_speech", "")).strip()
    entry["example"] = repair_text(entry.get("example", "")).strip()
    entry["eng_meaning"] = repair_text(entry.get("eng_meaning", "")).strip()
    entry["pragmatics"] = repair_text(entry.get("pragmatics", "")).strip()

    if not entry["phonetic"] and entry["pronunciation"]:
        entry["phonetic"] = entry["pronunciation"]
    if not entry["pronunciation"] and entry["phonetic"]:
        entry["pronunciation"] = entry["phonetic"]

    if not entry["ipa_uk"]:
        entry["ipa_uk"] = entry["phonetic"]
    if not entry["ipa_us"]:
        entry["ipa_us"] = entry["phonetic"]

    if not entry["pos"] and entry["part_of_speech"]:
        entry["pos"] = entry["part_of_speech"]
    if not entry["part_of_speech"] and entry["pos"]:
        entry["part_of_speech"] = entry["pos"]

    entry["tags"] = normalize_tags(entry.get("tags", []))
    entry["direction"] = repair_text(entry.get("direction", "")).strip() or "en-vi"
    entry["added_at"] = repair_text(entry.get("added_at", "")).strip()
    entry["definitions"] = normalize_definitions(
        entry.get("definitions", []),
        entry["eng_meaning"] or entry["meaning"],
        entry["example"],
    )
    word_hint = repair_text(entry.get("word", "")).strip()
    entry["level"] = normalize_cefr_level(entry.get("level")) or estimate_cefr_level(
        word_hint,
        entry["meaning"] or entry["eng_meaning"],
        entry["pos"],
    )
    if entry["level"] and entry["level"] not in entry["tags"]:
        entry["tags"].append(entry["level"])
    entry.pop("word", None)
    entry["is_favorite"] = bool(entry.get("is_favorite", False))
    return entry


def load_dictionary(pathlike: str | Path) -> dict[str, dict[str, Any]]:
    path = Path(pathlike)
    if not path.exists():
        return {}

    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, OSError):
        return {}

    if not isinstance(raw, dict):
        return {}

    words: dict[str, dict[str, Any]] = {}
    for key, value in raw.items():
        normalized_key = normalize_text(key)
        if not normalized_key:
            continue
        raw_entry = {"word": normalized_key}
        if isinstance(value, dict):
            raw_entry.update(value)
        else:
            raw_entry["meaning"] = value
        words[normalized_key] = normalize_entry(raw_entry)
    return words


def save_dictionary(
    pathlike: str | Path,
    words: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    path = Path(pathlike)
    processed: dict[str, dict[str, Any]] = {}

    for key, value in words.items():
        normalized_key = normalize_text(key)
        if not normalized_key:
            continue
        raw_entry = {"word": normalized_key}
        if isinstance(value, dict):
            raw_entry.update(value)
        else:
            raw_entry["meaning"] = value
        processed[normalized_key] = normalize_entry(raw_entry)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(processed, ensure_ascii=False, indent=4),
        encoding="utf-8",
    )
    return processed


def parse_legacy_line(line: str) -> tuple[str, dict[str, Any]] | None:
    raw_line = line.strip()
    if not raw_line or raw_line.startswith("#"):
        return None

    if "=" in raw_line:
        word, meaning = raw_line.split("=", 1)
        normalized_word = normalize_text(word)
        normalized_meaning = meaning.strip()
        if not normalized_word or not normalized_meaning:
            return None
        return normalized_word, normalize_entry({"meaning": normalized_meaning, "word": normalized_word})

    match = re.match(
        r"^(?P<word>[^\t]+?)\s*\t+\s*(?:(?P<pos>\([^)]+\))\s*)?(?P<meaning>.+)$",
        raw_line,
    )
    if not match:
        return None

    word = normalize_text(match.group("word"))
    meaning = match.group("meaning").strip()
    pos = (match.group("pos") or "").strip()[1:-1]
    if not word or not meaning:
        return None

    return word, normalize_entry({"meaning": meaning, "pos": pos, "word": word})


def import_legacy_txt(
    source_path: str | Path,
    target_path: str | Path | None = None,
) -> dict[str, dict[str, Any]]:
    source = Path(source_path)
    entries: dict[str, dict[str, Any]] = {}

    for line in source.read_text(encoding="utf-8-sig").splitlines():
        parsed = parse_legacy_line(line)
        if parsed is None:
            continue
        word, entry = parsed
        entries[word] = entry

    if target_path is not None:
        return save_dictionary(target_path, entries)
    return entries


def export_dictionary(
    pathlike: str | Path,
    words: dict[str, Any],
    *,
    delimiter: str = ",",
    format_name: str = "table",
) -> None:
    path = Path(pathlike)
    path.parent.mkdir(parents=True, exist_ok=True)

    if format_name == "txt":
        lines: list[str] = []
        for word in sorted(words):
            entry = normalize_entry(words[word])
            meaning = entry["meaning"] or entry["eng_meaning"]
            pos = entry["pos"]
            if pos and meaning:
                lines.append(f"{word}\t({pos}) {meaning}")
            elif meaning:
                lines.append(f"{word}\t{meaning}")
            else:
                lines.append(word)
        path.write_text("\n".join(lines), encoding="utf-8-sig")
        return

    # Excel on Windows reads TSV more reliably as UTF-16 than UTF-8.
    table_encoding = "utf-16" if delimiter == "\t" else "utf-8-sig"

    with path.open("w", encoding=table_encoding, newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=EXPORT_FIELDS, delimiter=delimiter)
        writer.writeheader()

        for word in sorted(words):
            entry = normalize_entry(words[word])
            row = {
                "word": word,
                "meaning": entry["meaning"],
                "phonetic": entry["phonetic"],
                "pos": entry["pos"],
                "example": entry["example"],
                "eng_meaning": entry["eng_meaning"],
                "pragmatics": entry["pragmatics"],
                "level": entry["level"],
                "is_favorite": entry["is_favorite"],
            }
            writer.writerow(row)
