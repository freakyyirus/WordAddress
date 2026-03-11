"""
Core Location Encoder for Open3Words
Converts latitude/longitude coordinates to 3-word addresses and back.

Algorithm:
1. Normalize lat/lon to 0-1 range
2. Convert to binary with specified precision (25-bit lat, 26-bit lon)
3. Interleave bits using Z-order curve (space-filling curve)
4. Shuffle the resulting integer (LCG) to prevent spatial correlation
5. Factor into 3 word indices
6. Map indices to words from the wordlist
"""

import math
import json
import os
from typing import Tuple, List, Optional


class LocationEncoder:
    """
    Encodes GPS coordinates (lat, lon) into 3-word addresses and decodes them back.
    Uses Z-order curve interleaving + Linear Congruential Generator shuffle.
    """

    def __init__(self, wordlist_path: Optional[str] = None):
        if wordlist_path is None:
            wordlist_path = os.path.join(os.path.dirname(__file__), "wordlist.json")

        if not os.path.exists(wordlist_path):
            # Generate wordlist if it doesn't exist
            from wordlist_generator import create_wordlist, save_wordlist
            wordlist = create_wordlist(40000)
            save_wordlist(wordlist, wordlist_path)

        with open(wordlist_path, "r", encoding="utf-8") as f:
            self.wordlist: List[str] = json.load(f)

        self.word_count: int = len(self.wordlist)
        self.word_to_index: dict = {w: i for i, w in enumerate(self.wordlist)}

        # ── Shuffle constants (Linear Congruential Generator) ──
        # These are SECRET in production — change them to make your system unique.
        # Requirements for full-period LCG:
        #   - m is a power of 2
        #   - a ≡ 1 (mod 4) when m is a power of 2
        #   - c is odd
        self.SHUFFLE_A: int = 6364136223846793005   # Multiplier (Knuth's constant)
        self.SHUFFLE_C: int = 1442695040888963407   # Increment (odd, coprime to m)
        self.SHUFFLE_M: int = 2 ** 51               # Modulus (matches total bit-space)

        # ── Grid precision ──
        self.LAT_BITS: int = 25   # -90 to +90  → ~3m precision at equator
        self.LON_BITS: int = 26   # -180 to +180 → ~3m precision at equator
        self.TOTAL_BITS: int = self.LAT_BITS + self.LON_BITS  # 51 bits

        # Pre-compute modular inverse for unshuffling
        self._a_inv: int = self._modinv(self.SHUFFLE_A, self.SHUFFLE_M)

    # ──────────────────────────────────────────────────────────
    # PUBLIC API
    # ──────────────────────────────────────────────────────────

    def encode(self, lat: float, lon: float) -> str:
        """
        Convert GPS coordinates to a 3-word address.

        Args:
            lat: Latitude in degrees (-90 to +90)
            lon: Longitude in degrees (-180 to +180)

        Returns:
            3-word address string like "table.chair.lamp"
        """
        self._validate_coords(lat, lon)
        n = self._coords_to_integer(lat, lon)
        shuffled = self._shuffle(n)
        return self._integer_to_words(shuffled)

    def decode(self, words: str) -> Tuple[float, float]:
        """
        Convert a 3-word address back to GPS coordinates.

        Args:
            words: 3-word address (e.g., "table.chair.lamp" or "table chair lamp")

        Returns:
            Tuple of (latitude, longitude)
        """
        words = self._normalize_input(words)
        n = self._words_to_integer(words)
        unshuffled = self._unshuffle(n)
        return self._integer_to_coords(unshuffled)

    def get_grid_square(self, lat: float, lon: float) -> dict:
        """
        Get the 3m × 3m grid square for given coordinates.

        Returns dict with center coordinates and bounds.
        """
        self._validate_coords(lat, lon)

        # Get the center of the grid cell
        n = self._coords_to_integer(lat, lon)
        center_lat, center_lon = self._integer_to_coords(n)

        # Calculate grid cell size at this latitude
        lat_step = 180 / (2 ** self.LAT_BITS)
        lon_step = 360 / (2 ** self.LON_BITS)

        return {
            "center": {"lat": center_lat, "lon": center_lon},
            "bounds": {
                "south": center_lat - lat_step / 2,
                "north": center_lat + lat_step / 2,
                "west": center_lon - lon_step / 2,
                "east": center_lon + lon_step / 2,
            },
            "size_meters": {
                "lat": lat_step * 111_000,  # ~111km per degree lat
                "lon": lon_step * 111_000 * math.cos(math.radians(lat)),
            },
        }

    # ──────────────────────────────────────────────────────────
    # COORDINATE ↔ INTEGER CONVERSION
    # ──────────────────────────────────────────────────────────

    def _coords_to_integer(self, lat: float, lon: float) -> int:
        """Convert lat/lon to a 51-bit integer using Z-order (Morton) curve."""
        # Normalize to [0, 1) range
        lat_norm = (lat + 90.0) / 180.0
        lon_norm = (lon + 180.0) / 360.0

        # Clamp to valid range
        lat_norm = max(0.0, min(lat_norm, 1.0 - 1e-15))
        lon_norm = max(0.0, min(lon_norm, 1.0 - 1e-15))

        # Convert to integer with specified precision
        lat_int = int(lat_norm * (2 ** self.LAT_BITS))
        lon_int = int(lon_norm * (2 ** self.LON_BITS))

        # Clamp to max values
        lat_int = min(lat_int, (2 ** self.LAT_BITS) - 1)
        lon_int = min(lon_int, (2 ** self.LON_BITS) - 1)

        # Interleave bits (Z-order / Morton curve)
        # Pattern: lon_bit_0, lat_bit_0, lon_bit_1, lat_bit_1, ...
        result = 0
        for i in range(max(self.LAT_BITS, self.LON_BITS)):
            if i < self.LON_BITS:
                result |= ((lon_int >> i) & 1) << (2 * i)
            if i < self.LAT_BITS:
                result |= ((lat_int >> i) & 1) << (2 * i + 1)

        return result

    def _integer_to_coords(self, n: int) -> Tuple[float, float]:
        """Convert a 51-bit integer back to lat/lon by de-interleaving bits."""
        lon_int = 0
        lat_int = 0

        for i in range(self.TOTAL_BITS):
            bit = (n >> i) & 1
            if i % 2 == 0:  # Even bits → longitude
                lon_int |= bit << (i // 2)
            else:            # Odd bits → latitude
                lat_int |= bit << (i // 2)

        # Denormalize back to degrees
        lat = (lat_int / (2 ** self.LAT_BITS)) * 180.0 - 90.0
        lon = (lon_int / (2 ** self.LON_BITS)) * 360.0 - 180.0

        return round(lat, 7), round(lon, 7)

    # ──────────────────────────────────────────────────────────
    # SHUFFLE / UNSHUFFLE (LCG)
    # ──────────────────────────────────────────────────────────

    def _shuffle(self, n: int) -> int:
        """Shuffle integer using Linear Congruential Generator."""
        return (self.SHUFFLE_A * n + self.SHUFFLE_C) % self.SHUFFLE_M

    def _unshuffle(self, m: int) -> int:
        """Reverse the LCG shuffle using modular inverse."""
        return ((m - self.SHUFFLE_C) * self._a_inv) % self.SHUFFLE_M

    # ──────────────────────────────────────────────────────────
    # INTEGER ↔ WORDS CONVERSION
    # ──────────────────────────────────────────────────────────

    def _integer_to_words(self, n: int) -> str:
        """Factor an integer into 3 word indices and look up words."""
        n = n % (self.word_count ** 3)  # Ensure within addressable range

        idx1 = n % self.word_count
        idx2 = (n // self.word_count) % self.word_count
        idx3 = (n // (self.word_count ** 2)) % self.word_count

        return f"{self.wordlist[idx1]}.{self.wordlist[idx2]}.{self.wordlist[idx3]}"

    def _words_to_integer(self, words: str) -> int:
        """Convert a dot-separated 3-word string back to an integer."""
        parts = words.split(".")
        if len(parts) != 3:
            raise ValueError(f"Expected 3 words separated by dots, got: '{words}'")

        indices = []
        for part in parts:
            idx = self.word_to_index.get(part)
            if idx is None:
                raise ValueError(f"Unknown word: '{part}'")
            indices.append(idx)

        return indices[0] + (indices[1] * self.word_count) + (indices[2] * self.word_count ** 2)

    # ──────────────────────────────────────────────────────────
    # HELPERS
    # ──────────────────────────────────────────────────────────

    @staticmethod
    def _validate_coords(lat: float, lon: float):
        """Raise ValueError if coordinates are out of range."""
        if not (-90 <= lat <= 90):
            raise ValueError(f"Latitude must be between -90 and 90, got {lat}")
        if not (-180 <= lon <= 180):
            raise ValueError(f"Longitude must be between -180 and 180, got {lon}")

    @staticmethod
    def _normalize_input(words: str) -> str:
        """Normalize user input to canonical format."""
        words = words.lower().strip()
        # Support space-separated as well as dot-separated
        words = words.replace(" ", ".")
        # Remove leading "///" prefix (W3W convention)
        if words.startswith("///"):
            words = words[3:]
        return words

    @staticmethod
    def _modinv(a: int, m: int) -> int:
        """Compute modular multiplicative inverse using Extended Euclidean Algorithm."""
        g, x, _ = LocationEncoder._extended_gcd(a, m)
        if g != 1:
            raise ValueError(f"Modular inverse does not exist (gcd={g})")
        return x % m

    @staticmethod
    def _extended_gcd(a: int, b: int) -> Tuple[int, int, int]:
        """Extended Euclidean Algorithm. Returns (gcd, x, y) such that a*x + b*y = gcd."""
        if a == 0:
            return b, 0, 1
        gcd, x1, y1 = LocationEncoder._extended_gcd(b % a, a)
        x = y1 - (b // a) * x1
        y = x1
        return gcd, x, y

    def precision_meters(self, lat: float = 0.0) -> dict:
        """
        Calculate the precision in meters at a given latitude.

        Returns:
            dict with lat_meters and lon_meters
        """
        lat_step = 180.0 / (2 ** self.LAT_BITS)
        lon_step = 360.0 / (2 ** self.LON_BITS)

        lat_meters = lat_step * 111_000  # ~111 km per degree latitude
        lon_meters = lon_step * 111_000 * math.cos(math.radians(lat))

        return {
            "lat_meters": round(lat_meters, 2),
            "lon_meters": round(lon_meters, 2),
        }


# ──────────────────────────────────────────────────────────────
# CLI Usage
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    encoder = LocationEncoder()

    test_locations = [
        ("London",   51.520847, -0.195521),
        ("NYC",      40.748817, -73.985428),
        ("Tokyo",    35.676200,  139.650300),
        ("Sydney",  -33.868800,  151.209300),
        ("São Paulo",-23.550520, -46.633308),
        ("North Pole", 89.999, 0.0),
        ("South Pole", -89.999, 0.0),
        ("Null Island", 0.0, 0.0),
    ]

    print("=" * 70)
    print("Open3Words Encoder — Test Results")
    print("=" * 70)
    print(f"Wordlist size: {encoder.word_count:,} words")
    print(f"Addressable cells: {encoder.word_count**3:,}")
    print(f"Precision at equator: {encoder.precision_meters(0)}")
    print(f"Precision at 51°N (London): {encoder.precision_meters(51)}")
    print("=" * 70)

    for name, lat, lon in test_locations:
        words = encoder.encode(lat, lon)
        decoded_lat, decoded_lon = encoder.decode(words)

        # Error in meters (Haversine approximation)
        dlat = (lat - decoded_lat) * 111_000
        dlon = (lon - decoded_lon) * 111_000 * math.cos(math.radians(lat))
        error_m = math.sqrt(dlat ** 2 + dlon ** 2)

        print(f"\n{name}:")
        print(f"  Input:   {lat:>11.6f}, {lon:>12.6f}")
        print(f"  Words:   ///{words}")
        print(f"  Decoded: {decoded_lat:>11.6f}, {decoded_lon:>12.6f}")
        print(f"  Error:   {error_m:.2f} meters")
