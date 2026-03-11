"""
LFSR Bit Scrambler for Open3Words
Linear Feedback Shift Register-based scrambling for uniform bit distribution.

Unlike LCG (which is also available), LFSR produces good dispersion —
a single bit flip in input propagates across all output bits.

Supports forward (scramble) and reverse (unscramble) operations
with configurable bit width and polynomial taps.
"""

from typing import Optional


# Pre-selected maximal-length LFSR polynomials (feedback taps) by bit width.
# These guarantee full-period (2^n - 1) sequences.
# Format: {bits: (tap_positions_tuple)}
# Tap positions are 1-indexed from the MSB.
LFSR_POLYNOMIALS = {
    15: (15, 14),             # x^15 + x^14 + 1
    16: (16, 15, 13, 4),      # x^16 + x^15 + x^13 + x^4 + 1
    20: (20, 17),             # x^20 + x^17 + 1
    24: (24, 23, 22, 17),     # x^24 + x^23 + x^22 + x^17 + 1
    28: (28, 25),             # x^28 + x^25 + 1
    30: (30, 29, 26, 24),     # x^30 + x^29 + x^26 + x^24 + 1
    32: (32, 31, 29, 1),      # x^32 + x^31 + x^29 + x + 1
    36: (36, 25),             # x^36 + x^25 + 1
    40: (40, 38, 21, 19),     # x^40 + x^38 + x^21 + x^19 + 1
    42: (42, 41, 20, 19),     # x^42 + x^41 + x^20 + x^19 + 1
    45: (45, 44, 42, 41),     # x^45 + x^44 + x^42 + x^41 + 1
    48: (48, 47, 21, 20),     # x^48 + x^47 + x^21 + x^20 + 1
    51: (51, 50, 48, 45),     # x^51 + x^50 + x^48 + x^45 + 1
}


class LFSRScrambler:
    """
    Scrambles and unscrambles N-bit integers using a Linear Feedback Shift Register.

    The LFSR is applied as a series of shift+XOR rounds for diffusion.
    The number of rounds controls the degree of bit mixing.
    """

    def __init__(self, bits: int = 42, rounds: int = None, taps: tuple = None):
        """
        Args:
            bits:   Width of the bit field (must be in LFSR_POLYNOMIALS or provide custom taps)
            rounds: Number of LFSR rounds to apply (default: bits)
            taps:   Custom tap positions (1-indexed from MSB). If None, uses lookup.
        """
        self.bits = bits
        self.mask = (1 << bits) - 1

        if taps is not None:
            self.taps = taps
        elif bits in LFSR_POLYNOMIALS:
            self.taps = LFSR_POLYNOMIALS[bits]
        else:
            # Fall back to a simple 2-tap polynomial
            self.taps = (bits, bits // 2)

        self.rounds = rounds if rounds is not None else bits

        # Build tap bitmask for fast XOR
        self._tap_mask = 0
        for t in self.taps:
            self._tap_mask |= (1 << (t - 1))

    def forward(self, value: int) -> int:
        """Scramble a value using LFSR rounds (forward direction)."""
        state = value & self.mask
        if state == 0:
            # LFSR can't operate on all-zero state; use an offset
            state = 1

        for _ in range(self.rounds):
            # Compute feedback bit as XOR of all tap positions
            feedback = 0
            for t in self.taps:
                feedback ^= (state >> (t - 1)) & 1

            # Shift left and insert feedback
            state = ((state << 1) | feedback) & self.mask

        return state

    def reverse(self, value: int) -> int:
        """Reverse the LFSR scrambling (inverse direction)."""
        state = value & self.mask
        if state == 0:
            state = 1

        for _ in range(self.rounds):
            # Extract the feedback bit that was inserted (now at LSB position)
            feedback = state & 1

            # Shift right to undo the forward shift-left
            state = state >> 1

            # Re-compute what the MSB should be using taps (excluding the top tap)
            # The feedback was: XOR of taps at positions tap[0], tap[1], ...
            # After the reverse shift, we need to recover the original top bit
            xor_val = feedback
            for t in self.taps[1:]:
                xor_val ^= (state >> (t - 1)) & 1

            # Set the MSB based on recovery
            state |= (xor_val << (self.bits - 1))

        return state & self.mask

    def test_roundtrip(self, n_samples: int = 1000) -> bool:
        """Test that forward+reverse produces identity for random values."""
        import random
        random.seed(12345)
        for _ in range(n_samples):
            original = random.randint(0, self.mask)
            scrambled = self.forward(original)
            recovered = self.reverse(scrambled)
            if recovered != original:
                return False
        return True


# ── CLI ──────────────────────────────────────────────────────

if __name__ == "__main__":
    print("LFSR Scrambler Test")
    print("=" * 50)

    for bits in [15, 20, 28, 42, 45, 51]:
        if bits in LFSR_POLYNOMIALS:
            s = LFSRScrambler(bits=bits)
            passed = s.test_roundtrip(500)
            sample = s.forward(12345 & s.mask)
            print(f"  {bits}-bit: taps={s.taps}  roundtrip={'PASS' if passed else 'FAIL'}  "
                  f"sample(12345) → {sample}")
