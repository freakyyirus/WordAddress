"""
Multi-Language Wordlist Manager for Open3Words
Manages separate wordlists per language for internationalized 3-word addresses.

Design:
- Each language has its own curated wordlist of equal size.
- Encoding/decoding is language-agnostic (same algorithm, different word table).
- Language-specific homophone and offensive-word filters.
- Supports runtime language switching.

Supported (or planned) languages:
    en - English (default)
    es - Spanish
    fr - French
    de - German
    pt - Portuguese
    ja - Japanese (romaji)
    zh - Chinese (pinyin)
    ar - Arabic (romanized)
    hi - Hindi (romanized)
"""

import json
import os
from typing import Dict, List, Optional, Tuple

from location_encoder import LocationEncoder


class MultiLanguageManager:
    """
    Manages wordlists for multiple languages.
    Each language has its own wordlist JSON file in the data/lang/ directory.
    """

    SUPPORTED_LANGUAGES = {
        "en": {"name": "English",    "native": "English",    "wordlist": "wordlist_en.json"},
        "es": {"name": "Spanish",    "native": "Español",    "wordlist": "wordlist_es.json"},
        "fr": {"name": "French",     "native": "Français",   "wordlist": "wordlist_fr.json"},
        "de": {"name": "German",     "native": "Deutsch",    "wordlist": "wordlist_de.json"},
        "pt": {"name": "Portuguese", "native": "Português",  "wordlist": "wordlist_pt.json"},
        "ja": {"name": "Japanese",   "native": "日本語",      "wordlist": "wordlist_ja.json"},
        "zh": {"name": "Chinese",    "native": "中文",        "wordlist": "wordlist_zh.json"},
        "ar": {"name": "Arabic",     "native": "العربية",     "wordlist": "wordlist_ar.json"},
        "hi": {"name": "Hindi",      "native": "हिन्दी",       "wordlist": "wordlist_hi.json"},
    }

    def __init__(self, data_dir: Optional[str] = None):
        self.data_dir = data_dir or os.path.join(os.path.dirname(__file__), "data", "lang")
        os.makedirs(self.data_dir, exist_ok=True)

        # Cache of loaded encoders per language
        self._encoders: Dict[str, LocationEncoder] = {}

        # Always load English as default/fallback
        self._ensure_english()

    def _ensure_english(self):
        """Ensure the default English wordlist exists (symlink to main wordlist)."""
        en_path = os.path.join(self.data_dir, "wordlist_en.json")
        main_path = os.path.join(os.path.dirname(__file__), "wordlist.json")

        if not os.path.exists(en_path):
            if os.path.exists(main_path):
                # Copy main wordlist as English
                with open(main_path, "r", encoding="utf-8") as f:
                    words = json.load(f)
                with open(en_path, "w", encoding="utf-8") as f:
                    json.dump(words, f)
            else:
                # Generate from scratch
                from wordlist_generator import create_wordlist, save_wordlist
                words = create_wordlist(40000)
                save_wordlist(words, en_path)
                save_wordlist(words, main_path)

    def get_encoder(self, lang: str = "en") -> LocationEncoder:
        """Get (or create) a LocationEncoder for the given language."""
        lang = lang.lower().strip()

        if lang in self._encoders:
            return self._encoders[lang]

        wordlist_path = self._get_wordlist_path(lang)

        if not os.path.exists(wordlist_path):
            if lang == "en":
                self._ensure_english()
            else:
                # For non-English, fall back to English with a warning
                import logging
                logging.getLogger(__name__).warning(
                    f"Wordlist for '{lang}' not found at {wordlist_path}. "
                    f"Falling back to English."
                )
                return self.get_encoder("en")

        encoder = LocationEncoder(wordlist_path=wordlist_path)
        self._encoders[lang] = encoder
        return encoder

    def encode(self, lat: float, lon: float, lang: str = "en") -> str:
        """Encode coordinates using the specified language's wordlist."""
        return self.get_encoder(lang).encode(lat, lon)

    def decode(self, words: str, lang: str = "en") -> Tuple[float, float]:
        """Decode a 3-word address using the specified language's wordlist."""
        return self.get_encoder(lang).decode(words)

    def detect_language(self, words: str) -> Optional[str]:
        """
        Attempt to detect which language a 3-word address belongs to.
        Tries each loaded language's wordlist.
        """
        parts = words.lower().strip().replace("///", "").replace(" ", ".").split(".")
        if len(parts) != 3:
            return None

        # Check each loaded language
        for lang, encoder in self._encoders.items():
            if all(p in encoder.word_to_index for p in parts):
                return lang

        # Try loading all available languages
        for lang_code in self.SUPPORTED_LANGUAGES:
            if lang_code in self._encoders:
                continue
            try:
                enc = self.get_encoder(lang_code)
                if all(p in enc.word_to_index for p in parts):
                    return lang_code
            except Exception:
                continue

        return None

    def list_languages(self) -> List[dict]:
        """Return list of supported languages with availability status."""
        result = []
        for code, info in self.SUPPORTED_LANGUAGES.items():
            path = self._get_wordlist_path(code)
            result.append({
                "code": code,
                "name": info["name"],
                "native_name": info["native"],
                "available": os.path.exists(path),
                "wordlist_path": path,
            })
        return result

    def install_wordlist(self, lang: str, words: List[str]) -> str:
        """Install a wordlist for a new language."""
        lang = lang.lower().strip()
        path = self._get_wordlist_path(lang)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(words, f, ensure_ascii=False)

        # Invalidate cached encoder
        self._encoders.pop(lang, None)
        return path

    def _get_wordlist_path(self, lang: str) -> str:
        """Get the filesystem path for a language's wordlist."""
        info = self.SUPPORTED_LANGUAGES.get(lang)
        filename = info["wordlist"] if info else f"wordlist_{lang}.json"
        return os.path.join(self.data_dir, filename)


# ── Stub word generators for other languages ─────────────────
# These create minimal placeholder wordlists from common words.
# In production, use curated bilingual dictionaries.

SPANISH_COMMON = [
    "agua", "aire", "alto", "amor", "arbol", "barco", "bello", "bien",
    "blanco", "bravo", "bueno", "cafe", "calle", "calma", "campo",
    "carta", "casa", "cielo", "cinco", "claro", "color", "como",
    "coraz", "corto", "costa", "crema", "cueva", "dulce", "este",
    "faro", "feria", "fiesta", "flora", "fuego", "gato", "globo",
    "grano", "gris", "grupo", "hielo", "hoja", "humo", "isla",
    "juego", "lago", "largo", "libro", "libre", "lobo", "loma",
    "luna", "madre", "mango", "marco", "mesa", "miel", "monte",
    "nieve", "noche", "norte", "nube", "nuevo", "ola", "oro",
    "padre", "palma", "pasto", "perla", "piedra", "pino", "plata",
    "playa", "plaza", "primo", "pueblo", "puente", "punto", "rayo",
    "rio", "roca", "rojo", "rosa", "rueda", "sable", "salto",
    "selva", "senda", "sierra", "sol", "sombra", "suave", "tigre",
    "tierra", "torre", "trigo", "vela", "verde", "vida", "viento",
]

FRENCH_COMMON = [
    "abeille", "aigle", "amour", "arbre", "argent", "autel", "bague",
    "balcon", "bleu", "bois", "brave", "brume", "calme", "champ",
    "chant", "clair", "coeur", "colline", "conte", "corde", "danse",
    "douce", "etoile", "fable", "faune", "feuille", "flamme", "fleur",
    "foret", "givre", "globe", "grain", "herbe", "image", "jardin",
    "joie", "laine", "lame", "large", "libre", "loup", "lune",
    "matin", "melon", "merle", "miel", "monde", "montagne", "moulin",
    "neige", "noble", "nuage", "olive", "onde", "ombre", "perle",
    "phare", "plage", "plaine", "plume", "poire", "pomme", "pont",
    "porte", "prairie", "prince", "puits", "reine", "roche", "roseau",
    "route", "sabre", "sable", "sauge", "soleil", "source", "terre",
    "tigre", "toile", "tour", "truite", "vague", "vallon", "vigne",
    "voile", "vent",
]


def generate_stub_wordlist(lang: str, target_size: int = 32768) -> List[str]:
    """
    Create a minimal stub wordlist for a language.
    Uses common seed words + numbered padding.
    For production, replace with curated lists from SCOWL/Wiktionary.
    """
    seeds = {
        "es": SPANISH_COMMON,
        "fr": FRENCH_COMMON,
    }

    base = list(seeds.get(lang, []))
    if not base:
        base = [f"word{i}" for i in range(100)]

    # Pad to target size
    existing = set(base)
    idx = 0
    while len(base) < target_size:
        candidate = f"{base[idx % len(seeds.get(lang, base))]}{idx // 100}" if idx >= 100 else None
        if candidate and candidate not in existing:
            base.append(candidate)
            existing.add(candidate)
        elif not candidate:
            filler = f"w{lang}{idx:05d}"
            base.append(filler)
            existing.add(filler)
        idx += 1

    return base[:target_size]


# ── CLI ──────────────────────────────────────────────────────

if __name__ == "__main__":
    mgr = MultiLanguageManager()
    print("Multi-Language Manager")
    print("=" * 50)
    for lang in mgr.list_languages():
        status = "✓" if lang["available"] else "✗"
        print(f"  [{status}] {lang['code']} - {lang['name']} ({lang['native_name']})")
