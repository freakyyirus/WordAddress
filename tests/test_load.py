"""
Locust Load Test for Open3Words API
Simulates concurrent users hitting encode/decode/suggest endpoints.

Run:
    locust -f tests/test_load.py --host=http://localhost:8000

Or headless:
    locust -f tests/test_load.py --host=http://localhost:8000 \
           --headless -u 100 -r 10 --run-time 60s
"""

import random
from locust import HttpUser, task, between


# Sample coordinates for load testing
TEST_COORDS = [
    (51.5074, -0.1278),    # London
    (40.7128, -74.0060),   # New York
    (35.6762, 139.6503),   # Tokyo
    (48.8566, 2.3522),     # Paris
    (-33.8688, 151.2093),  # Sydney
    (1.3521, 103.8198),    # Singapore
    (55.7558, 37.6173),    # Moscow
    (-22.9068, -43.1729),  # Rio
    (37.7749, -122.4194),  # San Francisco
    (28.6139, 77.2090),    # New Delhi
]


class Open3WordsUser(HttpUser):
    """Simulates a typical Open3Words API user."""

    wait_time = between(0.1, 1.0)  # 100ms to 1s between requests

    def on_start(self):
        """Cache some encoded words for decode testing."""
        self.known_words = []
        for lat, lon in TEST_COORDS[:3]:
            try:
                resp = self.client.post("/encode", json={"lat": lat, "lon": lon})
                if resp.status_code == 200:
                    self.known_words.append(resp.json().get("words", "table.chair.lamp"))
            except Exception:
                self.known_words.append("table.chair.lamp")

    # ── Encode tasks ─────────────────────────────────────────

    @task(5)
    def encode_post(self):
        """POST /encode with random coordinates."""
        lat, lon = random.choice(TEST_COORDS)
        # Add small jitter
        lat += random.uniform(-0.01, 0.01)
        lon += random.uniform(-0.01, 0.01)
        self.client.post("/encode", json={"lat": lat, "lon": lon})

    @task(3)
    def encode_get(self):
        """GET /encode with query params."""
        lat, lon = random.choice(TEST_COORDS)
        lat += random.uniform(-0.01, 0.01)
        lon += random.uniform(-0.01, 0.01)
        self.client.get(f"/encode?lat={lat:.6f}&lon={lon:.6f}")

    # ── Decode tasks ─────────────────────────────────────────

    @task(5)
    def decode_post(self):
        """POST /decode with known words."""
        if self.known_words:
            words = random.choice(self.known_words)
            self.client.post("/decode", json={"words": words})

    @task(3)
    def decode_get(self):
        """GET /decode with query params."""
        if self.known_words:
            words = random.choice(self.known_words)
            self.client.get(f"/decode?code={words}")

    # ── Suggest / autocomplete ───────────────────────────────

    @task(2)
    def suggest(self):
        """GET /suggest with partial input."""
        if self.known_words:
            words = random.choice(self.known_words)
            parts = words.split(".")
            # Send first 2 words + partial 3rd
            partial = f"{parts[0]}.{parts[1]}.{parts[2][:2]}"
            self.client.get(f"/suggest?code={partial}")

    @task(2)
    def autosuggest(self):
        """GET /autosuggest with partial input."""
        if self.known_words:
            words = random.choice(self.known_words)
            parts = words.split(".")
            self.client.get(f"/autosuggest?partial={parts[0]}.{parts[1]}.")

    # ── Error correction ─────────────────────────────────────

    @task(1)
    def correct(self):
        """POST /correct with intentional typo."""
        if self.known_words:
            words = random.choice(self.known_words)
            parts = words.split(".")
            # Introduce a typo in the first word
            if len(parts[0]) > 2:
                typo = parts[0][0] + "z" + parts[0][2:]
                self.client.post("/correct", json={"address": f"{typo}.{parts[1]}.{parts[2]}"})

    # ── Health check ─────────────────────────────────────────

    @task(1)
    def health(self):
        """GET /health."""
        self.client.get("/health")

    @task(1)
    def health_detailed(self):
        """GET /health/detailed."""
        self.client.get("/health/detailed")

    # ── Grid comparison ──────────────────────────────────────

    @task(1)
    def compare_grids(self):
        """GET /compare-grids."""
        lat, lon = random.choice(TEST_COORDS)
        self.client.get(f"/compare-grids?lat={lat}&lon={lon}")


class HighThroughputUser(HttpUser):
    """
    Aggressive user for stress testing.
    Rapid-fire encode/decode with no wait.
    """

    wait_time = between(0, 0.05)  # Nearly zero wait

    @task(10)
    def rapid_encode(self):
        lat = random.uniform(-90, 90)
        lon = random.uniform(-180, 180)
        self.client.post("/encode", json={"lat": lat, "lon": lon})

    @task(1)
    def rapid_health(self):
        self.client.get("/health")
