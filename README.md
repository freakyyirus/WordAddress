<p align="center">
  <h1 align="center">WordAddress</h1>
  <p align="center">
    <strong>Open-source three-word location encoding for the entire planet</strong>
  </p>
  <p align="center">
    <a href="#quick-start">Quick Start</a> &middot;
    <a href="#api-reference">API Reference</a> &middot;
    <a href="#deployment">Deployment</a> &middot;
    <a href="#roadmap">Roadmap</a> &middot;
    <a href="#license">License</a>
  </p>
</p>

---

**WordAddress** converts any GPS coordinate on Earth into a unique, human-memorable three-word address (e.g. `///forest.morning.river`) and back — with ~3.5 m precision at the equator.

It ships with three interchangeable grid systems, multi-language wordlists, AI voice input, AR navigation, blockchain proof-of-location, offline-first PWA, and production deployment configs for Docker, AWS Lambda, and Cloudflare Workers.

| Metric | Value |
|--------|-------|
| Grid precision (default) | ~3.5 m at equator |
| Wordlist size | 40,000 curated English words |
| Address space | 40,000³ ≈ **64 trillion** unique cells |
| API endpoints | **31** (29 REST + 1 WebSocket + 1 static) |
| Supported languages | 9 (en, es, fr, de, pt, ja, zh, ar, hi) |
| Total source lines | ~6,100+ |

---

## Table of Contents

- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Core Algorithm](#core-algorithm)
- [Features](#features)
- [Quick Start](#quick-start)
- [API Reference](#api-reference)
- [Project Structure](#project-structure)
- [Database Schema](#database-schema)
- [Smart Contract](#smart-contract)
- [Testing](#testing)
- [Deployment](#deployment)
- [Environment Variables](#environment-variables)
- [Monitoring](#monitoring)
- [Phase-wise Development Roadmap](#roadmap)
- [Production Readiness Checklist](#production-readiness-checklist)
- [Contributing](#contributing)
- [License](#license)

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                   React 18 + MapLibre GL Frontend                │
│  ┌──────────┐ ┌──────────┐ ┌───────────┐ ┌───────────────────┐  │
│  │  Encode  │ │  Decode  │ │  Voice    │ │  AI Assistant     │  │
│  └──────────┘ └──────────┘ └───────────┘ └───────────────────┘  │
│  ┌──────────┐ ┌──────────────┐ ┌──────────────────────────────┐ │
│  │ AR Nav   │ │ On-Device AI │ │ Service Worker (Offline PWA) │ │
│  └──────────┘ └──────────────┘ └──────────────────────────────┘ │
└─────────────────────────┬────────────────────────────────────────┘
                          │ HTTPS / WSS
┌─────────────────────────┴────────────────────────────────────────┐
│                       FastAPI Backend (Python 3.11)               │
│ ┌────────────────┐ ┌────────────────┐ ┌────────────────────────┐ │
│ │ Z-order Encoder│ │ S2 Encoder     │ │ H3 Hex Encoder         │ │
│ │ (Default Grid) │ │ (Google S2)    │ │ (Uber H3)              │ │
│ └────────────────┘ └────────────────┘ └────────────────────────┘ │
│ ┌────────────────┐ ┌────────────────┐ ┌────────────────────────┐ │
│ │ Error Corrector│ │ Fuzzy Search   │ │ Multi-Language Manager  │ │
│ │ (Levenshtein,  │ │ (Trie, BK-Tree,│ │ (9 languages,          │ │
│ │  Metaphone,    │ │  Trigram,      │ │  auto-detection)        │ │
│ │  Keyboard)     │ │  Phonetic)     │ │                         │ │
│ └────────────────┘ └────────────────┘ └────────────────────────┘ │
│ ┌────────────────┐ ┌────────────────┐ ┌────────────────────────┐ │
│ │ Voice (Whisper)│ │ AI Engine      │ │ Blockchain Verifier    │ │
│ │                │ │ (Ollama LLM)   │ │ (Ethereum / Web3)      │ │
│ └────────────────┘ └────────────────┘ └────────────────────────┘ │
└──────┬──────────┬──────────┬──────────┬──────────────────────────┘
       │          │          │          │
  ┌────┴───┐ ┌───┴───┐ ┌───┴───┐ ┌───┴────┐
  │PostGIS │ │ Redis │ │Whisper│ │ Ollama │
  │  (DB)  │ │(Cache)│ │(ASR)  │ │(LLM)   │
  └────────┘ └───────┘ └───────┘ └────────┘
```

---

## Tech Stack

### Backend

| Technology | Version | Purpose |
|---|---|---|
| **Python** | 3.11 | Core runtime |
| **FastAPI** | 0.109.0 | Async REST / WebSocket framework |
| **Uvicorn** | 0.27.0 | ASGI server with 2 workers |
| **Pydantic** | 2.5.3 | Request / response validation |
| **Redis** | 5.0.1 | Response caching with graceful fallback |
| **aiohttp** | 3.9.3 | Async HTTP client (Whisper, Ollama) |
| **s2sphere** | 0.2.5 | Google S2 Geometry cell encoding |
| **h3** | 3.7.7 | Uber H3 hexagonal grid encoding |
| **jellyfish** | 1.0.3 | Levenshtein, Metaphone, Soundex |
| **metaphone** | 0.6 | Double Metaphone phonetic matching |
| **nltk** | 3.9.1 | SCOWL / corpus-based wordlist generation |
| **web3** | 6.14.0 | Ethereum blockchain integration |
| **SpeechRecognition** | 3.10.1 | Audio processing utilities |
| **numpy** | 1.26.3 | Numeric operations |
| **SQLAlchemy** | 2.0.25 | ORM layer |
| **asyncpg** | 0.29.0 | Async PostgreSQL driver |
| **httpx** | 0.26.0 | HTTP client for health checks |

### Frontend

| Technology | Version | Purpose |
|---|---|---|
| **React** | 18.2 | Component UI framework |
| **MapLibre GL JS** | 4.1 | Interactive vector map (open-source) |
| **Three.js** | 0.161 | 3D / AR rendering |
| **@react-three/fiber** | 8.15 | React reconciler for Three.js |
| **@react-three/xr** | 5.7 | WebXR AR/VR bindings |
| **Lucide React** | 0.300 | Iconography |

### Infrastructure

| Technology | Purpose |
|---|---|
| **Docker Compose** | Multi-service orchestration (7 services) |
| **PostGIS 15** | Spatial database with trigram indexes |
| **Redis 7 Alpine** | LRU cache (256 MB, appendonly) |
| **Whisper ASR** | Self-hosted speech-to-text |
| **Ollama** | Local LLM (phi3:mini) — zero API costs |
| **Prometheus + Grafana** | Metrics and dashboards |
| **nginx** | Static serving + reverse proxy |

### Testing

| Technology | Version | Purpose |
|---|---|---|
| **pytest** | 7.4.4 | Unit and integration tests |
| **Hypothesis** | 6.98.1 | Property-based fuzz testing |
| **Locust** | 2.24.0 | Load and stress testing |

### Deployment Targets

| Platform | Config File |
|---|---|
| Docker Compose (full) | `docker-compose.yml` |
| Docker Compose (minimal) | `deploy/docker-compose.minimal.yml` |
| AWS Lambda (Mangum) | `deploy/aws-sam-template.yaml` |
| Cloudflare Workers | `deploy/wrangler.toml` |

### Smart Contract

| Technology | Version | Purpose |
|---|---|---|
| **Solidity** | 0.8.19 | Proof-of-Location smart contract |
| **Web3.py** | 6.14.0 | Python to Ethereum bridge |

---

## Core Algorithm

### Default Grid — Z-order Curve + LCG

```
GPS (lat, lon)
  │
  ▼
 Normalize to [0, 1) range
  │
  ▼
 Quantize: 25-bit latitude × 26-bit longitude = 51 bits
  │
  ▼
 Z-order (Morton) interleave → 51-bit integer
  │
  ▼
 LCG shuffle (Knuth constants) → dispersed integer
  │
  ▼
 Modular factoring → 3 indices into 40,000-word list
  │
  ▼
 ///word1.word2.word3
```

- **Precision:** ~3.5 m at equator
- **Address space:** 40,000³ ≈ 64 trillion unique cells
- **Shuffle:** Linear Congruential Generator prevents neighboring cells from having similar words
- **Reversal:** Extended Euclidean Algorithm computes modular inverse for LCG undo

### S2 Geometry Grid (Alternative)

| Property | Value |
|---|---|
| Library | Google S2 via `s2sphere` |
| Cell level | 25 (~5 m resolution) |
| Extracted bits | 42 |
| Scrambler | LFSR (Linear Feedback Shift Register) |
| Wordlist | 32,768 SCOWL-filtered words (32K³ ≈ 35 trillion) |

Encodes GPS → S2 cell → 42-bit extraction → LFSR scramble → 3 words. Decodes via brute-force scan across all 6 S2 cube faces.

### H3 Hexagonal Grid (Alternative)

| Property | Value |
|---|---|
| Library | Uber H3 |
| Resolution | 12 (~9.4 m edge length) |
| Extracted bits | 45 |
| Scrambler | LFSR |

Hexagonal tiling avoids edge/corner ambiguity. Provides GeoJSON boundary output and ring-1 neighbor enumeration.

### LFSR Scrambler

A configurable Linear Feedback Shift Register with pre-selected **maximal-length polynomials** for bit widths 15, 16, 20, 24, 28, 30, 32, 36, 40, 42, 45, 48, and 51. Deterministic and fully reversible. Used by S2 and H3 encoders as an alternative to the Z-order grid's LCG.

---

## Features

### Core Encoding
- **Three-word addressing** — Any GPS coordinate → unique `///word.word.word`
- **Sub-4m precision** — 25-bit lat × 26-bit lon quantization
- **Deterministic and reversible** — Same input always yields same output, and vice versa
- **Three grid systems** — Z-order (default), S2 Geometry, H3 Hexagonal — switchable per request

### Wordlists and Language
- **40,000-word curated English list** — Sourced from 6 categories, filtered for offensiveness and homophones
- **32,768-word SCOWL list** — Corpus-based alternative via NLTK/WordNet with homophone/offensive filtering
- **9 languages supported** — English, Spanish, French, German, Portuguese, Japanese, Chinese, Arabic, Hindi
- **Auto language detection** — Identifies language from a 3-word address

### Error Correction and Fuzzy Search
- **Multi-strategy correction** — Levenshtein edit distance, Double Metaphone, keyboard proximity (QWERTY map)
- **Trie prefix tree** — Instant autocomplete with configurable result limit
- **BK-Tree** — Sub-linear edit-distance lookups
- **Trigram index** — N-gram overlap similarity scoring
- **Phonetic index** — Soundex + Metaphone combined phonetic matching
- **Combined fuzzy engine** — Merges all 4 strategies with weighted ranking

### Voice and AI
- **Whisper speech-to-text** — Self-hosted ASR with regex pattern extraction + LLM fallback
- **Ollama LLM** — Natural language → GPS via local phi3:mini (zero API costs, full privacy)
- **Context-aware assistant** — Intent classification (navigate/share/save/nearby) with per-user history
- **Navigation info** — Haversine distance, bearing, cardinal direction, walking/driving time estimates

### Frontend
- **Interactive map** — MapLibre GL JS with click-to-encode, fly-to animations, markers with popups
- **4-tab UI** — Encode, Decode, Voice, Assistant
- **AR Navigation** — WebXR support with 2D compass fallback (distance, bearing, direction arrow)
- **On-device AI** — Browser-side Levenshtein correction, IndexedDB caching, offline action queue
- **Progressive Web App** — Service worker with pre-caching, network-first API, cache-first tiles, push notifications, background sync

### Blockchain
- **Proof-of-Location** — Ethereum smart contract (Solidity 0.8.19) for tamper-proof location attestation
- **Witness system** — Multiple witnesses confirm proofs; reputation ≥ 10 required
- **Reputation scoring** — On-chain score with admin bootstrap and reward mechanics

### Infrastructure
- **Redis caching** — LRU eviction, 256 MB, appendonly persistence, graceful fallback when unavailable
- **PostGIS spatial database** — Geometric indexes, trigram search, location proofs mirror
- **Prometheus + Grafana** — Health scraping every 15s, configurable dashboards

---

## Quick Start

### Option 1 — Docker Compose (Recommended)

```bash
git clone https://github.com/your-org/wordaddress.git
cd wordaddress
cp .env.example .env          # Edit as needed
docker compose up --build
```

| Service | URL | Description |
|---|---|---|
| **Web UI** | http://localhost:3000 | React + MapLibre frontend |
| **API** | http://localhost:8000 | FastAPI backend |
| **API Docs** | http://localhost:8000/docs | Swagger / OpenAPI explorer |
| **PostgreSQL** | localhost:5432 | PostGIS database |
| **Redis** | localhost:6379 | Cache |
| **Whisper** | localhost:9000 | Speech-to-text |
| **Ollama** | localhost:11434 | Local LLM |

After startup, pull the Ollama model:

```bash
docker exec wordaddress-ollama ollama pull phi3:mini
```

### Option 2 — Local Development

**Backend:**

```bash
cd api
python -m venv venv
venv\Scripts\activate           # Windows
# source venv/bin/activate      # macOS / Linux
pip install -r requirements.txt
python wordlist_generator.py    # Generate wordlist (first run only)
uvicorn main:app --reload --port 8000
```

**Frontend:**

```bash
cd frontend
npm install
npm start                       # Dev server on http://localhost:3000
```

### Option 3 — Minimal / Free-Tier VM (1 GB RAM)

For Oracle Cloud Free Tier, Fly.io, Railway, etc.:

```bash
docker compose -f deploy/docker-compose.minimal.yml up --build
```

Runs only API (64 MB limit) + Redis (64 MB). No database, Whisper, or Ollama.

---

## API Reference

### Core Encoding / Decoding

| Method | Path | Description |
|---|---|---|
| `POST` | `/encode` | GPS → three-word address (JSON body: `{"lat": ..., "lon": ...}`) |
| `GET` | `/encode` | GPS → words via query params: `?lat=&lon=&grid=default|s2|h3&lang=en` |
| `POST` | `/decode` | Three-word address → GPS (JSON body: `{"words": "..."}`) |
| `GET` | `/decode` | Words → GPS: `?code=word.word.word&grid=&lang=` |

### Error Correction and Suggestions

| Method | Path | Description |
|---|---|---|
| `POST` | `/correct` | Fix typos in word addresses |
| `GET` | `/autosuggest` | Autocomplete partial input: `?q=for.mor` |
| `GET` | `/suggest` | Fuzzy correction + autocomplete: `?q=alpa.brvo.charlee` |
| `POST` | `/suggest` | POST variant for fuzzy suggestions |

### S2 Geometry Grid

| Method | Path | Description |
|---|---|---|
| `GET` | `/s2/encode` | GPS → S2-based three-word address: `?lat=&lon=` |
| `GET` | `/s2/decode` | S2 words → GPS: `?code=` |
| `GET` | `/s2/neighbors` | Neighboring S2 cells: `?lat=&lon=` |

### H3 Hexagonal Grid

| Method | Path | Description |
|---|---|---|
| `GET` | `/h3/encode` | GPS → H3-based three-word address: `?lat=&lon=` |
| `GET` | `/h3/decode` | H3 words → GPS: `?code=` |
| `GET` | `/h3/neighbors` | Neighboring H3 hexagons: `?lat=&lon=` |
| `GET` | `/h3/boundary` | H3 hex boundary GeoJSON polygon: `?lat=&lon=` |

### Voice and AI

| Method | Path | Description |
|---|---|---|
| `POST` | `/voice/decode` | Upload audio → extract 3-word address |
| `WS` | `/voice/stream` | Real-time streaming voice recognition |
| `POST` | `/ai/parse-location` | Natural language → coordinates via LLM |
| `POST` | `/ai/suggest` | AI-powered smart suggestions |
| `POST` | `/assistant/query` | Conversational assistant (navigate/share/save/nearby) |
| `POST` | `/assistant/navigate` | Navigation info between two points |

### Blockchain

| Method | Path | Description |
|---|---|---|
| `POST` | `/blockchain/submit-proof` | Submit proof-of-location on-chain |
| `POST` | `/blockchain/witness` | Witness / confirm a proof |
| `GET` | `/blockchain/verify` | Check on-chain verification status: `?proof_id=` |
| `GET` | `/blockchain/reputation` | Query reputation score: `?address=` |

### Utility and Health

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Basic health check (wordlist size, Redis status) |
| `GET` | `/health/detailed` | All subsystem statuses (S2, H3, fuzzy, blockchain, etc.) |
| `GET` | `/precision` | Grid precision in meters at given latitude |
| `GET` | `/languages` | List all supported languages with availability |
| `GET` | `/languages/basic` | Basic language list (English only) |
| `GET` | `/detect-language` | Auto-detect language of word address: `?code=` |
| `GET` | `/compare-grids` | Compare default vs S2 vs H3 for same coordinates: `?lat=&lon=` |

### Examples

```bash
# ── Encode ──────────────────────────────────────────────────
# POST
curl -X POST http://localhost:8000/encode \
  -H "Content-Type: application/json" \
  -d '{"lat": 51.5074, "lon": -0.1278}'

# GET (with grid selection and language)
curl "http://localhost:8000/encode?lat=51.5074&lon=-0.1278&grid=s2&lang=en"

# ── Decode ──────────────────────────────────────────────────
curl "http://localhost:8000/decode?code=forest.morning.river"

# ── Fuzzy Suggest ───────────────────────────────────────────
curl "http://localhost:8000/suggest?q=forst.mornig.rivr"

# ── S2 Geometry ─────────────────────────────────────────────
curl "http://localhost:8000/s2/encode?lat=48.8566&lon=2.3522"

# ── H3 Hexagonal ───────────────────────────────────────────
curl "http://localhost:8000/h3/encode?lat=35.6762&lon=139.6503"

# ── Compare All Grids ──────────────────────────────────────
curl "http://localhost:8000/compare-grids?lat=51.5074&lon=-0.1278"

# ── Error Correction ───────────────────────────────────────
curl -X POST http://localhost:8000/correct \
  -H "Content-Type: application/json" \
  -d '{"words": "forst.mornig.rivr"}'

# ── Blockchain ─────────────────────────────────────────────
curl -X POST http://localhost:8000/blockchain/submit-proof \
  -H "Content-Type: application/json" \
  -d '{"lat": 51.5074, "lon": -0.1278, "words": "forest.morning.river"}'
```

---

## Project Structure

```
wordaddress/
├── api/                               # ─── Python Backend ──────────────
│   ├── main.py                        # FastAPI app — all 31 endpoints
│   ├── location_encoder.py            # Z-order curve + LCG encoder (core)
│   ├── s2_encoder.py                  # S2 Geometry grid encoder
│   ├── h3_encoder.py                  # H3 hexagonal grid encoder
│   ├── lfsr_scrambler.py              # LFSR bit scrambler (15–51 bits)
│   ├── wordlist_generator.py          # Curated 40K word generator
│   ├── scowl_wordlist.py             # SCOWL/corpus-based 32K generator
│   ├── multi_language.py              # 9-language wordlist manager
│   ├── fuzzy_search.py               # Trie + BK-Tree + Trigram + Phonetic
│   ├── error_correction.py            # Levenshtein + Metaphone + keyboard
│   ├── voice_processor.py             # Whisper ASR integration
│   ├── ai_location_engine.py          # Ollama LLM location parsing
│   ├── location_assistant.py          # Context-aware conversational AI
│   ├── blockchain_verification.py     # Web3 / Ethereum proof-of-location
│   ├── test_system.py                 # Core unit tests (pytest)
│   ├── requirements.txt               # 25 Python dependencies
│   └── Dockerfile                     # Python 3.11-slim + curl
│
├── frontend/                           # ─── React Frontend ─────────────
│   ├── src/
│   │   ├── App.js                     # Main SPA (map, encode/decode/voice/assistant)
│   │   ├── ARNavigation.js            # AR navigation + compass fallback
│   │   ├── OnDeviceAI.js              # Offline AI + IndexedDB caching
│   │   └── index.js                   # Entry point + SW registration
│   ├── public/
│   │   ├── service-worker.js          # Offline-first PWA (288 lines)
│   │   ├── index.html                 # HTML shell
│   │   └── manifest.json              # PWA manifest
│   ├── Dockerfile                     # Multi-stage: Node 18 → nginx
│   ├── nginx.conf                     # SPA routing + API reverse proxy
│   └── package.json                   # React 18, MapLibre, Three.js
│
├── contracts/                          # ─── Blockchain ──────────────────
│   ├── Open3WordsProofOfLocation.sol  # Solidity 0.8.19 smart contract
│   └── abi.json                       # Contract ABI
│
├── deploy/                             # ─── Deployment Configs ─────────
│   ├── lambda_handler.py              # AWS Lambda via Mangum
│   ├── cloudflare_worker.js           # CF Workers edge proxy
│   ├── wrangler.toml                  # Cloudflare Worker config
│   ├── aws-sam-template.yaml          # AWS SAM serverless template
│   └── docker-compose.minimal.yml     # 2-service stack for free-tier VMs
│
├── tests/                              # ─── Advanced Testing ───────────
│   ├── test_load.py                   # Locust load and stress tests
│   └── test_fuzz_security.py          # Hypothesis fuzz + security tests
│
├── monitoring/                         # ─── Observability ──────────────
│   └── prometheus.yml                 # Scrape config (15s interval)
│
├── docker-compose.yml                  # Full 7-service production stack
├── init.sql                            # PostGIS schema (6 tables)
├── .env.example                        # All environment variables
└── .gitignore                          # Python, Node, Docker, IDE ignores
```

---

## Database Schema

The `init.sql` initializes PostgreSQL with **PostGIS** and **pg_trgm** extensions and creates 6 tables:

| Table | Purpose | Key Columns |
|---|---|---|
| `wordlist` | Dictionary storage (40K words) | `word` (unique), `word_index` (unique), `category`, `metaphone` |
| `grid_cells` | Spatial cache of encoded cells | `word1`/`word2`/`word3`, `lat`/`lon`, `geom` (Point 4326), `z_index` |
| `word_aliases` | Alternate spellings / abbreviations | `alias`, `canonical` → FK `wordlist.word`, `type` |
| `api_usage` | Request analytics / audit log | `endpoint`, `method`, `status_code`, `latency_ms`, `client_ip` |
| `location_proofs` | On-chain proof mirror | `proof_id`, `location_hash`, `prover_address`, `tx_hash`, `verified` |
| `saved_locations` | User favorites | `user_id`, `words`, `label`, `lat`/`lon`, `geom` (Point 4326) |

**Indexes:** B-tree on words, GiST on geometry columns, GIN trigram on `wordlist.word`, B-tree on `api_usage.created_at DESC`.

**Triggers:** Auto-compute `geom` column from `lat`/`lon` on INSERT for `grid_cells` and `saved_locations`.

---

## Smart Contract

**File:** `contracts/Open3WordsProofOfLocation.sol` — Solidity 0.8.19, MIT License

### Functions

| Function | Access | Description |
|---|---|---|
| `submitProof(bytes32 locationHash, uint8 witnessesRequired)` | External | Submit a location proof; emits `ProofSubmitted` |
| `witnessProof(bytes32 proofId)` | External | Confirm a proof (requires reputation ≥ 10, no self-witness) |
| `isVerified(bytes32 proofId)` | View | Check if proof has sufficient witnesses |
| `grantReputation(address user, uint256 amount)` | External | Admin bootstrap (requires caller reputation ≥ 100) |

### Events

| Event | Indexed Parameters |
|---|---|
| `ProofSubmitted` | `proofId`, `prover` |
| `ProofWitnessed` | `proofId`, `witness` |
| `ProofVerified` | `proofId` |

### Constants

- `MIN_REPUTATION = 10` — Minimum reputation to witness a proof
- `REPUTATION_REWARD = 5` — Reward per successful witness action

---

## Testing

### Unit and Integration Tests

```bash
cd api
python -m pytest test_system.py -v
```

| Test Suite | Coverage |
|---|---|
| `TestWordlistGenerator` | Creation, uniqueness, no-empty words, size validation |
| `TestLocationEncoder` | Round-trip for 7 global cities (< 10 m error), uniqueness, format, determinism |
| `TestErrorCorrection` | Exact match passthrough, single-char typo recovery, full address correction |
| `TestBlockchain` | Hash format (SHA-256), determinism, uniqueness |

### Fuzz and Property-Based Tests

```bash
python -m pytest tests/test_fuzz_security.py -v
```

| Test Class | What It Tests |
|---|---|
| `TestEncoderFuzz` | 500 random coordinates roundtrip, 200 determinism checks, poles, antimeridian, negative zero |
| `TestCorrectionFuzz` | Random single-char typos (100 trials, 50% threshold), random deletions (50 trials) |
| `TestSecurityInputs` | SQL injection (10 payloads), XSS (5 payloads), 100K-char input, unicode/null bytes, NaN/Infinity, out-of-range coords, empty input |
| `TestLFSRScrambler` | Bit dispersion quality (avg diff > 1000), uniqueness over 10K samples (zero collisions) |

### Load and Stress Tests

```bash
pip install locust
locust -f tests/test_load.py --host http://localhost:8000
# Open http://localhost:8089 in your browser
```

| User Class | Behavior |
|---|---|
| `Open3WordsUser` | Realistic traffic: encode (30%), decode (25%), suggest (15%), autosuggest (10%), correct (10%), health (5%), compare-grids (5%) |
| `HighThroughputUser` | Stress mode: near-zero wait, random global coordinates, rapid-fire encode + health |

---

## Deployment

### Full Stack — Docker Compose

```bash
docker compose up --build
```

7 services: API, Web (nginx), PostgreSQL (PostGIS), Redis, Whisper, Ollama, and optionally Prometheus + Grafana.

### Minimal — Free-Tier VM (1 GB RAM)

```bash
docker compose -f deploy/docker-compose.minimal.yml up --build
```

2 services only: API (64 MB) + Redis (64 MB). Ideal for Oracle Cloud Free Tier, Fly.io, Railway.

### Serverless — AWS Lambda

```bash
cd deploy
sam build
sam deploy --guided
```

Wraps the full FastAPI app via **Mangum**. Configured with 256 MB memory, 30-second timeout, HTTP API Gateway catch-all proxy.

### Edge — Cloudflare Workers

```bash
cd deploy
npx wrangler publish
```

Lightweight edge proxy for `/encode` and `/decode`. Proxies to the origin API for full encoding logic. Includes CORS headers and demo mode.

---

## Environment Variables

Copy and customize:

```bash
cp .env.example .env
```

| Variable | Default | Required | Description |
|---|---|---|---|
| `REDIS_URL` | `redis://localhost:6379` | No | Redis connection (graceful fallback if unavailable) |
| `DATABASE_URL` | `postgresql://o3w:o3w_secret@localhost:5432/open3words` | No | PostGIS connection |
| `WHISPER_URL` | `http://localhost:9000` | No | Self-hosted Whisper ASR endpoint |
| `OLLAMA_URL` | `http://localhost:11434` | No | Ollama LLM endpoint |
| `WEB3_RPC_URL` | `http://localhost:8545` | No | Ethereum JSON-RPC |
| `CONTRACT_ADDRESS` | *(empty)* | For blockchain | Deployed contract address |
| `PRIVATE_KEY` | *(empty)* | For blockchain | Ethereum signing key |
| `DEFAULT_GRID` | `default` | No | Grid system: `default`, `s2`, or `h3` |
| `DEFAULT_LANG` | `en` | No | Default language code |
| `API_HOST` | `0.0.0.0` | No | Bind address |
| `API_PORT` | `8000` | No | Bind port |
| `API_WORKERS` | `2` | No | Uvicorn worker count |
| `LOG_LEVEL` | `info` | No | Logging verbosity |

> **Note:** The API starts with zero configuration. All external services (Redis, PostgreSQL, Whisper, Ollama, blockchain) are optional and degrade gracefully.

---

## Monitoring

```bash
docker compose --profile monitoring up
```

| Service | URL | Credentials |
|---|---|---|
| Prometheus | http://localhost:9090 | — |
| Grafana | http://localhost:3001 | admin / admin |

Prometheus scrapes the `/health` endpoint every 15 seconds.

---

<a id="roadmap"></a>

## Phase-wise Development Roadmap

### Phase 1 — Core Engine ✅ Complete

| Deliverable | Description |
|---|---|
| Z-order encoder | 25-bit lat × 26-bit lon, Morton interleave, LCG shuffle, modular inverse decode |
| 40K wordlist generator | 6-category curated corpus, offensive/homophone filtering, compound-word padding |
| Error correction | Levenshtein + Double Metaphone + keyboard proximity + prefix matching |
| Basic REST API | POST `/encode`, POST `/decode`, POST `/correct`, GET `/autosuggest` |
| Test suite | Round-trip accuracy (< 10 m), uniqueness, determinism, error correction |

### Phase 2 — AI, Voice and Blockchain ✅ Complete

| Deliverable | Description |
|---|---|
| Whisper integration | Audio upload pipeline → regex extraction → LLM fallback |
| Ollama LLM engine | Natural language → GPS, per-user conversation context, smart suggestions |
| Conversational assistant | Intent classification (navigate/share/save/nearby), favorites, history |
| Blockchain verification | Solidity contract, Web3.py, witness system, reputation scoring |
| PostGIS database | 6-table schema with spatial triggers, trigram indexes, analytics table |

### Phase 3 — Frontend and PWA ✅ Complete

| Deliverable | Description |
|---|---|
| React 18 SPA | MapLibre map with 4-tab UI (encode/decode/voice/assistant) |
| AR Navigation | WebXR support + 2D compass fallback with Haversine distance |
| On-Device AI | IndexedDB caching, offline Levenshtein correction, background sync queue |
| Service Worker | Pre-caching, network-first API, cache-first tiles, push notifications |
| PWA manifest | Installable standalone app with theme color and icons |
| nginx config | SPA routing, API reverse proxy, WebSocket upgrade, static caching (1 year) |

### Phase 4 — Alternative Grids and Advanced Search ✅ Complete

| Deliverable | Description |
|---|---|
| S2 Geometry encoder | Google S2 cells at level 25 (~5 m), LFSR scrambling, 6-face decode, neighbor lookup |
| H3 Hexagonal encoder | Uber H3 at resolution 12 (~9.4 m), boundary GeoJSON, ring-1 neighbors |
| LFSR scrambler | Maximal-length polynomials for 13 bit widths (15–51), roundtrip verified |
| SCOWL wordlist | NLTK/WordNet corpus-based 32K generator with quality filters |
| Multi-language | 9 languages with auto-detection and per-language encoders |
| Fuzzy search engine | Trie + BK-Tree + Trigram + Phonetic combined scoring |
| GET endpoints | Query-param variants for encode, decode, suggest, grid comparison |

### Phase 5 — Testing and Hardening ✅ Complete

| Deliverable | Description |
|---|---|
| Hypothesis fuzz tests | 500-sample roundtrip, boundary coords (poles, antimeridian), determinism |
| Security tests | SQL injection, XSS, unicode, NaN, overflow, empty input |
| LFSR verification | Dispersion quality (avg diff > 1000), 10K-sample uniqueness (zero collisions) |
| Locust load tests | Realistic traffic mix + stress mode with near-zero wait |

### Phase 6 — Deployment and Infrastructure ✅ Complete

| Deliverable | Description |
|---|---|
| Docker Compose (full) | 7 services with health checks, volume persistence, resource limits |
| Docker Compose (minimal) | 2-service stack for free-tier VMs (64 MB each) |
| AWS Lambda | Mangum wrapper + SAM template (256 MB, 30s timeout) |
| Cloudflare Workers | Edge proxy with CORS and demo mode |
| Prometheus + Grafana | Metrics collection and dashboarding |
| Environment config | `.env.example` with all 14 variables documented |

### Phase 7 — Future Enhancements 🔜 Planned

| Feature | Priority | Description |
|---|---|---|
| Mobile apps (React Native) | High | iOS + Android native apps with offline encoding |
| SDK packages | High | Python, JavaScript, Go client libraries on package registries |
| Custom wordlists | Medium | Upload branded wordlists via admin API |
| Address sharing | Medium | Deep links, QR codes, NFC tap-to-share |
| Geocoding integration | Medium | Reverse geocode to human-readable place names |
| Rate limiting and auth | Medium | API key management, JWT auth, per-key rate limits |
| Horizontal scaling | Medium | Redis Cluster, read replicas, Kubernetes Helm chart |
| Multi-region deployment | Low | Edge-replicated wordlists via CF KV or DynamoDB Global Tables |
| Accessibility audit | Low | WCAG 2.1 AA compliance, screen reader testing |
| Internationalized frontend | Low | i18n for UI strings to match multi-language wordlists |

---

## Production Readiness Checklist

### Security

- [x] CORS middleware configured
- [x] Pydantic validation on all request bodies
- [x] SQL injection test coverage (10 payloads)
- [x] XSS payload test coverage (5 payloads)
- [x] Unicode / null byte boundary tests
- [x] No secrets in source code (`.env.example` with empty defaults)
- [x] `.gitignore` covers `.env`, `__pycache__`, `node_modules`, `*.sqlite3`
- [ ] Rate limiting (add via middleware or API gateway)
- [ ] JWT / API key authentication
- [ ] HTTPS enforcement (configure at load balancer / reverse proxy)

### Reliability

- [x] Graceful Redis fallback (API works without Redis)
- [x] Optional Whisper / Ollama (voice/AI degrade gracefully)
- [x] Docker health checks on API container
- [x] Service worker offline fallback for frontend
- [x] Deterministic encoding verified via fuzz tests (500+ coordinates)
- [ ] Circuit breakers for external service calls
- [ ] Structured logging (JSON format) for log aggregation

### Performance

- [x] Redis caching layer with LRU eviction (256 MB)
- [x] Uvicorn with 2 async workers
- [x] Locust load test suite
- [x] nginx static file caching (1-year `Cache-Control`)
- [x] Service worker pre-caching for offline speed
- [ ] CDN for static frontend assets
- [ ] Database connection pooling (asyncpg pool tuning)

### Observability

- [x] `/health` and `/health/detailed` endpoints
- [x] Prometheus scrape target configured
- [x] Grafana dashboard ready
- [x] `api_usage` analytics table in PostgreSQL
- [ ] Distributed tracing (OpenTelemetry)
- [ ] Error tracking (Sentry integration)

### CI/CD

- [ ] GitHub Actions workflow for test + lint + build
- [ ] Docker image publishing to GHCR / ECR
- [ ] Automated deployment pipeline
- [ ] Database migrations (Alembic)

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/my-feature`
3. Make changes and add tests
4. Run the test suite:
   ```bash
   cd api && python -m pytest test_system.py -v
   python -m pytest ../tests/test_fuzz_security.py -v
   ```
5. Submit a pull request

Please follow the existing code style and ensure all tests pass before submitting.

---

## License

MIT

---

<p align="center">
  <strong>WordAddress</strong> — Every 3.5 m² of Earth, named in three words.
</p>
