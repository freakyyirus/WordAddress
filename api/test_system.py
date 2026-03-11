"""
Open3Words Test Suite
Run with: python -m pytest api/test_system.py -v
"""

import sys
import os
import json
import math

sys.path.insert(0, os.path.dirname(__file__))


# ──────────────────────────────────────────────────────────────
# Test: Wordlist Generator
# ──────────────────────────────────────────────────────────────

class TestWordlistGenerator:
    def test_wordlist_creation(self):
        from wordlist_generator import create_wordlist
        words = create_wordlist(target_size=1000)
        assert len(words) >= 1000, f"Expected >= 1000 words, got {len(words)}"

    def test_wordlist_uniqueness(self):
        from wordlist_generator import create_wordlist
        words = create_wordlist(target_size=1000)
        assert len(words) == len(set(words)), "Wordlist contains duplicates"

    def test_no_empty_words(self):
        from wordlist_generator import create_wordlist
        words = create_wordlist(target_size=500)
        for w in words:
            assert len(w.strip()) >= 2, f"Word too short: '{w}'"


# ──────────────────────────────────────────────────────────────
# Test: Location Encoder (Core Algorithm)
# ──────────────────────────────────────────────────────────────

class TestLocationEncoder:
    @classmethod
    def setup_class(cls):
        from location_encoder import LocationEncoder
        cls.encoder = LocationEncoder()

    # ── Round-trip tests ──────────────────────────────────────

    def test_roundtrip_london(self):
        self._assert_roundtrip(51.5074, -0.1278, "London")

    def test_roundtrip_new_york(self):
        self._assert_roundtrip(40.7128, -74.0060, "New York")

    def test_roundtrip_tokyo(self):
        self._assert_roundtrip(35.6762, 139.6503, "Tokyo")

    def test_roundtrip_sydney(self):
        self._assert_roundtrip(-33.8688, 151.2093, "Sydney")

    def test_roundtrip_south_pole(self):
        self._assert_roundtrip(-89.9999, 0.0, "Near South Pole")

    def test_roundtrip_equator_dateline(self):
        self._assert_roundtrip(0.0, 179.9999, "Equator/dateline")

    def test_roundtrip_negative_coords(self):
        self._assert_roundtrip(-22.9068, -43.1729, "Rio de Janeiro")

    def _assert_roundtrip(self, lat, lon, label=""):
        words = self.encoder.encode(lat, lon)
        parts = words.split(".")
        assert len(parts) == 3, f"{label}: Expected 3 words, got {len(parts)}"

        decoded_lat, decoded_lon = self.encoder.decode(words)
        error = self._haversine(lat, lon, decoded_lat, decoded_lon)
        # Should be within ~4 meters (our grid precision)
        assert error < 10, f"{label}: Error {error:.2f}m > 10m threshold"

    @staticmethod
    def _haversine(lat1, lon1, lat2, lon2):
        R = 6371000
        to_rad = math.radians
        dlat = to_rad(lat2 - lat1)
        dlon = to_rad(lon2 - lon1)
        a = math.sin(dlat / 2) ** 2 + math.cos(to_rad(lat1)) * math.cos(to_rad(lat2)) * math.sin(dlon / 2) ** 2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    # ── Uniqueness test ───────────────────────────────────────

    def test_unique_encodings(self):
        """Different locations must produce different word addresses."""
        coords = [
            (51.5074, -0.1278),
            (48.8566, 2.3522),
            (40.7128, -74.0060),
            (35.6762, 139.6503),
            (-33.8688, 151.2093),
            (1.3521, 103.8198),
        ]
        encoded = [self.encoder.encode(lat, lon) for lat, lon in coords]
        assert len(set(encoded)) == len(encoded), "Duplicate encodings for different coordinates"

    # ── Format test ───────────────────────────────────────────

    def test_word_format(self):
        words = self.encoder.encode(51.5074, -0.1278)
        parts = words.split(".")
        assert len(parts) == 3
        for part in parts:
            assert part.isalpha(), f"Word '{part}' is not all-alpha"
            assert part.islower(), f"Word '{part}' is not lowercase"

    # ── Deterministic test ────────────────────────────────────

    def test_determinism(self):
        """Same input must always produce same output."""
        w1 = self.encoder.encode(51.5074, -0.1278)
        w2 = self.encoder.encode(51.5074, -0.1278)
        assert w1 == w2, "Encoding is not deterministic"


# ──────────────────────────────────────────────────────────────
# Test: Error Correction
# ──────────────────────────────────────────────────────────────

class TestErrorCorrection:
    @classmethod
    def setup_class(cls):
        from location_encoder import LocationEncoder
        from error_correction import ErrorCorrector
        encoder = LocationEncoder()
        cls.corrector = ErrorCorrector(encoder.wordlist)

    def test_exact_match(self):
        word = "hello" if "hello" in self.corrector.wordlist_set else self.corrector.wordlist[0]
        results = self.corrector.correct_word(word)
        assert len(results) > 0
        assert results[0]["word"] == word

    def test_typo_correction(self):
        # Intentional typo of the first word in the list
        original = self.corrector.wordlist[0]
        if len(original) > 2:
            typo = original[0] + "z" + original[2:]
            results = self.corrector.correct_word(typo)
            words_found = [r["word"] for r in results]
            # The original should be among the top suggestions
            assert original in words_found, f"Expected '{original}' in corrections for '{typo}'"

    def test_address_correction(self):
        w1 = self.corrector.wordlist[0]
        w2 = self.corrector.wordlist[1]
        w3 = self.corrector.wordlist[2]
        address = f"{w1}.{w2}.{w3}"
        results = self.corrector.correct_address(address)
        assert len(results) > 0
        assert results[0]["words"] == address  # Exact match should be top


# ──────────────────────────────────────────────────────────────
# Test: Blockchain Verification (offline)
# ──────────────────────────────────────────────────────────────

class TestBlockchain:
    def test_location_hash(self):
        from blockchain_verification import BlockchainVerifier
        h = BlockchainVerifier.hash_location(51.5074, -0.1278, "alpha.bravo.charlie")
        assert h.startswith("0x")
        assert len(h) == 66  # 0x + 64 hex chars

    def test_hash_determinism(self):
        from blockchain_verification import BlockchainVerifier
        h1 = BlockchainVerifier.hash_location(51.5074, -0.1278, "test.word.here")
        h2 = BlockchainVerifier.hash_location(51.5074, -0.1278, "test.word.here")
        assert h1 == h2

    def test_hash_uniqueness(self):
        from blockchain_verification import BlockchainVerifier
        h1 = BlockchainVerifier.hash_location(51.5074, -0.1278, "alpha.bravo.charlie")
        h2 = BlockchainVerifier.hash_location(40.7128, -74.0060, "alpha.bravo.charlie")
        assert h1 != h2


# ──────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
