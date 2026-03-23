from __future__ import annotations

from datetime import date
import random


def _word_items(words: dict) -> list[tuple[str, dict]]:
    return [(word, data) for word, data in words.items() if isinstance(data, dict)]


def build_multiple_choice_question(words: dict) -> dict | None:
    items = _word_items(words)
    if len(items) < 4:
        return None

    answer_word, answer_data = random.choice(items)
    wrong_choices: list[str] = []

    while len(wrong_choices) < 3:
        word, data = random.choice(items)
        meaning = data.get("meaning", "")
        if word != answer_word and meaning and meaning not in wrong_choices:
            wrong_choices.append(meaning)

    options = wrong_choices + [answer_data.get("meaning", "")]
    random.shuffle(options)
    return {
        "word": answer_word,
        "phonetic": answer_data.get("phonetic", ""),
        "answer": answer_data.get("meaning", ""),
        "options": options,
    }


def build_scramble_round(words: dict) -> dict | None:
    items = [(word, data) for word, data in _word_items(words) if len(word) > 2]
    if not items:
        return None
    word, data = random.choice(items)
    letters = list(word)
    while "".join(letters) == word:
        random.shuffle(letters)
    return {"word": word, "scrambled": "".join(letters), "meaning": data.get("meaning", "")}


def build_reverse_round(words: dict) -> dict | None:
    items = [item for item in _word_items(words) if item[1].get("meaning")]
    if len(items) < 4:
        return None

    answer_word, answer_data = random.choice(items)
    wrong_choices: list[str] = []
    while len(wrong_choices) < 3:
        word, _ = random.choice(items)
        if word != answer_word and word not in wrong_choices:
            wrong_choices.append(word)

    options = wrong_choices + [answer_word]
    random.shuffle(options)
    return {
        "meaning": answer_data.get("meaning", ""),
        "answer": answer_word,
        "options": options,
    }


def build_hangman_round(words: dict) -> dict | None:
    items = [
        (word, data)
        for word, data in _word_items(words)
        if " " not in word and "-" not in word and len(word) >= 3
    ]
    if not items:
        return None
    word, data = random.choice(items)
    return {"word": word, "meaning": data.get("meaning", "")}


def build_flashcard_round(words: dict) -> dict | None:
    items = [item for item in _word_items(words) if item[1].get("meaning")]
    if not items:
        return None

    word, data = random.choice(items)
    return {
        "word": word,
        "meaning": data.get("meaning", ""),
        "phonetic": data.get("phonetic", ""),
        "example": data.get("example", ""),
        "level": data.get("level", ""),
    }


def build_matching_round(words: dict, pair_count: int = 4) -> dict | None:
    items = [item for item in _word_items(words) if item[1].get("meaning")]
    if len(items) < pair_count:
        return None

    selected = random.sample(items, pair_count)
    pairs = [
        {"id": index, "word": word, "meaning": data.get("meaning", "")}
        for index, (word, data) in enumerate(selected, start=1)
    ]
    left = pairs[:]
    right = pairs[:]
    random.shuffle(left)
    random.shuffle(right)
    return {"pairs": pairs, "left": left, "right": right}


def build_daily_challenge(words: dict, day: date | None = None, size: int = 3) -> list[dict]:
    items = [item for item in _word_items(words) if item[1].get("meaning")]
    if len(items) < max(size, 4):
        return []

    challenge_day = day or date.today()
    rng = random.Random(challenge_day.toordinal())
    selected = rng.sample(items, size)
    questions: list[dict] = []

    for answer_word, answer_data in selected:
        wrong_choices: list[str] = []
        while len(wrong_choices) < 3:
            word, data = rng.choice(items)
            meaning = data.get("meaning", "")
            if word != answer_word and meaning and meaning not in wrong_choices:
                wrong_choices.append(meaning)

        options = wrong_choices + [answer_data.get("meaning", "")]
        rng.shuffle(options)
        questions.append(
            {
                "word": answer_word,
                "answer": answer_data.get("meaning", ""),
                "options": options,
                "phonetic": answer_data.get("phonetic", ""),
            }
        )

    return questions


def crossword_candidates(words: dict) -> list[tuple[str, str]]:
    valid_words = []
    for word, data in _word_items(words):
        clean_word = word.lower()
        meaning = data.get("meaning", "")
        if " " in clean_word or "-" in clean_word:
            continue
        if not (3 <= len(clean_word) <= 12):
            continue
        if not meaning or "(Chưa rõ nghĩa)" in meaning:
            continue
        valid_words.append((clean_word, meaning))

    random.shuffle(valid_words)
    return sorted(valid_words[:30], key=lambda item: len(item[0]), reverse=True)
