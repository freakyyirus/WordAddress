"""
H3 Hexagonal Encoder for Open3Words
Alternative encoder using Uber's H3 hexagonal grid system.

H3 partitions the globe into hexagonal cells of approximately equal area,
which avoids pole-clumping that plagues rectangular grids. 12 pentagonal
cells exist globally but are negligible.

Usage:
    encoder = H3Encoder()
    words = encoder.encode(51.5074, -0.1278)
    lat, lon = encoder.decode(words)
"""

import json
import math
import os
from typing import Tuple, List, Optional

try:
    import h3
    HAS_H3 = True
except ImportError:
    HAS_H3 = False

from lfsr_scrambler import LFSRScrambler


class H3Encoder:
    """
    Encodes GPS coordinates using H3 hexagonal cells + LFSR scrambling.

    H3 resolutions and approximate edge lengths:
        9  → ~174 m     12 → ~9.4 m
        10 → ~66 m      13 → ~3.6 m
        11 → ~25 m      14 → ~1.3 m
    """

    # Resolution 12 ≈ 9.4 m edge ≈ ~5 m radius (close to W3W's 3m grid)
    DEFAULT_RESOLUTION = 12

    # H3 indices at resolution 12 use roughly 52 bits of entropy
    CELL_BITS = 45

    def __init__(
        self,
        wordlist_path: Optional[str] = None,
        resolution: int = DEFAULT_RESOLUTION,
        cell_bits: int = CELL_BITS,
    ):
        if not HAS_H3:
            raise ImportError(
                "h3 is required for H3Encoder. Install: pip install h3"
            )

        self.resolution = resolution
        self.cell_bits = cell_bits

        # Load wordlist
        if wordlist_path is None:
            wordlist_path = os.path.join(os.path.dirname(__file__), "wordlist.json")

        if not os.path.exists(wordlist_path):
            from wordlist_generator import create_wordlist, save_wordlist
            wordlist = create_wordlist(40000)
            save_wordlist(wordlist, wordlist_path)

        with open(wordlist_path, "r", encoding="utf-8") as f:
            self.wordlist: List[str] = json.load(f)

        self.word_count = len(self.wordlist)
        self.word_to_index = {w: i for i, w in enumerate(self.wordlist)}

        # LFSR scrambler
        self.scrambler = LFSRScrambler(bits=self.cell_bits)

    # ── Public API ────────────────────────────────────────────

    def encode(self, lat: float, lon: float) -> str:
        """Convert GPS coordinates to a 3-word address using H3 hexagons."""
        self._validate_coords(lat, lon)

        # 1. Get H3 hex cell index (returns a hex string like '8928308280fffff')
        h3_index = h3.latlng_to_cell(lat, lon, self.resolution)

        # 2. Convert hex string to integer and extract lower N bits
        h3_int = int(h3_index, 16)
        raw_bits = h3_int & ((1 << self.cell_bits) - 1)

        # 3. Scramble for dispersion
        scrambled = self.scrambler.forward(raw_bits)

        # 4. Map to words
        return self._integer_to_words(scrambled)

    def decode(self, words: str) -> Tuple[float, float]:
        """Convert a 3-word address back to GPS coordinates."""
        words = self._normalize_input(words)

        # 1. Words → integer
        scrambled = self._words_to_integer(words)

        # 2. Reverse LFSR
        raw_bits = self.scrambler.reverse(scrambled)

        # 3. Reconstruct H3 index
        #    We need to try reconstructing the full H3 integer from partial bits
        h3_index = self._reconstruct_h3_index(raw_bits)

        # 4. Get cell center
        lat, lon = h3.cell_to_latlng(h3_index)
        return round(lat, 7), round(lon, 7)

    def get_cell_info(self, lat: float, lon: float) -> dict:
        """Get H3 cell metadata."""
        h3_index = h3.latlng_to_cell(lat, lon, self.resolution)
        lat_c, lon_c = h3.cell_to_latlng(h3_index)
        area = h3.cell_area(h3_index, unit="m^2")
        boundary = h3.cell_to_boundary(h3_index)  # list of (lat, lon)

        return {
            "h3_index": h3_index,
            "resolution": self.resolution,
            "center": {"lat": round(lat_c, 7), "lon": round(lon_c, 7)},
            "area_m2": round(area, 2),
            "is_pentagon": h3.is_pentagon(h3_index),
            "boundary": [{"lat": round(b[0], 7), "lon": round(b[1], 7)} for b in boundary],
        }

    def get_neighbors(self, lat: float, lon: float) -> List[str]:
        """Get word addresses of neighboring hexagonal cells."""
        h3_index = h3.latlng_to_cell(lat, lon, self.resolution)
        ring = h3.grid_ring(h3_index, 1)  # immediate neighbors

        result = []
        for neighbor in ring:
            n_int = int(neighbor, 16)
            raw_bits = n_int & ((1 << self.cell_bits) - 1)
            scrambled = self.scrambler.forward(raw_bits)
            result.append(self._integer_to_words(scrambled))

        return result

    def get_hex_boundary(self, lat: float, lon: float) -> List[dict]:
        """Get hex cell boundary as GeoJSON-compatible coordinate list."""
        h3_index = h3.latlng_to_cell(lat, lon, self.resolution)
        boundary = h3.cell_to_boundary(h3_index)
        return [{"lat": round(b[0], 7), "lon": round(b[1], 7)} for b in boundary]

    # ── Internals ─────────────────────────────────────────────

    def _reconstruct_h3_index(self, raw_bits: int) -> str:
        """Reconstruct H3 hex string from lower bits."""
        # H3 index structure: mode(4) | res(4) | base_cell(7) | child_digits(3*res)
        # We try resolution-specific header bits
        # For resolution 12: header is typically 0x8C (mode=1, res=12)
        header = (0x08 << 56) | (self.resolution << 52)
        candidate = header | raw_bits

        # Validate and return
        hex_str = hex(candidate)[2:]
        try:
            if h3.is_valid_cell(hex_str):
                return hex_str
        except Exception:
            pass

        # Brute-force through base cells (0-121)
        for base_cell in range(122):
            candidate = header | (base_cell << (3 * self.resolution)) | raw_bits
            hex_str = hex(candidate)[2:]
            try:
                if h3.is_valid_cell(hex_str):
                    return hex_str
            except Exception:
                continue

        # Last resort: just use the raw number directly
        return hex(header | raw_bits)[2:]

    def _integer_to_words(self, n: int) -> str:
        n = n % (self.word_count ** 3)
        idx1 = n % self.word_count
        idx2 = (n // self.word_count) % self.word_count
        idx3 = (n // (self.word_count ** 2)) % self.word_count
        return f"{self.wordlist[idx1]}.{self.wordlist[idx2]}.{self.wordlist[idx3]}"

    def _words_to_integer(self, words: str) -> int:
        parts = words.split(".")
        if len(parts) != 3:
            raise ValueError(f"Expected 3 dot-separated words, got: '{words}'")
        indices = []
        for part in parts:
            idx = self.word_to_index.get(part)
            if idx is None:
                raise ValueError(f"Unknown word: '{part}'")
            indices.append(idx)
        return indices[0] + indices[1] * self.word_count + indices[2] * self.word_count ** 2

    @staticmethod
    def _validate_coords(lat: float, lon: float):
        if not (-90 <= lat <= 90):
            raise ValueError(f"Latitude must be between -90 and 90, got {lat}")
        if not (-180 <= lon <= 180):
            raise ValueError(f"Longitude must be between -180 and 180, got {lon}")

    @staticmethod
    def _normalize_input(words: str) -> str:
        words = words.lower().strip().replace(" ", ".")
        if words.startswith("///"):
            words = words[3:]
        return words


# ── CLI ──────────────────────────────────────────────────────

if __name__ == "__main__":
    if not HAS_H3:
        print("h3 not installed. Run: pip install h3")
    else:
        enc = H3Encoder()
        tests = [
            ("London",   51.5074, -0.1278),
            ("NYC",      40.7128, -74.0060),
            ("Tokyo",    35.6762,  139.6503),
            ("Sydney",  -33.8688,  151.2093),
        ]
        for name, lat, lon in tests:
            words = enc.encode(lat, lon)
            info = enc.get_cell_info(lat, lon)
            print(f"{name:12} → ///{words}  (H3={info['h3_index']}, area={info['area_m2']:.0f}m²)")
