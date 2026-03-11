# WordAddress Development Guide

A comprehensive phase-by-phase development guide for building an open-source three-word location encoding system.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Prerequisites](#prerequisites)
3. [Phase-wise Development Roadmap](#phase-wise-development-roadmap)
4. [Detailed Phase Guides](#detailed-phase-guides)
5. [Testing Strategy](#testing-strategy)
6. [Deployment Guide](#deployment-guide)
7. [Production Readiness](#production-readiness)

---

## Project Overview

**WordAddress** converts any GPS coordinate into a unique three-word address (e.g., `///forest.morning.river`) with ~3.5m precision.

| Metric | Value |
|--------|-------|
| Grid precision | ~3.5m at equator |
| Wordlist size | 40,000 words |
| Address space | 64 trillion unique cells |
| Supported languages | 9 |

### Core Features
- Three interchangeable grid systems (Z-order, S2, H3)
- Multi-language wordlists with auto-detection
- AI voice input via Whisper
- Conversational AI assistant via Ollama
- Blockchain proof-of-location
- Offline-first PWA with AR navigation

---

## Prerequisites

### Required Tools
```bash
# Core tools
- Python 3.11+
- Node.js 18+
- Docker & Docker Compose
- Git

# Python dependencies (install via requirements.txt)
- FastAPI, Uvicorn, Pydantic
- Redis, SQLAlchemy, asyncpg
- s2sphere, h3, jellyfish, nltk
- web3, httpx, aiohttp

# Frontend dependencies (via npm)
- React 18, MapLibre GL JS
- Three.js, @react-three/fiber, @react-three/xr
- Lucide React
```

### System Requirements
- **Development**: 8GB RAM, multi-core CPU
- **Production (Full)**: 16GB RAM, 4+ CPU cores
- **Production (Minimal)**: 1GB RAM (API + Redis only)

---

## Phase-wise Development Roadmap

### Phase 1: Core Engine (Week 1-2)
- [ ] Implement Z-order encoder (25-bit lat × 26-bit lon)
- [ ] Create 40K wordlist generator
- [ ] Build error correction (Levenshtein, Metaphone, keyboard proximity)
- [ ] Create basic REST API (encode, decode, correct, autosuggest)
- [ ] Write unit tests for round-trip accuracy

### Phase 2: AI, Voice, Blockchain (Week 3-4)
- [ ] Integrate Whisper for speech-to-text
- [ ] Implement Ollama LLM for natural language parsing
- [ ] Build conversational assistant
- [ ] Deploy Solidity smart contract
- [ ] Set up PostGIS database with 6 tables

### Phase 3: Frontend & PWA (Week 5-6)
- [ ] Build React SPA with MapLibre
- [ ] Implement AR navigation
- [ ] Create on-device AI with IndexedDB
- [ ] Configure service worker for offline-first
- [ ] Create PWA manifest

### Phase 4: Alternative Grids (Week 7-8)
- [ ] Implement S2 Geometry encoder
- [ ] Implement H3 hexagonal encoder
- [ ] Build LFSR scrambler
- [ ] Create SCOWL wordlist generator
- [ ] Add multi-language support (9 languages)
- [ ] Implement fuzzy search engine

### Phase 5: Testing & Hardening (Week 9-10)
- [ ] Write Hypothesis fuzz tests
- [ ] Create security tests (SQL injection, XSS)
- [ ] Implement Locust load tests
- [ ] Verify LFSR dispersion quality

### Phase 6: Deployment (Week 11-12)
- [ ] Configure Docker Compose (full stack)
- [ ] Configure Docker Compose (minimal)
- [ ] Set up AWS Lambda deployment
- [ ] Set up Cloudflare Workers
- [ ] Configure Prometheus + Grafana
- [ ] Document environment variables

### Phase 7: Production Hardening (Week 13-16)
- [ ] Implement rate limiting
- [ ] Add JWT/API key authentication
- [ ] Set up HTTPS enforcement
- [ ] Add circuit breakers
- [ ] Implement structured JSON logging
- [ ] Set up CDN for static assets
- [ ] Configure database connection pooling

### Phase 8: Future Enhancements (Ongoing)
- [ ] React Native mobile apps
- [ ] SDK packages (Python, JavaScript, Go)
- [ ] Custom wordlists admin API
- [ ] Address sharing (deep links, QR, NFC)
- [ ] Geocoding integration
- [ ] Horizontal scaling (K8s, Redis Cluster)
- [ ] Multi-region deployment
- [ ] Accessibility audit (WCAG 2.1 AA)
- [ ] Internationalized frontend

---

## Detailed Phase Guides

### Phase 1: Core Engine

#### 1.1 Z-order Encoder Implementation

**File:** `api/location_encoder.py`

The Z-order (Morton) curve interleaves latitude and longitude bits for spatial locality.

```python
# Core algorithm steps:
# 1. Normalize GPS to [0, 1) range
# 2. Quantize: 25-bit latitude × 26-bit longitude
# 3. Apply Z-order interleaving (Morton code)
# 4. LCG shuffle for word dispersion
# 5. Modular factoring → 3 word indices
```

**Key Functions:**
- `encode(lat, lon) -> str` - GPS to three-word address
- `decode(words) -> (lat, lon)` - Three-word address to GPS
- `modular_inverse()` - Extended Euclidean algorithm for reversal

#### 1.2 Wordlist Generator

**File:** `api/wordlist_generator.py`

Generate 40,000 curated English words from 6 categories:
- Nature (trees, animals, weather)
- Places (cities, landmarks)
- Objects (everyday items)
- Actions (verbs)
- Colors
- Numbers

**Filtering:**
- Remove offensive words
- Remove homophones
- Remove compound words > 20 chars
- Ensure uniqueness

#### 1.3 Error Correction

**File:** `api/error_correction.py`

Implement three strategies:
1. **Levenshtein distance** - Edit distance for typo correction
2. **Double Metaphone** - Phonetic matching
3. **Keyboard proximity** - QWERTY layout adjacency

#### 1.4 Basic REST API

**File:** `api/main.py`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/encode` | POST | GPS → three-word address |
| `/decode` | POST | Three-word address → GPS |
| `/correct` | POST | Fix typos in words |
| `/autosuggest` | GET | Autocomplete partial input |

---

### Phase 2: AI, Voice, Blockchain

#### 2.1 Whisper Integration

**File:** `api/voice_processor.py`

```python
# Audio processing pipeline:
# 1. Receive audio file upload
# 2. Send to Whisper ASR service
# 3. Extract 3-word address via regex
# 4. Fallback to LLM if regex fails
```

#### 2.2 Ollama LLM Integration

**File:** `api/ai_location_engine.py`

```python
# Natural language to GPS:
# 1. Receive natural language input
# 2. Send to Ollama (phi3:mini)
# 3. Parse coordinates from response
# 4. Return GPS + three-word address
```

#### 2.3 Conversational Assistant

**File:** `api/location_assistant.py`

Intent classification:
- `navigate` - Get directions between points
- `share` - Generate shareable link
- `save` - Save location to favorites
- `nearby` - Find nearby locations

#### 2.4 Blockchain Verification

**File:** `contracts/Open3WordsProofOfLocation.sol`

Solidity smart contract with:
- `submitProof()` - Submit location proof
- `witnessProof()` - Confirm proof (requires 10+ reputation)
- `grantReputation()` - Admin bootstrap

**File:** `api/blockchain_verification.py`

Python Web3 integration for on-chain verification.

#### 2.5 PostGIS Database

**File:** `init.sql`

Tables:
- `wordlist` - Dictionary storage
- `grid_cells` - Spatial cache
- `word_aliases` - Alternate spellings
- `api_usage` - Request analytics
- `location_proofs` - On-chain proof mirror
- `saved_locations` - User favorites

---

### Phase 3: Frontend & PWA

#### 3.1 React SPA

**File:** `frontend/src/App.js`

Four-tab interface:
1. **Encode** - GPS → three-word address
2. **Decode** - Three-word address → GPS
3. **Voice** - Speech input
4. **Assistant** - Conversational AI

#### 3.2 MapLibre Integration

```javascript
// Map setup:
- Click to encode location
- Fly-to animations
- Markers with popups
- Vector tiles
```

#### 3.3 AR Navigation

**File:** `frontend/src/ARNavigation.js`

- WebXR for AR-capable devices
- 2D compass fallback
- Haversine distance calculation
- Bearing computation

#### 3.4 On-Device AI

**File:** `frontend/src/OnDeviceAI.js`

- IndexedDB caching
- Offline Levenshtein correction
- Background sync queue

#### 3.5 Service Worker

**File:** `frontend/public/service-worker.js`

- Pre-caching static assets
- Network-first for API calls
- Cache-first for map tiles
- Push notification support

---

### Phase 4: Alternative Grids

#### 4.1 S2 Geometry Encoder

**File:** `api/s2_encoder.py`

- Google S2 cells at level 25 (~5m resolution)
- LFSR scrambling
- 6-face decode
- Neighbor lookup

#### 4.2 H3 Hexagonal Encoder

**File:** `api/h3_encoder.py`

- Uber H3 at resolution 12 (~9.4m)
- Boundary GeoJSON output
- Ring-1 neighbors enumeration

#### 4.3 LFSR Scrambler

**File:** `api/lfsr_scrambler.py`

Maximal-length polynomials for bit widths: 15, 16, 20, 24, 28, 30, 32, 36, 40, 42, 45, 48, 51

#### 4.4 Multi-Language Support

**File:** `api/multi_language.py`

Supported languages:
- English (en)
- Spanish (es)
- French (fr)
- German (de)
- Portuguese (pt)
- Japanese (ja)
- Chinese (zh)
- Arabic (ar)
- Hindi (hi)

#### 4.5 Fuzzy Search Engine

**File:** `api/fuzzy_search.py`

- Trie prefix tree
- BK-Tree for edit distance
- Trigram index
- Phonetic index (Soundex + Metaphone)
- Combined weighted ranking

---

### Phase 5: Testing & Hardening

#### 5.1 Unit Tests

**File:** `api/test_system.py`

```bash
cd api
python -m pytest test_system.py -v
```

Test coverage:
- Round-trip accuracy (< 10m error)
- Uniqueness verification
- Determinism checks
- Error correction accuracy

#### 5.2 Fuzz Tests

**File:** `tests/test_fuzz_security.py`

```bash
python -m pytest tests/test_fuzz_security.py -v
```

- 500 random coordinate round-trips
- Boundary coordinates (poles, antimeridian)
- Security payloads (SQL injection, XSS)

#### 5.3 Load Tests

**File:** `tests/test_load.py`

```bash
locust -f tests/test_load.py --host http://localhost:8000
```

Traffic mix:
- Encode: 30%
- Decode: 25%
- Suggest: 15%
- Autosuggest: 10%
- Correct: 10%
- Health: 5%
- Compare-grids: 5%

---

### Phase 6: Deployment

#### 6.1 Docker Compose (Full)

```bash
docker compose up --build
```

Services:
- API (FastAPI)
- Web (nginx)
- PostgreSQL (PostGIS)
- Redis
- Whisper
- Ollama
- Prometheus (optional)
- Grafana (optional)

#### 6.2 Docker Compose (Minimal)

```bash
docker compose -f deploy/docker-compose.minimal.yml up --build
```

Services (for 1GB RAM):
- API (64 MB limit)
- Redis (64 MB limit)

#### 6.3 AWS Lambda

```bash
cd deploy
sam build
sam deploy --guided
```

#### 6.4 Cloudflare Workers

```bash
cd deploy
npx wrangler publish
```

---

### Phase 7: Production Hardening

#### 7.1 Rate Limiting

Add middleware to `api/main.py`:
- Token bucket algorithm
- Per-IP or per-API-key limits
- Configurable thresholds

#### 7.2 Authentication

Implement JWT or API key auth:
- `python-jose` for JWT
- API key generation and storage
- Protected endpoints middleware

#### 7.3 Circuit Breakers

For external services:
- Redis fallback
- Whisper timeout handling
- Ollama retry logic

---

## Testing Strategy

### Test Pyramid

```
       /\
      /  \     E2E Tests (Locust)
     /----\    - Full workflow
    /      \
   /--------\  Integration Tests
  /          \ - API endpoint tests
 /------------\ Unit Tests
/              \ - Core algorithm tests
```

### Running Tests

```bash
# Unit tests
cd api && python -m pytest test_system.py -v

# Fuzz tests
python -m pytest tests/test_fuzz_security.py -v

# Load tests
locust -f tests/test_load.py --host http://localhost:8000
```

### Coverage Targets

| Test Type | Target |
|-----------|--------|
| Unit tests | 80%+ coverage |
| Fuzz tests | 500+ random inputs |
| Load tests | 1000+ concurrent users |

---

## Deployment Guide

### Development Environment

```bash
# Clone repository
git clone https://github.com/your-org/wordaddress.git
cd wordaddress

# Copy environment file
cp .env.example .env

# Start full stack
docker compose up --build

# Access services
# Web UI: http://localhost:3000
# API: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

### Production Environment

1. **Configure environment variables**
2. **Set up HTTPS** (nginx reverse proxy)
3. **Configure rate limiting**
4. **Set up monitoring** (Prometheus + Grafana)
5. **Configure backups** (PostgreSQL)

---

## Production Readiness Checklist

### Security
- [ ] CORS middleware
- [ ] Pydantic validation
- [ ] SQL injection protection
- [ ] XSS protection
- [ ] No secrets in source
- [ ] Rate limiting
- [ ] JWT/API key auth
- [ ] HTTPS enforcement

### Reliability
- [ ] Redis fallback
- [ ] Whisper/Ollama optional
- [ ] Docker health checks
- [ ] Service worker offline
- [ ] Circuit breakers
- [ ] Structured logging

### Performance
- [ ] Redis caching
- [ ] Uvicorn workers
- [ ] Load testing
- [ ] Static caching
- [ ] CDN for assets
- [ ] Connection pooling

### Observability
- [ ] Health endpoints
- [ ] Prometheus metrics
- [ ] Grafana dashboards
- [ ] Analytics table
- [ ] Distributed tracing
- [ ] Error tracking

---

## Quick Reference

### API Endpoints

| Category | Endpoints |
|----------|-----------|
| Core | `/encode`, `/decode`, `/correct`, `/autosuggest` |
| Grids | `/s2/*`, `/h3/*`, `/compare-grids` |
| Voice | `/voice/decode`, `/voice/stream` (WS) |
| AI | `/ai/parse-location`, `/ai/suggest`, `/assistant/*` |
| Blockchain | `/blockchain/submit-proof`, `/blockchain/witness` |
| Utility | `/health`, `/health/detailed`, `/languages` |

### File Structure

```
wordaddress/
├── api/                    # Python backend
│   ├── main.py            # FastAPI app
│   ├── location_encoder.py
│   ├── s2_encoder.py
│   ├── h3_encoder.py
│   ├── voice_processor.py
│   ├── ai_location_engine.py
│   └── ...
├── frontend/              # React frontend
│   ├── src/
│   │   ├── App.js
│   │   ├── ARNavigation.js
│   │   └── OnDeviceAI.js
│   └── public/
│       └── service-worker.js
├── contracts/            # Solidity contracts
├── deploy/               # Deployment configs
├── tests/                # Advanced tests
└── docker-compose.yml
```

---

## License

MIT License - See LICENSE file for details.
