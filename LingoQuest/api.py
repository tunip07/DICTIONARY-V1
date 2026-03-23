from __future__ import annotations

import json
import urllib.parse
import urllib.request

from crud import merge_entry
from storage import normalize_text


COMMON_VERB_HEADWORDS = {
    "be",
    "do",
    "get",
    "go",
    "have",
    "make",
    "run",
    "set",
    "take",
}

LOW_PRIORITY_MARKERS = (
    "archaic",
    "dated",
    "informal",
    "obsolete",
    "offensive",
    "rare",
    "slang",
    "vulgar",
)


def _first_non_empty(values):
    for value in values:
        if value:
            return value
    return ""


def _score_dictionaryapi_sense(word: str, pos: str, definition: str, example: str, order: int) -> float:
    normalized_word = normalize_text(word)
    normalized_pos = pos.strip().lower()
    normalized_definition = definition.strip().lower()
    normalized_example = example.strip().lower()
    definition_words = len(normalized_definition.split())

    score = 0.0

    if example:
        score += 2.5
    if 4 <= definition_words <= 14:
        score += 2.0
    elif definition_words > 20:
        score -= 1.0

    if normalized_pos == "verb":
        score += 1.5

    if normalized_word in COMMON_VERB_HEADWORDS:
        if normalized_pos == "verb":
            score += 8.0
        elif normalized_pos == "noun":
            score -= 6.0
        else:
            score -= 2.0

    if any(marker in normalized_definition for marker in LOW_PRIORITY_MARKERS):
        score -= 3.0
    if any(marker in normalized_example for marker in LOW_PRIORITY_MARKERS):
        score -= 1.0

    score -= order * 0.05
    return score


def _select_best_dictionaryapi_sense(entry: dict) -> dict | None:
    headword = entry.get("word", "")
    candidates = []
    order = 0

    for meaning_item in entry.get("meanings", []):
        pos = meaning_item.get("partOfSpeech", "").strip()
        for definition_item in meaning_item.get("definitions", []):
            definition = definition_item.get("definition", "").strip()
            if not definition:
                continue
            example = definition_item.get("example", "").strip()
            synonyms = [item for item in definition_item.get("synonyms", []) if item]
            score = _score_dictionaryapi_sense(headword, pos, definition, example, order)
            candidates.append(
                {
                    "score": score,
                    "definition": definition,
                    "example": example,
                    "pos": pos,
                    "synonyms": synonyms,
                }
            )
            order += 1

    if not candidates:
        return None

    return max(candidates, key=lambda item: item["score"])


def fetch_datamuse_suggestions(query: str, max_results: int = 3, timeout: int = 1) -> list[str]:
    url = f"https://api.datamuse.com/sug?s={urllib.parse.quote(query)}&max={max_results}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return [item["word"] for item in payload if item.get("word")]


def fetch_datamuse_collocations(word: str, timeout: int = 2) -> str:
    try:
        url = f"https://api.datamuse.com/words?rel_jja={urllib.parse.quote(word)}&max=5"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        res = json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8"))
        words = [item["word"] for item in res if item.get("word")]
        if words:
            return "Hay đi kèm với: " + ", ".join(words)

        url2 = f"https://api.datamuse.com/words?rel_bga={urllib.parse.quote(word)}&max=5"
        req2 = urllib.request.Request(url2, headers={"User-Agent": "Mozilla/5.0"})
        res2 = json.loads(urllib.request.urlopen(req2, timeout=timeout).read().decode("utf-8"))
        words2 = [item["word"] for item in res2 if item.get("word")]
        if words2:
            return "Tình huống: " + ", ".join(words2)
    except Exception:
        pass
    return "Đang phân tích ngữ cảnh..."


def translate_to_vietnamese(text: str, timeout: int = 3) -> str:
    if not text:
        return ""
    try:
        url = (
            "https://translate.googleapis.com/translate_a/single"
            f"?client=gtx&sl=en&tl=vi&dt=t&q={urllib.parse.quote(text)}"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
        return "".join(part[0] for part in data[0] if part and part[0]).strip()
    except Exception:
        return ""


def parse_dictionaryapi_payload(payload) -> dict | None:
    if not isinstance(payload, list) or not payload:
        return None

    entry = payload[0]
    phonetic = entry.get("phonetic", "")
    if not phonetic:
        phonetic = _first_non_empty(
            phonetic_item.get("text", "") for phonetic_item in entry.get("phonetics", [])
        )

    best_sense = _select_best_dictionaryapi_sense(entry)
    if not best_sense:
        return None

    meaning = best_sense["definition"]
    pos = best_sense["pos"]
    example = best_sense["example"]
    synonyms = best_sense["synonyms"]

    translated = translate_to_vietnamese(meaning)
    return {
        "meaning": translated or meaning,
        "phonetic": phonetic,
        "pronunciation": phonetic,
        "ipa_uk": phonetic,
        "ipa_us": phonetic,
        "pos": pos,
        "part_of_speech": pos,
        "example": example,
        "eng_meaning": meaning,
        "definitions": [{"definition": meaning, "example": example, "synonyms": synonyms}],
    }


def build_translation_fallback_entry(term: str, translated: str) -> dict | None:
    cleaned_term = normalize_text(term)
    cleaned_translation = translated.strip()
    if not cleaned_term or not cleaned_translation:
        return None

    # Ignore empty/self-translations that are unlikely to help the user.
    if normalize_text(cleaned_translation) == cleaned_term:
        return None

    return {
        "meaning": cleaned_translation,
        "phonetic": "",
        "pronunciation": "",
        "ipa_uk": "",
        "ipa_us": "",
        "pos": "",
        "part_of_speech": "",
        "example": "",
        "eng_meaning": cleaned_term,
        "definitions": [{"definition": cleaned_term, "example": "", "synonyms": []}],
    }


def fetch_dictionary_entry(word: str, timeout: int = 5) -> dict | None:
    url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{urllib.parse.quote(word)}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return None
    return parse_dictionaryapi_payload(payload)


def lookup_remote_word(
    word: str,
    *,
    fetch_entry=fetch_dictionary_entry,
    fetch_suggestions=fetch_datamuse_suggestions,
    fetch_collocations=fetch_datamuse_collocations,
    translate=translate_to_vietnamese,
) -> dict:
    requested_word = normalize_text(word)
    corrected_word = requested_word
    entry = fetch_entry(requested_word) if requested_word else None

    if not entry and requested_word:
        try:
            suggestions = fetch_suggestions(requested_word, max_results=1)
        except Exception:
            suggestions = []

        if suggestions:
            candidate = normalize_text(suggestions[0])
            if candidate and candidate != requested_word:
                corrected_word = candidate
                entry = fetch_entry(corrected_word)

    source = "dictionaryapi"
    if not entry and corrected_word:
        translated = translate(corrected_word)
        entry = build_translation_fallback_entry(corrected_word, translated)
        if entry:
            source = "translate_fallback"

    pragmatics = fetch_collocations(corrected_word) if corrected_word else ""
    return {
        "requested_word": requested_word,
        "word": corrected_word,
        "entry": entry,
        "pragmatics": pragmatics,
        "found": bool(entry),
        "corrected": corrected_word != requested_word,
        "source": source if entry else "",
    }


def fetch_and_cache_word(
    words: dict,
    word: str,
    *,
    fetch_entry=fetch_dictionary_entry,
    fetch_suggestions=fetch_datamuse_suggestions,
    fetch_collocations=fetch_datamuse_collocations,
    translate=translate_to_vietnamese,
) -> dict:
    result = lookup_remote_word(
        word,
        fetch_entry=fetch_entry,
        fetch_suggestions=fetch_suggestions,
        fetch_collocations=fetch_collocations,
        translate=translate,
    )

    return cache_lookup_result(words, result)


def cache_lookup_result(words: dict, result: dict) -> dict:
    if not result.get("found"):
        return result

    corrected_word = result.get("word", "")
    requested_word = result.get("requested_word", "")
    existing = words.get(corrected_word, words.get(requested_word, {}))
    merged = merge_entry(existing, result.get("entry"), pragmatics=result.get("pragmatics", ""))
    words[corrected_word] = merged
    result["cached_entry"] = merged
    return result
