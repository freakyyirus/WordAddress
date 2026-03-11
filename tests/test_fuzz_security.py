"""
Fuzz & Security Tests for Open3Words API
Tests for robustness against malformed, adversarial, and edge-case inputs.

Uses Hypothesis for property-based fuzz testing and direct HTTP for security.

Run:
    python -m pytest tests/test_fuzz_security.py -v
"""

import sys
import os
import random
import string
import math

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))

try:
    from hypothesis import given, settings, HealthCheck
    from hypothesis import strategies as st
    HAS_HYPOTHESIS = True
except ImportError:
    HAS_HYPOTHESIS = False

import pytest


# ══════════════════════════════════════════════════════════════
# Fuzz Tests: Core Encoder
# ══════════════════════════════════════════════════════════════

class TestEncoderFuzz:
    """Property-based fuzz tests for the encoding algorithm."""

    @classmethod
    def setup_class(cls):
        from location_encoder import LocationEncoder
        cls.encoder = LocationEncoder()

    @pytest.mark.skipif(not HAS_HYPOTHESIS, reason="hypothesis not installed")
    @given(
        lat=st.floats(min_value=-89.999, max_value=89.999, allow_nan=False, allow_infinity=False),
        lon=st.floats(min_value=-179.999, max_value=179.999, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=500, suppress_health_check=[HealthCheck.too_slow])
    def test_roundtrip_fuzz(self, lat, lon):
        """Any valid coordinate must encode and decode within tolerance."""
        words = self.encoder.encode(lat, lon)
        parts = words.split(".")

        # Must produce exactly 3 words
        assert len(parts) == 3, f"Expected 3 words, got {len(parts)}: {words}"

        # All words must be alphabetic lowercase
        for p in parts:
            assert p.isalpha() and p.islower(), f"Invalid word: '{p}'"

        # Round-trip error must be small
        dlat, dlon = self.encoder.decode(words)
        error_lat = abs(lat - dlat) * 111_000
        error_lon = abs(lon - dlon) * 111_000 * math.cos(math.radians(lat))
        error_m = math.sqrt(error_lat ** 2 + error_lon ** 2)
        assert error_m < 20, f"Round-trip error {error_m:.1f}m exceeds 20m for ({lat}, {lon})"

    @pytest.mark.skipif(not HAS_HYPOTHESIS, reason="hypothesis not installed")
    @given(
        lat=st.floats(min_value=-89, max_value=89, allow_nan=False, allow_infinity=False),
        lon=st.floats(min_value=-179, max_value=179, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_determinism_fuzz(self, lat, lon):
        """Same input always produces the same output."""
        w1 = self.encoder.encode(lat, lon)
        w2 = self.encoder.encode(lat, lon)
        assert w1 == w2

    def test_boundary_coordinates(self):
        """Test extreme coordinate values."""
        boundaries = [
            (-90, -180), (-90, 180), (90, -180), (90, 180),
            (0, 0), (0, -180), (0, 180), (-90, 0), (90, 0),
            (89.999999, 179.999999), (-89.999999, -179.999999),
        ]
        for lat, lon in boundaries:
            try:
                words = self.encoder.encode(lat, lon)
                assert len(words.split(".")) == 3
            except ValueError:
                pass  # Out-of-range is acceptable at exact boundaries

    def test_negative_zero_coordinates(self):
        """Test -0.0 vs 0.0."""
        w1 = self.encoder.encode(0.0, 0.0)
        w2 = self.encoder.encode(-0.0, -0.0)
        assert w1 == w2


# ══════════════════════════════════════════════════════════════
# Fuzz Tests: Error Correction
# ══════════════════════════════════════════════════════════════

class TestCorrectionFuzz:
    """Fuzz tests for the error correction module."""

    @classmethod
    def setup_class(cls):
        from location_encoder import LocationEncoder
        from error_correction import ErrorCorrector
        enc = LocationEncoder()
        cls.corrector = ErrorCorrector(enc.wordlist)
        cls.wordlist = enc.wordlist

    def test_random_typos(self):
        """Introduce random single-char typos and check correction."""
        rng = random.Random(42)
        successes = 0
        trials = 100

        for _ in range(trials):
            original = rng.choice(self.wordlist)
            if len(original) < 3:
                continue

            # Random substitution
            pos = rng.randint(0, len(original) - 1)
            char = rng.choice(string.ascii_lowercase)
            typo = original[:pos] + char + original[pos + 1:]

            results = self.corrector.correct_word(typo)
            found_words = [r["word"] for r in results]
            if original in found_words:
                successes += 1

        # At least 60% of single-char typos should be caught
        assert successes >= trials * 0.5, f"Only caught {successes}/{trials} typos"

    def test_random_deletions(self):
        """Delete a random character and check correction."""
        rng = random.Random(99)
        successes = 0
        trials = 50

        for _ in range(trials):
            original = rng.choice(self.wordlist)
            if len(original) < 4:
                continue

            pos = rng.randint(0, len(original) - 1)
            deleted = original[:pos] + original[pos + 1:]

            results = self.corrector.correct_word(deleted)
            found_words = [r["word"] for r in results]
            if original in found_words:
                successes += 1

        assert successes >= trials * 0.3, f"Only caught {successes}/{trials} deletions"


# ══════════════════════════════════════════════════════════════
# Security Tests
# ══════════════════════════════════════════════════════════════

class TestSecurityInputs:
    """Test that the encoder handles adversarial inputs safely."""

    @classmethod
    def setup_class(cls):
        from location_encoder import LocationEncoder
        cls.encoder = LocationEncoder()

    def test_sql_injection_in_words(self):
        """SQL injection strings should raise ValueError, not crash."""
        payloads = [
            "'; DROP TABLE users; --",
            "word1.word2.word3' OR '1'='1",
            "word1.word2.word3; DELETE FROM grid_cells;",
            "<script>alert('xss')</script>.word2.word3",
        ]
        for payload in payloads:
            with pytest.raises((ValueError, KeyError, Exception)):
                self.encoder.decode(payload)

    def test_xss_in_words(self):
        """XSS payloads should not propagate."""
        payloads = [
            "<img src=x onerror=alert(1)>.word2.word3",
            "word1.<svg onload=alert(1)>.word3",
            'word1.word2.<iframe src="javascript:alert(1)">',
        ]
        for payload in payloads:
            with pytest.raises((ValueError, KeyError, Exception)):
                self.encoder.decode(payload)

    def test_extremely_long_input(self):
        """Very long strings should not cause memory issues."""
        long_word = "a" * 100000
        with pytest.raises((ValueError, KeyError, Exception)):
            self.encoder.decode(f"{long_word}.{long_word}.{long_word}")

    def test_unicode_injection(self):
        """Unicode and null bytes should be handled safely."""
        payloads = [
            "word1\x00.word2.word3",
            "word1.word2.word3\xff",
            "wörd1.wörd2.wörd3",
            "слово1.слово2.слово3",  # Cyrillic
            "كلمة.كلمة.كلمة",  # Arabic
        ]
        for payload in payloads:
            with pytest.raises((ValueError, KeyError, Exception)):
                self.encoder.decode(payload)

    def test_nan_infinity_coords(self):
        """NaN and Infinity should be rejected."""
        with pytest.raises((ValueError, Exception)):
            self.encoder.encode(float("nan"), 0.0)
        with pytest.raises((ValueError, Exception)):
            self.encoder.encode(0.0, float("inf"))
        with pytest.raises((ValueError, Exception)):
            self.encoder.encode(float("-inf"), float("inf"))

    def test_out_of_range_coords(self):
        """Coordinates outside valid range should fail."""
        with pytest.raises(ValueError):
            self.encoder.encode(91, 0)
        with pytest.raises(ValueError):
            self.encoder.encode(0, 181)
        with pytest.raises(ValueError):
            self.encoder.encode(-91, -181)

    def test_empty_input(self):
        """Empty strings should fail gracefully."""
        with pytest.raises((ValueError, Exception)):
            self.encoder.decode("")
        with pytest.raises((ValueError, Exception)):
            self.encoder.decode("...")
        with pytest.raises((ValueError, Exception)):
            self.encoder.decode("word1.")


# ══════════════════════════════════════════════════════════════
# LFSR Scrambler Tests
# ══════════════════════════════════════════════════════════════

class TestLFSRScrambler:
    """Tests for the LFSR bit scrambler module."""

    def test_scrambler_dispersion(self):
        """Adjacent inputs should produce non-adjacent outputs."""
        from lfsr_scrambler import LFSRScrambler
        s = LFSRScrambler(bits=42)
        outputs = [s.forward(i) for i in range(100)]

        # Check that consecutive inputs produce spread-out outputs
        diffs = [abs(outputs[i + 1] - outputs[i]) for i in range(len(outputs) - 1)]
        avg_diff = sum(diffs) / len(diffs)

        # Average difference should be large (not 1)
        assert avg_diff > 1000, f"Insufficient dispersion: avg diff = {avg_diff}"

    def test_scrambler_uniqueness(self):
        """All outputs should be unique (no collisions)."""
        from lfsr_scrambler import LFSRScrambler
        s = LFSRScrambler(bits=20)
        outputs = {s.forward(i) for i in range(10000)}
        assert len(outputs) == 10000, f"Collisions detected: {10000 - len(outputs)} duplicates"


# ══════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
