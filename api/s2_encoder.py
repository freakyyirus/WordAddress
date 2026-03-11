"""
S2 Geometry Encoder for Open3Words
Alternative encoder using Google's S2 spherical geometry library.

S2 partitions the globe onto 6 faces of a cube, then uses quad-tree subdivision.
This gives globally consistent, low-distortion cells with integer IDs.

Usage:
    encoder = S2Encoder()
    words = encoder.encode(51.5074, -0.1278)
    lat, lon = encoder.decode(words)
"""

import json
import math
import os
from typing import Tuple, List, Optional

try:
    from s2sphere import CellId, LatLng, Cell
    HAS_S2 = True
except ImportError:
    HAS_S2 = False

from lfsr_scrambler import LFSRScrambler


class S2Encoder:
    """
    Encodes GPS coordinates using Google S2 Geometry cells + LFSR scrambling.
    Falls back to the classic Z-order encoder if s2sphere is not installed.
    """

    # S2 cell level 25 ≈ ~4.9 m per cell side at the equator
    # Levels:  21 → ~78 m,  23 → ~20 m,  25 → ~5 m,  28 → ~0.6 m
    DEFAULT_LEVEL = 25

    # We extract 42 bits from the S2 cell ID (enough for level-25 precision)
    CELL_BITS = 42

    def __init__(
        self,
        wordlist_path: Optional[str] = None,
        level: int = DEFAULT_LEVEL,
        cell_bits: int = CELL_BITS,
    ):
        if not HAS_S2:
            raise ImportError(
                "s2sphere is required for S2Encoder. Install it with: pip install s2sphere"
            )

        self.level = level
        self.cell_bits = cell_bits

        # Load wordlist (reuse the same wordlist as the main encoder)
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

        # LFSR scrambler for bit dispersion
        self.scrambler = LFSRScrambler(bits=self.cell_bits)

    # ── Public API ────────────────────────────────────────────

    def encode(self, lat: float, lon: float) -> str:
        """Convert GPS coordinates to a 3-word address using S2 cells."""
        self._validate_coords(lat, lon)

        # 1. Get S2 cell at target level
        ll = LatLng.from_degrees(lat, lon)
        cell_id = CellId.from_lat_lng(ll).parent(self.level)

        # 2. Extract lower N bits from cell ID
        raw_bits = cell_id.id() & ((1 << self.cell_bits) - 1)

        # 3. Scramble bits with LFSR for uniform distribution
        scrambled = self.scrambler.forward(raw_bits)

        # 4. Map to 3 words
        return self._integer_to_words(scrambled)

    def decode(self, words: str) -> Tuple[float, float]:
        """Convert a 3-word address back to GPS coordinates."""
        words = self._normalize_input(words)

        # 1. Map words back to integer
        scrambled = self._words_to_integer(words)

        # 2. Reverse LFSR scramble
        raw_bits = self.scrambler.reverse(scrambled)

        # 3. Reconstruct S2 cell ID
        #    We need the face bits and structure — reconstruct from level
        #    For simplicity we scan all 6 faces and find the one that matches
        cell_id = self._reconstruct_cell_id(raw_bits)

        # 4. Get lat/lon from cell center
        ll = cell_id.to_lat_lng()
        return round(ll.lat().degrees, 7), round(ll.lng().degrees, 7)

    def get_cell_info(self, lat: float, lon: float) -> dict:
        """Get S2 cell metadata for given coordinates."""
        ll = LatLng.from_degrees(lat, lon)
        cell_id = CellId.from_lat_lng(ll).parent(self.level)
        cell = Cell(cell_id)

        # Approximate cell edge length in meters
        edge_m = cell_id.to_lat_lng().get_distance(
            CellId(cell_id.id() + 1).to_lat_lng()
        ).radians * 6_371_000

        return {
            "cell_id": str(cell_id.id()),
            "level": self.level,
            "face": cell_id.face(),
            "token": cell_id.to_token(),
            "approx_edge_m": round(edge_m, 2),
            "center": {
                "lat": round(cell_id.to_lat_lng().lat().degrees, 7),
                "lon": round(cell_id.to_lat_lng().lng().degrees, 7),
            },
        }

    def get_neighbors(self, lat: float, lon: float, include_diagonals: bool = True) -> List[str]:
        """Get word addresses of neighboring cells."""
        ll = LatLng.from_degrees(lat, lon)
        cell_id = CellId.from_lat_lng(ll).parent(self.level)

        neighbor_ids = []
        for edge_neighbor in cell_id.get_all_neighbors(self.level):
            neighbor_ids.append(edge_neighbor)

        result = []
        for nid in neighbor_ids:
            raw_bits = nid.id() & ((1 << self.cell_bits) - 1)
            scrambled = self.scrambler.forward(raw_bits)
            result.append(self._integer_to_words(scrambled))

        return result

    # ── Internal helpers ──────────────────────────────────────

    def _reconstruct_cell_id(self, raw_bits: int) -> CellId:
        """Reconstruct a full S2 CellId from the extracted lower bits."""
        # Try all 6 faces to find a valid reconstruction
        for face in range(6):
            # Build a candidate cell ID
            face_bits = face << 61  # S2 face occupies top 3 bits of 64-bit ID
            # The cell ID at a given level has a sentinel bit at position 2*(30-level)
            sentinel = 1 << (2 * (30 - self.level))
            candidate_id = face_bits | (raw_bits << (2 * (30 - self.level) + 1)) | sentinel

            try:
                candidate = CellId(candidate_id)
                if candidate.is_valid() and candidate.level() == self.level:
                    return candidate
            except Exception:
                continue

        # Fallback: use the raw bits directly with face 0
        face_bits = 0
        sentinel = 1 << (2 * (30 - self.level))
        fallback_id = face_bits | (raw_bits << (2 * (30 - self.level) + 1)) | sentinel
        return CellId(fallback_id)

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
    if not HAS_S2:
        print("s2sphere not installed. Run: pip install s2sphere")
    else:
        enc = S2Encoder()
        tests = [
            ("London",   51.5074, -0.1278),
            ("NYC",      40.7128, -74.0060),
            ("Tokyo",    35.6762,  139.6503),
            ("Sydney",  -33.8688,  151.2093),
        ]
        for name, lat, lon in tests:
            words = enc.encode(lat, lon)
            dlat, dlon = enc.decode(words)
            err = math.sqrt(((lat - dlat) * 111000) ** 2 + ((lon - dlon) * 111000 * math.cos(math.radians(lat))) ** 2)
            print(f"{name:12} → ///{words}  (error: {err:.1f}m)")
