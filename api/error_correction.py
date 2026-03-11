"""
AI-powered Error Correction for Open3Words
Handles typos, homophones, accents, and speech-to-text errors.

Uses multiple correction strategies:
1. Levenshtein (edit) distance
2. Phonetic matching (Double Metaphone)
3. Keyboard proximity
4. Optional LLM-based context correction
"""

import heapq
from typing import List, Dict, Optional, Tuple
from itertools import product

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


# QWERTY keyboard neighbor map for proximity-based correction
KEYBOARD_NEIGHBORS = {
    "q": "wa", "w": "qeas", "e": "wrds", "r": "etfd", "t": "ryfg",
    "y": "tugh", "u": "yijh", "i": "uokj", "o": "iplk", "p": "ol",
    "a": "qwsz", "s": "awedxz", "d": "serfcx", "f": "drtgvc",
    "g": "ftyhbv", "h": "gyujnb", "j": "huikmn", "k": "jiolm",
    "l": "kop", "z": "asx", "x": "zsdc", "c": "xdfv", "v": "cfgb",
    "b": "vghn", "n": "bhjm", "m": "njk",
}


def levenshtein_distance(s1: str, s2: str) -> int:
    """Compute Levenshtein edit distance between two strings."""
    if HAS_JELLYFISH:
        return jellyfish.levenshtein_distance(s1, s2)

    # Fallback pure-Python implementation
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)

    prev_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        for j, c2 in enumerate(s2):
            ins = prev_row[j + 1] + 1
            dele = curr_row[j] + 1
            sub = prev_row[j] + (c1 != c2)
            curr_row.append(min(ins, dele, sub))
        prev_row = curr_row

    return prev_row[-1]


def phonetic_code(word: str) -> Tuple[Optional[str], Optional[str]]:
    """Return Double Metaphone codes for a word."""
    if HAS_METAPHONE:
        return doublemetaphone(word)
    if HAS_JELLYFISH:
        try:
            return jellyfish.metaphone(word), None
        except Exception:
            pass
    return None, None


class ErrorCorrector:
    """
    Multi-layer error correction for 3-word addresses.
    """

    def __init__(self, wordlist: List[str], max_edit_distance: int = 2):
        self.wordlist = wordlist
        self.word_set = set(wordlist)
        self.max_edit_distance = max_edit_distance

        # Build phonetic index
        self.phonetic_index: Dict[str, List[str]] = {}
        for word in wordlist:
            code1, code2 = phonetic_code(word)
            for code in (code1, code2):
                if code:
                    self.phonetic_index.setdefault(code, []).append(word)

        # Build prefix index for fast prefix matching
        self.prefix_index: Dict[str, List[str]] = {}
        for word in wordlist:
            for length in range(1, min(len(word) + 1, 5)):
                prefix = word[:length]
                self.prefix_index.setdefault(prefix, []).append(word)

    def correct_word(self, wrong_word: str, top_k: int = 5) -> List[Dict]:
        """
        Correct a single word. Returns ranked list of suggestions.
        """
        wrong_word = wrong_word.lower().strip()

        # Exact match — no correction needed
        if wrong_word in self.word_set:
            return [{"word": wrong_word, "score": 100, "method": "exact"}]

        candidates = []

        # Strategy 1: Edit distance
        for word in self.wordlist:
            dist = levenshtein_distance(wrong_word, word)
            if dist <= self.max_edit_distance:
                score = 100 - dist * 30
                candidates.append({"word": word, "score": score, "method": "edit_distance", "distance": dist})

        # Strategy 2: Phonetic matching
        code1, code2 = phonetic_code(wrong_word)
        for code in (code1, code2):
            if code and code in self.phonetic_index:
                for word in self.phonetic_index[code]:
                    if word != wrong_word:
                        candidates.append({"word": word, "score": 75, "method": "phonetic"})

        # Strategy 3: Prefix matching
        if len(wrong_word) >= 2:
            prefix = wrong_word[:3]
            if prefix in self.prefix_index:
                for word in self.prefix_index[prefix][:10]:
                    dist = levenshtein_distance(wrong_word, word)
                    if dist <= self.max_edit_distance + 1:
                        candidates.append({"word": word, "score": 60 - dist * 10, "method": "prefix"})

        # Strategy 4: Keyboard proximity
        keyboard_variants = self._keyboard_variants(wrong_word)
        for variant in keyboard_variants:
            if variant in self.word_set:
                candidates.append({"word": variant, "score": 85, "method": "keyboard"})

        # Deduplicate and rank
        seen = set()
        unique = []
        for c in sorted(candidates, key=lambda x: -x["score"]):
            if c["word"] not in seen:
                seen.add(c["word"])
                unique.append(c)
                if len(unique) >= top_k:
                    break

        return unique

    def correct_address(self, address: str, top_k: int = 5) -> List[Dict]:
        """
        Correct a full 3-word address. Returns ranked list of suggested addresses.
        """
        address = address.lower().strip().replace(" ", ".")
        if address.startswith("///"):
            address = address[3:]
        parts = address.split(".")

        if len(parts) != 3:
            return [{"error": f"Expected 3 words, got {len(parts)}"}]

        # Get suggestions for each word
        word_suggestions = []
        for part in parts:
            suggestions = self.correct_word(part, top_k=3)
            if suggestions:
                word_suggestions.append(suggestions)
            else:
                word_suggestions.append([{"word": part, "score": 0, "method": "unknown"}])

        # Generate combinations and score them
        all_combos = []
        for combo in product(*word_suggestions):
            words = ".".join(c["word"] for c in combo)
            total_score = sum(c["score"] for c in combo) / 3
            methods = [c["method"] for c in combo]
            all_combos.append({
                "words": words,
                "score": round(total_score, 1),
                "methods": methods,
                "corrections": [
                    {"original": parts[i], "corrected": combo[i]["word"], "method": combo[i]["method"]}
                    for i in range(3)
                    if parts[i] != combo[i]["word"]
                ],
            })

        # Sort by score descending
        all_combos.sort(key=lambda x: -x["score"])

        # Deduplicate
        seen = set()
        unique = []
        for c in all_combos:
            if c["words"] not in seen:
                seen.add(c["words"])
                unique.append(c)
                if len(unique) >= top_k:
                    break

        return unique

    def _keyboard_variants(self, word: str, max_variants: int = 50) -> List[str]:
        """Generate possible words from keyboard typo corrections."""
        variants = set()

        for i, char in enumerate(word):
            neighbors = KEYBOARD_NEIGHBORS.get(char, "")
            for neighbor in neighbors:
                variant = word[:i] + neighbor + word[i + 1:]
                variants.add(variant)
                if len(variants) >= max_variants:
                    return list(variants)

        return list(variants)

    def suggest_completions(self, prefix: str, limit: int = 10) -> List[str]:
        """
        Suggest word completions for a given prefix.
        Used for autocomplete/autosuggest.
        """
        prefix = prefix.lower().strip()
        if prefix in self.prefix_index:
            return self.prefix_index[prefix][:limit]

        # Fuzzy prefix matching
        results = []
        for word in self.wordlist:
            if word.startswith(prefix):
                results.append(word)
                if len(results) >= limit:
                    break
        return results
