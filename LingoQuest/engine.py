from __future__ import annotations

from collections import defaultdict
from difflib import get_close_matches
import re

from storage import normalize_text


class SearchEngine:
    """Search helper with O(1) exact lookup and prefix-index autocomplete."""

    def __init__(self, words: dict[str, dict] | None = None):
        self.set_words(words or {})

    def set_words(self, words: dict[str, dict]) -> None:
        self._words = {
            normalize_text(word): entry
            for word, entry in words.items()
            if normalize_text(word)
        }
        self._sorted_words = sorted(self._words)
        self._prefix_index: dict[str, list[str]] = defaultdict(list)
        self._meaning_token_index: dict[str, list[str]] = defaultdict(list)
        self._meaning_prefix_index: dict[str, list[str]] = defaultdict(list)

        for word in self._sorted_words:
            for end in range(1, len(word) + 1):
                self._prefix_index[word[:end]].append(word)

            seen_tokens: set[str] = set()
            for token in self._tokenize(str(self._words[word].get("meaning", ""))):
                if token in seen_tokens:
                    continue
                seen_tokens.add(token)
                self._meaning_token_index[token].append(word)
                for end in range(1, len(token) + 1):
                    self._meaning_prefix_index[token[:end]].append(word)

    def all_words(self, limit: int | None = None) -> list[str]:
        return self._slice(self._sorted_words, limit)

    def contains(self, query: str) -> bool:
        return normalize_text(query) in self._words

    def exact_lookup(self, query: str) -> dict | None:
        return self._words.get(normalize_text(query))

    def autocomplete(self, prefix: str, limit: int | None = 5) -> list[str]:
        normalized = normalize_text(prefix)
        if not normalized:
            return []
        return self._bounded_prefix_matches(normalized, limit)

    def meaning_contains(self, query: str, limit: int | None = None) -> list[str]:
        normalized = normalize_text(query)
        if not normalized:
            return []
        tokens = self._tokenize(normalized)
        if not tokens:
            return []

        candidate_lists: list[list[str]] = []
        last_index = len(tokens) - 1

        for index, token in enumerate(tokens):
            if index == last_index:
                matches = self._meaning_token_index.get(token)
                if not matches:
                    matches = self._meaning_prefix_index.get(token, [])
            else:
                matches = self._meaning_token_index.get(token, [])

            if not matches:
                return []
            candidate_lists.append(matches)

        return self._intersect_lists(candidate_lists, limit)

    def fuzzy_suggestions(
        self,
        query: str,
        limit: int | None = 5,
        cutoff: float = 0.72,
    ) -> list[str]:
        normalized = normalize_text(query)
        if len(normalized) < 2 or not self._sorted_words:
            return []
        max_items = len(self._sorted_words) if limit is None else max(limit, 1)
        return get_close_matches(
            normalized,
            self._sorted_words,
            n=max_items,
            cutoff=cutoff,
        )

    def suggestions(self, query: str, limit: int = 5) -> list[str]:
        normalized = normalize_text(query)
        if not normalized:
            return []

        suggestions: list[str] = []
        if self.contains(normalized):
            suggestions.append(normalized)

        for word in self._bounded_prefix_matches(normalized, limit):
            if word not in suggestions:
                suggestions.append(word)
            if len(suggestions) >= limit:
                break

        if suggestions:
            return suggestions

        return self.fuzzy_suggestions(normalized, limit=limit)

    def _bounded_prefix_matches(
        self,
        prefix: str,
        limit: int | None,
    ) -> list[str]:
        matches = self._prefix_index.get(prefix, [])
        if limit is None:
            return list(matches)
        if limit <= 0:
            return []
        return list(matches[:limit])

    @staticmethod
    def _intersect_lists(
        candidate_lists: list[list[str]],
        limit: int | None,
    ) -> list[str]:
        if not candidate_lists:
            return []

        ordered = candidate_lists[0]
        if len(candidate_lists) == 1:
            return SearchEngine._slice(ordered, limit)

        others = [set(items) for items in candidate_lists[1:]]
        results: list[str] = []

        for word in ordered:
            if all(word in items for items in others):
                results.append(word)
                if limit is not None and len(results) >= limit:
                    break

        return results

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return re.findall(r"\w+", normalize_text(text))

    def search(self, query: str, limit: int | None = None) -> list[str]:
        normalized = normalize_text(query)
        if not normalized:
            return self.all_words(limit)

        if self.contains(normalized):
            return [normalized]

        prefix_matches = self.autocomplete(normalized, limit=limit)
        if prefix_matches:
            return prefix_matches

        meaning_matches = self.meaning_contains(normalized, limit=limit)
        if meaning_matches:
            return meaning_matches

        return self.fuzzy_suggestions(normalized, limit=limit)

    @staticmethod
    def _slice(items: list[str], limit: int | None) -> list[str]:
        if limit is None:
            return list(items)
        return list(items[:limit])
