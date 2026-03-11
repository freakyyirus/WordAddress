"""
SCOWL / Corpus-Based Wordlist Generator for Open3Words
Generates wordlists from public-domain word corpora.

Supports:
- SCOWL (Spell Checker Oriented Word Lists) — http://wordlist.aspell.net/
- WordNet lemmas
- Custom frequency-filtered lists
- Homophone filtering, offensive word filtering, length constraints

This is an ALTERNATIVE to the hand-curated wordlist_generator.py.
Both can coexist; the multi_language.py module selects which to use.
"""

import os
import json
import re
import string
from typing import List, Set, Optional

try:
    import urllib.request
    HAS_URLLIB = True
except ImportError:
    HAS_URLLIB = False


# ── Known homophones to exclude (English) ────────────────────

ENGLISH_HOMOPHONES = {
    "knight", "night", "write", "right", "rite", "wright",
    "know", "no", "new", "knew", "gnu",
    "hear", "here", "there", "their", "they're",
    "to", "too", "two", "for", "four", "fore",
    "where", "wear", "ware", "pair", "pare", "pear",
    "bear", "bare", "sea", "see", "son", "sun",
    "one", "won", "which", "witch", "be", "bee",
    "bye", "buy", "by", "flour", "flower",
    "steal", "steel", "tail", "tale",
    "wait", "weight", "waste", "waist",
    "weak", "week", "would", "wood",
    "your", "you're", "its", "it's",
    "rain", "reign", "rein",
    "plain", "plane", "break", "brake",
    "knot", "not", "cell", "sell",
    "dear", "deer", "die", "dye",
    "feat", "feet", "fir", "fur",
    "grate", "great", "hall", "haul",
    "hole", "whole", "hour", "our",
    "led", "lead", "mail", "male",
    "meat", "meet", "peace", "piece",
    "role", "roll", "root", "route",
    "scene", "seen", "some", "sum",
    "stair", "stare", "threw", "through",
}

# Words that are offensive, vulgar, or easily confused
BANNED_PATTERNS = [
    r"\b(ass|damn|hell|shit|fuck|crap|dick|bitch|slut|whore|piss|cock|cunt|bastard)\b",
    r"\b(kill|die|dead|murder|rape|slave|nazi|terror)\b",
]

BANNED_REGEX = re.compile("|".join(BANNED_PATTERNS), re.IGNORECASE)


class SCOWLWordlistGenerator:
    """Generate curated wordlists from SCOWL or other public corpora."""

    # SCOWL word list sizes (1-10, 20, 35, 50, 55, 60, 70, 80, 95)
    # Lower numbers = more common words
    SCOWL_LEVELS = [10, 20, 35, 50]

    def __init__(
        self,
        min_length: int = 3,
        max_length: int = 10,
        target_size: int = 32768,  # 2^15 for 15-bit word indices
    ):
        self.min_length = min_length
        self.max_length = max_length
        self.target_size = target_size

    def generate_from_file(self, filepath: str) -> List[str]:
        """
        Generate a filtered wordlist from a local text file (one word per line).
        Works with SCOWL, /usr/share/dict/words, or any word list.
        """
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            raw = {line.strip().lower() for line in f if line.strip()}

        return self._filter_and_select(raw)

    def generate_from_builtin(self) -> List[str]:
        """
        Generate a wordlist from Python's built-in word sources.
        Falls back to a synthetic list if no corpus is available.
        """
        words: Set[str] = set()

        # Try NLTK words corpus
        try:
            import nltk
            try:
                from nltk.corpus import words as nltk_words
                words.update(w.lower() for w in nltk_words.words())
            except LookupError:
                nltk.download("words", quiet=True)
                from nltk.corpus import words as nltk_words
                words.update(w.lower() for w in nltk_words.words())
        except ImportError:
            pass

        # Try WordNet lemmas
        try:
            from nltk.corpus import wordnet
            words.update(
                lemma.name().lower().replace("_", "")
                for synset in wordnet.all_synsets()
                for lemma in synset.lemmas()
                if "_" not in lemma.name()
            )
        except Exception:
            pass

        # Try system dictionary (Linux/macOS)
        for dict_path in ["/usr/share/dict/words", "/usr/share/dict/american-english"]:
            if os.path.exists(dict_path):
                with open(dict_path, "r", encoding="utf-8", errors="ignore") as f:
                    words.update(line.strip().lower() for line in f if line.strip())

        if not words:
            # Ultimate fallback: use the curated generator
            from wordlist_generator import create_wordlist
            return create_wordlist(self.target_size)

        return self._filter_and_select(words)

    def generate_from_url(self, url: str) -> List[str]:
        """Download a word list from a URL and filter it."""
        if not HAS_URLLIB:
            raise RuntimeError("urllib not available")

        req = urllib.request.Request(url, headers={"User-Agent": "Open3Words/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw_text = resp.read().decode("utf-8", errors="ignore")

        words = {line.strip().lower() for line in raw_text.splitlines() if line.strip()}
        return self._filter_and_select(words)

    def _filter_and_select(self, raw_words: Set[str]) -> List[str]:
        """Apply all filters and select target_size words."""
        filtered = []

        for word in sorted(raw_words):
            # Length filter
            if len(word) < self.min_length or len(word) > self.max_length:
                continue

            # Alpha only (no hyphens, apostrophes, digits)
            if not word.isalpha():
                continue

            # ASCII only (no accented characters)
            if not all(c in string.ascii_lowercase for c in word):
                continue

            # Homophone filter
            if word in ENGLISH_HOMOPHONES:
                continue

            # Offensive / banned word filter
            if BANNED_REGEX.match(word):
                continue

            # No plurals ending in 's' if singular form also present
            # (We'll do a second pass for this)
            filtered.append(word)

        # Remove plurals where singular exists
        word_set = set(filtered)
        deduped = []
        for word in filtered:
            if word.endswith("s") and word[:-1] in word_set:
                continue  # Skip plural
            if word.endswith("es") and word[:-2] in word_set:
                continue
            deduped.append(word)

        # Sort by length (prefer shorter, more memorable words) then alphabetically
        deduped.sort(key=lambda w: (len(w), w))

        # Trim or pad to target size
        if len(deduped) >= self.target_size:
            return deduped[: self.target_size]
        else:
            # Pad with compound words from the curated generator
            try:
                from wordlist_generator import create_wordlist
                fallback = create_wordlist(self.target_size - len(deduped))
                existing = set(deduped)
                for w in fallback:
                    if w not in existing:
                        deduped.append(w)
                        existing.add(w)
                    if len(deduped) >= self.target_size:
                        break
            except Exception:
                pass
            return deduped[: self.target_size]

    def save(self, words: List[str], filepath: str):
        """Save wordlist as JSON."""
        os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(words, f, ensure_ascii=False, indent=None)

    def load(self, filepath: str) -> List[str]:
        """Load a saved wordlist."""
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)


# ── Convenience function ─────────────────────────────────────

def generate_scowl_wordlist(
    target_size: int = 32768,
    output_path: Optional[str] = None,
) -> List[str]:
    """
    One-shot function to generate a SCOWL-quality wordlist.
    Tries built-in sources, falls back to curated list.
    """
    gen = SCOWLWordlistGenerator(target_size=target_size)
    words = gen.generate_from_builtin()

    if output_path:
        gen.save(words, output_path)

    return words


# ── CLI ──────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate Open3Words wordlist from corpus")
    parser.add_argument("--size", type=int, default=32768, help="Target wordlist size (default: 32768)")
    parser.add_argument("--input", type=str, help="Input word file (one word per line)")
    parser.add_argument("--output", type=str, default="wordlist_scowl.json", help="Output JSON path")
    parser.add_argument("--min-length", type=int, default=3)
    parser.add_argument("--max-length", type=int, default=10)
    args = parser.parse_args()

    gen = SCOWLWordlistGenerator(
        min_length=args.min_length,
        max_length=args.max_length,
        target_size=args.size,
    )

    if args.input:
        words = gen.generate_from_file(args.input)
    else:
        words = gen.generate_from_builtin()

    gen.save(words, args.output)
    print(f"Generated {len(words)} words → {args.output}")
    print(f"Sample (first 20): {words[:20]}")
