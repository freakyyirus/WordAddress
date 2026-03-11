"""
Enhanced Fuzzy Search Module for Open3Words
Provides multiple strategies for fuzzy word matching and autocomplete.

Strategies:
1. Trie-based prefix matching (fast autocomplete)
2. BK-Tree for edit distance queries
3. Phonetic indexing (Double Metaphone + Soundex)
4. N-gram similarity (trigram overlap)
5. Whoosh full-text search integration (optional)
6. SQLite FTS5 integration (optional)

This module SUPPLEMENTS the existing error_correction.py without replacing it.
"""

import math
from typing import List, Dict, Optional, Tuple, Set
from collections import defaultdict

try:
    import jellyfish
    HAS_JELLYFISH = True
except ImportError:
    HAS_JELLYFISH = False

try:
    from metaphone import doublemetaphone
    HAS_METAPHONE = True
except ImportError:
    HAS_METAPHONE = False


# ─────────────────────────────────────────────────────────────
# Trie for fast prefix matching
# ─────────────────────────────────────────────────────────────

class TrieNode:
    __slots__ = ("children", "is_end", "word")
    def __init__(self):
        self.children: Dict[str, "TrieNode"] = {}
        self.is_end = False
        self.word: Optional[str] = None


class Trie:
    """Prefix tree for ultra-fast autocomplete on word lists."""

    def __init__(self):
        self.root = TrieNode()

    def insert(self, word: str):
        node = self.root
        for ch in word:
            if ch not in node.children:
                node.children[ch] = TrieNode()
            node = node.children[ch]
        node.is_end = True
        node.word = word

    def search_prefix(self, prefix: str, limit: int = 10) -> List[str]:
        """Find all words starting with the given prefix."""
        node = self.root
        for ch in prefix:
            if ch not in node.children:
                return []
            node = node.children[ch]

        results = []
        self._collect(node, results, limit)
        return results

    def _collect(self, node: TrieNode, results: List[str], limit: int):
        if len(results) >= limit:
            return
        if node.is_end and node.word:
            results.append(node.word)
        for ch in sorted(node.children):
            if len(results) >= limit:
                return
            self._collect(node.children[ch], results, limit)

    def contains(self, word: str) -> bool:
        node = self.root
        for ch in word:
            if ch not in node.children:
                return False
            node = node.children[ch]
        return node.is_end


# ─────────────────────────────────────────────────────────────
# BK-Tree for edit distance queries
# ─────────────────────────────────────────────────────────────

def _edit_distance(a: str, b: str) -> int:
    if HAS_JELLYFISH:
        return jellyfish.levenshtein_distance(a, b)
    # Fallback
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a):
        curr = [i + 1]
        for j, cb in enumerate(b):
            curr.append(min(prev[j + 1] + 1, curr[j] + 1, prev[j] + (ca != cb)))
        prev = curr
    return prev[-1]


class BKTreeNode:
    __slots__ = ("word", "children")
    def __init__(self, word: str):
        self.word = word
        self.children: Dict[int, "BKTreeNode"] = {}


class BKTree:
    """BK-Tree for efficient approximate string matching."""

    def __init__(self):
        self.root: Optional[BKTreeNode] = None

    def insert(self, word: str):
        if self.root is None:
            self.root = BKTreeNode(word)
            return
        node = self.root
        d = _edit_distance(word, node.word)
        while d in node.children:
            node = node.children[d]
            d = _edit_distance(word, node.word)
        node.children[d] = BKTreeNode(word)

    def query(self, word: str, max_distance: int = 2) -> List[Tuple[str, int]]:
        """Find all words within max_distance edits."""
        if self.root is None:
            return []

        results = []
        stack = [self.root]
        while stack:
            node = stack.pop()
            d = _edit_distance(word, node.word)
            if d <= max_distance:
                results.append((node.word, d))
            # Only explore children within distance range
            for dist, child in node.children.items():
                if d - max_distance <= dist <= d + max_distance:
                    stack.append(child)

        results.sort(key=lambda x: x[1])
        return results


# ─────────────────────────────────────────────────────────────
# N-gram (Trigram) Similarity
# ─────────────────────────────────────────────────────────────

class TrigramIndex:
    """Index words by their character trigrams for similarity search."""

    def __init__(self):
        self._index: Dict[str, Set[str]] = defaultdict(set)
        self._words: Set[str] = set()

    def add(self, word: str):
        self._words.add(word)
        for trigram in self._trigrams(word):
            self._index[trigram].add(word)

    def search(self, query: str, limit: int = 10, threshold: float = 0.3) -> List[Tuple[str, float]]:
        """Find words with trigram similarity above threshold."""
        query_trigrams = set(self._trigrams(query))
        if not query_trigrams:
            return []

        candidates: Dict[str, int] = defaultdict(int)
        for tri in query_trigrams:
            for word in self._index.get(tri, []):
                candidates[word] += 1

        results = []
        for word, overlap in candidates.items():
            word_trigrams = set(self._trigrams(word))
            sim = overlap / len(query_trigrams | word_trigrams)
            if sim >= threshold:
                results.append((word, round(sim, 3)))

        results.sort(key=lambda x: -x[1])
        return results[:limit]

    @staticmethod
    def _trigrams(word: str) -> List[str]:
        padded = f"  {word} "
        return [padded[i:i + 3] for i in range(len(padded) - 2)]


# ─────────────────────────────────────────────────────────────
# Phonetic Index
# ─────────────────────────────────────────────────────────────

class PhoneticIndex:
    """Index words by their phonetic representation."""

    def __init__(self):
        self._metaphone_index: Dict[str, List[str]] = defaultdict(list)
        self._soundex_index: Dict[str, List[str]] = defaultdict(list)

    def add(self, word: str):
        if HAS_METAPHONE:
            primary, secondary = doublemetaphone(word)
            if primary:
                self._metaphone_index[primary].append(word)
            if secondary:
                self._metaphone_index[secondary].append(word)

        if HAS_JELLYFISH:
            sx = jellyfish.soundex(word)
            self._soundex_index[sx].append(word)

    def find_similar(self, query: str, limit: int = 10) -> List[str]:
        """Find phonetically similar words."""
        candidates = set()

        if HAS_METAPHONE:
            primary, secondary = doublemetaphone(query)
            if primary and primary in self._metaphone_index:
                candidates.update(self._metaphone_index[primary])
            if secondary and secondary in self._metaphone_index:
                candidates.update(self._metaphone_index[secondary])

        if HAS_JELLYFISH:
            sx = jellyfish.soundex(query)
            if sx in self._soundex_index:
                candidates.update(self._soundex_index[sx])

        # Sort by edit distance to the query
        ranked = sorted(candidates, key=lambda w: _edit_distance(query, w))
        return ranked[:limit]


# ─────────────────────────────────────────────────────────────
# Combined Fuzzy Search Engine
# ─────────────────────────────────────────────────────────────

class FuzzySearchEngine:
    """
    Combined fuzzy search using all available strategies.
    Call build() with the wordlist, then use search() for queries.
    """

    def __init__(self, wordlist: List[str]):
        self.wordlist = wordlist
        self.word_set = set(wordlist)

        # Build all indices
        self.trie = Trie()
        self.bk_tree = BKTree()
        self.trigram_index = TrigramIndex()
        self.phonetic_index = PhoneticIndex()

        for word in wordlist:
            self.trie.insert(word)
            self.bk_tree.insert(word)
            self.trigram_index.add(word)
            self.phonetic_index.add(word)

    def autocomplete(self, prefix: str, limit: int = 10) -> List[str]:
        """Fast prefix-based completion using Trie."""
        return self.trie.search_prefix(prefix.lower(), limit)

    def fuzzy_match(self, query: str, max_distance: int = 2, limit: int = 10) -> List[Dict]:
        """
        Multi-strategy fuzzy match combining all indexes.
        Returns ranked results with scores.
        """
        query = query.lower().strip()

        # Exact match
        if query in self.word_set:
            return [{"word": query, "score": 100, "distance": 0, "method": "exact"}]

        seen = {}

        # 1. BK-Tree (edit distance)
        for word, dist in self.bk_tree.query(query, max_distance):
            score = max(0, 100 - dist * 30)
            if word not in seen or seen[word]["score"] < score:
                seen[word] = {"word": word, "score": score, "distance": dist, "method": "edit_distance"}

        # 2. Trigram similarity
        for word, sim in self.trigram_index.search(query, limit * 2, threshold=0.2):
            score = int(sim * 100)
            if word not in seen or seen[word]["score"] < score:
                seen[word] = {"word": word, "score": score, "distance": _edit_distance(query, word), "method": "trigram"}

        # 3. Phonetic
        for word in self.phonetic_index.find_similar(query, limit * 2):
            dist = _edit_distance(query, word)
            score = max(0, 90 - dist * 20)
            if word not in seen or seen[word]["score"] < score:
                seen[word] = {"word": word, "score": score, "distance": dist, "method": "phonetic"}

        # 4. Prefix fallback
        if len(seen) < limit:
            for word in self.trie.search_prefix(query[:3], limit):
                if word not in seen:
                    dist = _edit_distance(query, word)
                    seen[word] = {"word": word, "score": max(0, 60 - dist * 15), "distance": dist, "method": "prefix"}

        results = sorted(seen.values(), key=lambda x: (-x["score"], x["distance"]))
        return results[:limit]

    def suggest_for_address(self, address: str, limit: int = 5) -> List[Dict]:
        """
        Suggest corrections for a complete 3-word address.
        Returns ranked address suggestions with aggregate scores.
        """
        parts = address.lower().strip().replace("///", "").split(".")
        if len(parts) != 3:
            return []

        word_suggestions = [self.fuzzy_match(p, max_distance=2, limit=5) for p in parts]

        results = []
        for s1 in word_suggestions[0][:3]:
            for s2 in word_suggestions[1][:3]:
                for s3 in word_suggestions[2][:3]:
                    avg_score = (s1["score"] + s2["score"] + s3["score"]) // 3
                    corrections = []
                    if s1["word"] != parts[0]:
                        corrections.append({"from": parts[0], "to": s1["word"]})
                    if s2["word"] != parts[1]:
                        corrections.append({"from": parts[1], "to": s2["word"]})
                    if s3["word"] != parts[2]:
                        corrections.append({"from": parts[2], "to": s3["word"]})

                    results.append({
                        "words": f"{s1['word']}.{s2['word']}.{s3['word']}",
                        "score": avg_score,
                        "corrections": corrections,
                    })
                    if len(results) >= limit * 3:
                        break
                if len(results) >= limit * 3:
                    break
            if len(results) >= limit * 3:
                break

        results.sort(key=lambda x: -x["score"])
        return results[:limit]


# ── CLI ──────────────────────────────────────────────────────

if __name__ == "__main__":
    # Demo with a small word list
    sample = ["table", "tower", "tiger", "timber", "tumble",
              "chair", "charm", "chain", "change", "chance",
              "lamp", "lake", "land", "large", "laser"]

    engine = FuzzySearchEngine(sample)

    print("Autocomplete 'ta':", engine.autocomplete("ta"))
    print("Fuzzy 'tabel':", engine.fuzzy_match("tabel"))
    print("Fuzzy 'chiar':", engine.fuzzy_match("chiar"))
    print("Address suggest 'tabel.chiar.lmpa':", engine.suggest_for_address("tabel.chiar.lmpa"))
