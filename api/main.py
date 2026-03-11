"""
Open3Words — Main FastAPI Application
Production-ready API for encoding, decoding, voice, AI, and assistant endpoints.
"""

import json
import os
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, UploadFile, File, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from location_encoder import LocationEncoder
from error_correction import ErrorCorrector
from voice_processor import VoiceProcessor, VoiceResult
from ai_location_engine import AILocationEngine
from location_assistant import LocationAssistant

# ── Optional Redis ───────────────────────────────────────────
try:
    import redis
    REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
    redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    redis_client.ping()
    HAS_REDIS = True
except Exception:
    redis_client = None
    HAS_REDIS = False

# ── App setup ────────────────────────────────────────────────
app = FastAPI(
    title="Open3Words API",
    description="A What3Words-style 3-word location encoding system with AI, voice, and smart features.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Initialize components ────────────────────────────────────
encoder = LocationEncoder()
corrector = ErrorCorrector(encoder.wordlist)
voice_processor = VoiceProcessor()
ai_engine = AILocationEngine()
assistant = LocationAssistant()


# ── Pydantic models ──────────────────────────────────────────

class CoordsRequest(BaseModel):
    lat: float = Field(..., ge=-90, le=90, description="Latitude")
    lon: float = Field(..., ge=-180, le=180, description="Longitude")


class WordsRequest(BaseModel):
    words: str = Field(..., description="3-word address (e.g., 'table.chair.lamp')")


class CorrectionRequest(BaseModel):
    address: str = Field(..., description="Possibly misspelled 3-word address")


class NLQueryRequest(BaseModel):
    query: str = Field(..., description="Natural language location description")
    context_id: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None


class AssistantRequest(BaseModel):
    user_id: str = Field(..., description="User identifier")
    query: str = Field(..., description="User query")
    lat: Optional[float] = None
    lon: Optional[float] = None


class NavigationRequest(BaseModel):
    from_lat: float
    from_lon: float
    to_lat: float
    to_lon: float


# ── Health check ─────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "wordlist_size": encoder.word_count,
        "addressable_cells": encoder.word_count ** 3,
        "redis_connected": HAS_REDIS,
    }


# ── Core: Encode / Decode ───────────────────────────────────

@app.post("/encode")
async def encode_coordinates(coords: CoordsRequest):
    """Convert lat/lon to a 3-word address."""
    cache_key = f"enc:{coords.lat:.6f}:{coords.lon:.6f}"

    # Check cache
    if HAS_REDIS:
        cached = redis_client.get(cache_key)
        if cached:
            return json.loads(cached)

    try:
        words = encoder.encode(coords.lat, coords.lon)
        grid = encoder.get_grid_square(coords.lat, coords.lon)
        result = {
            "words": words,
            "coordinates": {"lat": coords.lat, "lon": coords.lon},
            "grid": grid,
            "language": "en",
        }

        if HAS_REDIS:
            redis_client.setex(cache_key, 86400, json.dumps(result))

        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/decode")
async def decode_words(request: WordsRequest):
    """Convert a 3-word address to lat/lon."""
    words = request.words.lower().strip().replace(" ", ".")
    if words.startswith("///"):
        words = words[3:]

    parts = words.split(".")
    if len(parts) != 3:
        raise HTTPException(status_code=400, detail="Must be exactly 3 words separated by dots")

    cache_key = f"dec:{words}"
    if HAS_REDIS:
        cached = redis_client.get(cache_key)
        if cached:
            return json.loads(cached)

    try:
        lat, lon = encoder.decode(words)
        grid = encoder.get_grid_square(lat, lon)
        result = {
            "words": words,
            "coordinates": {"lat": lat, "lon": lon},
            "grid": grid,
            "language": "en",
        }

        if HAS_REDIS:
            redis_client.setex(cache_key, 86400, json.dumps(result))

        return result

    except ValueError as e:
        raise HTTPException(status_code=404, detail=f"Address not found: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Autosuggest ──────────────────────────────────────────────

@app.get("/autosuggest")
async def autosuggest(
    partial: str = Query(..., description="Partial 3-word address"),
    focus_lat: Optional[float] = Query(None),
    focus_lon: Optional[float] = Query(None),
    limit: int = Query(5, ge=1, le=20),
):
    """Suggest valid address completions based on partial input."""
    partial = partial.lower().strip()
    parts = partial.split(".")

    suggestions = []

    if len(parts) == 1:
        # Suggest completions for first word
        matches = corrector.suggest_completions(parts[0], limit=limit)
        for w in matches:
            suggestions.append({"words": f"{w}.*.*", "type": "partial"})

    elif len(parts) == 2:
        # Suggest completions for second word
        matches = corrector.suggest_completions(parts[1] if parts[1] else "", limit=limit)
        for w in matches:
            suggestions.append({"words": f"{parts[0]}.{w}.*", "type": "partial"})

    elif len(parts) == 3:
        # Suggest completions for third word
        matches = corrector.suggest_completions(parts[2] if parts[2] else "", limit=limit)
        for w in matches:
            address = f"{parts[0]}.{parts[1]}.{w}"
            try:
                lat, lon = encoder.decode(address)
                suggestions.append({
                    "words": address,
                    "coordinates": {"lat": lat, "lon": lon},
                    "type": "complete",
                })
            except Exception:
                suggestions.append({"words": address, "type": "unverified"})

    return {"suggestions": suggestions[:limit], "partial": partial}


# ── Error correction ─────────────────────────────────────────

@app.post("/correct")
async def correct_address(request: CorrectionRequest):
    """AI-powered error correction for mistyped addresses."""
    suggestions = corrector.correct_address(request.address)
    decoded_suggestions = []

    for s in suggestions:
        try:
            lat, lon = encoder.decode(s["words"])
            s["coordinates"] = {"lat": lat, "lon": lon}
        except Exception:
            s["coordinates"] = None
        decoded_suggestions.append(s)

    return {
        "input": request.address,
        "suggestions": decoded_suggestions,
        "auto_correct": decoded_suggestions[0] if decoded_suggestions else None,
    }


# ── Voice ────────────────────────────────────────────────────

@app.post("/voice/decode")
async def decode_voice(audio: UploadFile = File(...)):
    """Upload an audio file to extract a 3-word address."""
    allowed_types = {"audio/wav", "audio/mpeg", "audio/mp4", "audio/webm", "audio/ogg", "application/octet-stream"}
    if audio.content_type and audio.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail=f"Unsupported audio type: {audio.content_type}")

    audio_bytes = await audio.read()
    if len(audio_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty audio file")
    if len(audio_bytes) > 25 * 1024 * 1024:  # 25 MB limit
        raise HTTPException(status_code=413, detail="Audio file too large (max 25MB)")

    result = await voice_processor.process_voice(audio_bytes, audio.filename or "audio.wav")

    # If words were extracted, decode them
    response = {
        "text": result.text,
        "confidence": result.confidence,
        "detected_language": result.detected_language,
        "processed_words": result.processed_words,
        "method": result.method,
    }

    if result.processed_words:
        try:
            lat, lon = encoder.decode(result.processed_words)
            response["coordinates"] = {"lat": lat, "lon": lon}
        except Exception:
            response["coordinates"] = None

    return response


# ── AI / Natural Language ────────────────────────────────────

@app.post("/ai/parse-location")
async def parse_natural_language(request: NLQueryRequest):
    """
    Convert natural language to coordinates using local AI.
    Example: "the coffee shop near central park" → coordinates + 3-word address
    """
    user_loc = (request.lat, request.lon) if request.lat and request.lon else None
    result = await ai_engine.natural_language_to_location(
        request.query, request.context_id, user_loc
    )

    # If we got coordinates, also encode them
    if result.get("success") and result.get("coordinates"):
        coords = result["coordinates"]
        try:
            words = encoder.encode(coords["lat"], coords["lon"])
            result["words"] = words
        except Exception:
            pass

    return result


@app.post("/ai/suggest")
async def ai_suggestions(
    partial: str = Query(...),
    intent: str = Query("general"),
    limit: int = Query(5, ge=1, le=10),
):
    """AI-powered smart suggestions based on partial input and user intent."""
    suggestions = await ai_engine.smart_suggestions(partial, intent, limit)
    return {"suggestions": suggestions, "partial": partial, "intent": intent}


# ── Assistant ────────────────────────────────────────────────

@app.post("/assistant/query")
async def assistant_query(request: AssistantRequest):
    """
    Smart location assistant.
    Examples:
    - "Take me to the nearest hospital"
    - "Save this location as home"
    - "Share my location"
    """
    current = (request.lat, request.lon) if request.lat and request.lon else None
    result = await assistant.process_query(request.user_id, request.query, current)
    return result


@app.post("/assistant/navigate")
async def get_navigation(request: NavigationRequest):
    """Get navigation info between two points."""
    from_loc = (request.from_lat, request.from_lon)
    to_loc = (request.to_lat, request.to_lon)
    nav = assistant.get_navigation_info(from_loc, to_loc)

    # Encode both locations
    try:
        from_words = encoder.encode(request.from_lat, request.from_lon)
        to_words = encoder.encode(request.to_lat, request.to_lon)
        nav["from_words"] = from_words
        nav["to_words"] = to_words
    except Exception:
        pass

    return nav


# ── Precision info ───────────────────────────────────────────

@app.get("/precision")
async def get_precision(lat: float = Query(0.0, ge=-90, le=90)):
    """Get grid precision in meters at a given latitude."""
    return encoder.precision_meters(lat)


# ── Languages (basic — see /languages below for multi-lang) ──
# NOTE: The enhanced /languages endpoint with multi-language support
# is defined further below, after the multi-language manager is loaded.
# This original endpoint is kept as /languages/basic for backward compat.

@app.get("/languages/basic")
async def get_languages_basic():
    """List available languages (basic, English only)."""
    return {
        "languages": [
            {"code": "en", "name": "English", "native_name": "English"},
        ]
    }


# ── WebSocket for real-time voice streaming ──────────────────

@app.websocket("/voice/stream")
async def voice_stream(websocket: WebSocket):
    """
    WebSocket endpoint for real-time voice streaming.
    Client sends audio chunks, server returns interim and final transcriptions.
    """
    await websocket.accept()
    buffer = bytearray()

    try:
        while True:
            message = await websocket.receive()

            if "bytes" in message:
                buffer.extend(message["bytes"])

                # Process when enough audio is buffered (~3 seconds at 16kHz, 16-bit mono)
                if len(buffer) > 96000:
                    result = await voice_processor.process_voice(bytes(buffer))
                    await websocket.send_json({
                        "type": "interim",
                        "text": result.text,
                        "words": result.processed_words,
                        "confidence": result.confidence,
                    })

            elif "text" in message:
                data = json.loads(message["text"])
                if data.get("action") == "finalize":
                    if buffer:
                        result = await voice_processor.process_voice(bytes(buffer))
                        response = {
                            "type": "final",
                            "text": result.text,
                            "words": result.processed_words,
                            "confidence": result.confidence,
                        }
                        if result.processed_words:
                            try:
                                lat, lon = encoder.decode(result.processed_words)
                                response["coordinates"] = {"lat": lat, "lon": lon}
                            except Exception:
                                pass
                        await websocket.send_json(response)
                    buffer = bytearray()

                elif data.get("action") == "reset":
                    buffer = bytearray()

    except WebSocketDisconnect:
        pass


# ══════════════════════════════════════════════════════════════
# NEW FEATURES — S2/H3 Encoders, LFSR, Multi-Language, Fuzzy
#                Blockchain, GET endpoints, Suggest endpoint
# ══════════════════════════════════════════════════════════════

# ── Optional: S2 Geometry Encoder ────────────────────────────
try:
    from s2_encoder import S2Encoder
    s2_encoder = S2Encoder()
    HAS_S2 = True
except Exception:
    s2_encoder = None
    HAS_S2 = False

# ── Optional: H3 Hexagonal Encoder ──────────────────────────
try:
    from h3_encoder import H3Encoder
    h3_encoder = H3Encoder()
    HAS_H3 = True
except Exception:
    h3_encoder = None
    HAS_H3 = False

# ── Multi-Language Manager ───────────────────────────────────
try:
    from multi_language import MultiLanguageManager
    lang_manager = MultiLanguageManager()
    HAS_MULTILANG = True
except Exception:
    lang_manager = None
    HAS_MULTILANG = False

# ── Enhanced Fuzzy Search Engine ─────────────────────────────
try:
    from fuzzy_search import FuzzySearchEngine
    fuzzy_engine = FuzzySearchEngine(encoder.wordlist)
    HAS_FUZZY = True
except Exception:
    fuzzy_engine = None
    HAS_FUZZY = False

# ── Blockchain Verifier ─────────────────────────────────────
try:
    from blockchain_verification import BlockchainVerifier
    blockchain = BlockchainVerifier()
    HAS_BLOCKCHAIN = True
except Exception:
    blockchain = None
    HAS_BLOCKCHAIN = False

# ── LFSR Scrambler (informational) ──────────────────────────
try:
    from lfsr_scrambler import LFSRScrambler
    HAS_LFSR = True
except Exception:
    HAS_LFSR = False


# ── Pydantic models for new endpoints ───────────────────────

class SuggestRequest(BaseModel):
    code: str = Field(..., description="Partial or mistyped 3-word address")
    lang: str = Field("en", description="Language code")


class BlockchainProofRequest(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    words: str
    witnesses_required: int = Field(1, ge=1, le=10)


class BlockchainWitnessRequest(BaseModel):
    proof_id: str


# ── GET /encode — alternative GET endpoint ───────────────────

@app.get("/encode")
async def encode_get(
    lat: float = Query(..., ge=-90, le=90, description="Latitude"),
    lon: float = Query(..., ge=-180, le=180, description="Longitude"),
    lang: str = Query("en", description="Language code"),
    grid: str = Query("default", description="Grid system: default, s2, h3"),
):
    """
    GET alternative for encoding. Same as POST /encode but via query params.
    Supports multiple grid systems (default Z-order, S2, H3).
    """
    cache_key = f"enc:{lat:.6f}:{lon:.6f}:{lang}:{grid}"
    if HAS_REDIS:
        cached = redis_client.get(cache_key)
        if cached:
            return json.loads(cached)

    try:
        if grid == "s2" and HAS_S2:
            words = s2_encoder.encode(lat, lon)
            grid_info = s2_encoder.get_cell_info(lat, lon)
        elif grid == "h3" and HAS_H3:
            words = h3_encoder.encode(lat, lon)
            grid_info = h3_encoder.get_cell_info(lat, lon)
        elif lang != "en" and HAS_MULTILANG:
            words = lang_manager.encode(lat, lon, lang)
            grid_info = encoder.get_grid_square(lat, lon)
        else:
            words = encoder.encode(lat, lon)
            grid_info = encoder.get_grid_square(lat, lon)

        result = {
            "words": words,
            "coordinates": {"lat": lat, "lon": lon},
            "grid": grid_info,
            "language": lang,
            "grid_system": grid,
        }

        if HAS_REDIS:
            redis_client.setex(cache_key, 86400, json.dumps(result))

        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── GET /decode — alternative GET endpoint ───────────────────

@app.get("/decode")
async def decode_get(
    code: str = Query(..., description="3-word address (dot-separated)"),
    lang: str = Query("en", description="Language code"),
    grid: str = Query("default", description="Grid system: default, s2, h3"),
):
    """
    GET alternative for decoding. Accepts ?code=word1.word2.word3
    """
    words = code.lower().strip().replace(" ", ".")
    if words.startswith("///"):
        words = words[3:]

    parts = words.split(".")
    if len(parts) != 3:
        raise HTTPException(status_code=400, detail="Must be exactly 3 words separated by dots")

    try:
        if grid == "s2" and HAS_S2:
            lat, lon = s2_encoder.decode(words)
        elif grid == "h3" and HAS_H3:
            lat, lon = h3_encoder.decode(words)
        elif lang != "en" and HAS_MULTILANG:
            lat, lon = lang_manager.decode(words, lang)
        else:
            lat, lon = encoder.decode(words)

        return {
            "words": words,
            "coordinates": {"lat": lat, "lon": lon},
            "language": lang,
            "grid_system": grid,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── GET /suggest — fuzzy suggestion endpoint ─────────────────

@app.get("/suggest")
async def suggest(
    code: str = Query(..., description="Partial or mistyped 3-word address"),
    lang: str = Query("en", description="Language code"),
    limit: int = Query(5, ge=1, le=20),
):
    """
    Given a partial or misspelled code, return the closest valid codes.
    Useful for client-side error correction and autocomplete.
    """
    code = code.lower().strip().replace("///", "")

    # If it looks like a complete address, do fuzzy correction
    parts = code.split(".")
    suggestions = []

    if len(parts) == 3 and HAS_FUZZY:
        raw = fuzzy_engine.suggest_for_address(code, limit)
        for s in raw:
            try:
                lat, lon = encoder.decode(s["words"])
                s["coordinates"] = {"lat": lat, "lon": lon}
            except Exception:
                s["coordinates"] = None
            suggestions.append(s)
    elif HAS_FUZZY:
        # Partial input — autocomplete the last incomplete word
        last = parts[-1] if parts else code
        completions = fuzzy_engine.autocomplete(last, limit)
        for w in completions:
            if len(parts) >= 2:
                full = ".".join(parts[:-1]) + "." + w
            else:
                full = w
            suggestions.append({"words": full, "score": 80, "type": "autocomplete"})
    else:
        # Fallback to existing corrector
        raw = corrector.correct_address(code)[:limit]
        for s in raw:
            try:
                lat, lon = encoder.decode(s["words"])
                s["coordinates"] = {"lat": lat, "lon": lon}
            except Exception:
                s["coordinates"] = None
            suggestions.append(s)

    return {
        "suggestions": suggestions[:limit],
        "input": code,
        "language": lang,
    }


# ── POST /suggest — JSON body variant ────────────────────────

@app.post("/suggest")
async def suggest_post(request: SuggestRequest):
    """POST variant of /suggest for richer payloads."""
    code = request.code.lower().strip().replace("///", "")
    lang = request.lang

    suggestions = []
    if HAS_FUZZY:
        raw = fuzzy_engine.suggest_for_address(code, 5)
        for s in raw:
            try:
                lat, lon = encoder.decode(s["words"])
                s["coordinates"] = {"lat": lat, "lon": lon}
            except Exception:
                s["coordinates"] = None
            suggestions.append(s)

    return {"suggestions": suggestions, "input": code, "language": lang}


# ── S2 Geometry endpoints ────────────────────────────────────

@app.get("/s2/encode")
async def s2_encode(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
):
    """Encode coordinates using S2 Geometry grid."""
    if not HAS_S2:
        raise HTTPException(status_code=501, detail="S2 encoder not available (install s2sphere)")
    try:
        words = s2_encoder.encode(lat, lon)
        info = s2_encoder.get_cell_info(lat, lon)
        return {"words": words, "coordinates": {"lat": lat, "lon": lon}, "cell": info, "grid_system": "s2"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/s2/decode")
async def s2_decode(code: str = Query(...)):
    """Decode an S2-encoded 3-word address."""
    if not HAS_S2:
        raise HTTPException(status_code=501, detail="S2 encoder not available")
    try:
        lat, lon = s2_encoder.decode(code)
        return {"words": code, "coordinates": {"lat": lat, "lon": lon}, "grid_system": "s2"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/s2/neighbors")
async def s2_neighbors(lat: float = Query(...), lon: float = Query(...)):
    """Get neighboring S2 cell addresses."""
    if not HAS_S2:
        raise HTTPException(status_code=501, detail="S2 encoder not available")
    try:
        neighbors = s2_encoder.get_neighbors(lat, lon)
        return {"center": s2_encoder.encode(lat, lon), "neighbors": neighbors}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── H3 Hexagonal endpoints ──────────────────────────────────

@app.get("/h3/encode")
async def h3_encode(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
):
    """Encode coordinates using H3 hexagonal grid."""
    if not HAS_H3:
        raise HTTPException(status_code=501, detail="H3 encoder not available (install h3)")
    try:
        words = h3_encoder.encode(lat, lon)
        info = h3_encoder.get_cell_info(lat, lon)
        return {"words": words, "coordinates": {"lat": lat, "lon": lon}, "cell": info, "grid_system": "h3"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/h3/decode")
async def h3_decode(code: str = Query(...)):
    """Decode an H3-encoded 3-word address."""
    if not HAS_H3:
        raise HTTPException(status_code=501, detail="H3 encoder not available")
    try:
        lat, lon = h3_encoder.decode(code)
        return {"words": code, "coordinates": {"lat": lat, "lon": lon}, "grid_system": "h3"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/h3/neighbors")
async def h3_neighbors(lat: float = Query(...), lon: float = Query(...)):
    """Get neighboring H3 hexagonal cell addresses."""
    if not HAS_H3:
        raise HTTPException(status_code=501, detail="H3 encoder not available")
    try:
        neighbors = h3_encoder.get_neighbors(lat, lon)
        return {"center": h3_encoder.encode(lat, lon), "neighbors": neighbors}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/h3/boundary")
async def h3_boundary(lat: float = Query(...), lon: float = Query(...)):
    """Get H3 hex cell boundary polygon."""
    if not HAS_H3:
        raise HTTPException(status_code=501, detail="H3 encoder not available")
    try:
        boundary = h3_encoder.get_hex_boundary(lat, lon)
        return {"center": {"lat": lat, "lon": lon}, "boundary": boundary}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Multi-Language endpoints ─────────────────────────────────

@app.get("/languages")
async def get_languages_v2():
    """List all supported languages with availability status."""
    if HAS_MULTILANG:
        return {"languages": lang_manager.list_languages()}
    return {
        "languages": [
            {"code": "en", "name": "English", "native_name": "English", "available": True},
        ]
    }


@app.get("/detect-language")
async def detect_language(code: str = Query(...)):
    """Auto-detect the language of a 3-word address."""
    if not HAS_MULTILANG:
        return {"code": code, "language": "en", "confidence": "default"}
    detected = lang_manager.detect_language(code)
    return {"code": code, "language": detected or "unknown", "confidence": "high" if detected else "none"}


# ── Blockchain Verification endpoints ────────────────────────

@app.post("/blockchain/submit-proof")
async def submit_proof(request: BlockchainProofRequest):
    """Submit a Proof of Location to the blockchain."""
    if not HAS_BLOCKCHAIN:
        return {
            "status": "unavailable",
            "message": "Blockchain not configured. Set WEB3_RPC_URL and CONTRACT_ADDRESS.",
            "location_hash": blockchain.hash_location(request.lat, request.lon, request.words) if blockchain else None,
        }
    tx_hash = blockchain.submit_proof(request.lat, request.lon, request.words, request.witnesses_required)
    return {
        "status": "submitted" if tx_hash else "offline",
        "tx_hash": tx_hash,
        "location_hash": blockchain.hash_location(request.lat, request.lon, request.words),
    }


@app.post("/blockchain/witness")
async def witness_proof(request: BlockchainWitnessRequest):
    """Witness (confirm) an existing Proof of Location."""
    if not HAS_BLOCKCHAIN:
        raise HTTPException(status_code=501, detail="Blockchain not configured")
    tx_hash = blockchain.witness_proof(request.proof_id)
    return {"status": "witnessed" if tx_hash else "failed", "tx_hash": tx_hash}


@app.get("/blockchain/verify")
async def verify_proof(proof_id: str = Query(...)):
    """Check if a proof has been verified on-chain."""
    if not HAS_BLOCKCHAIN:
        raise HTTPException(status_code=501, detail="Blockchain not configured")
    verified = blockchain.verify_proof(proof_id)
    return {"proof_id": proof_id, "verified": verified}


@app.get("/blockchain/reputation")
async def get_reputation(address: str = Query(...)):
    """Query reputation score for a blockchain address."""
    if not HAS_BLOCKCHAIN:
        raise HTTPException(status_code=501, detail="Blockchain not configured")
    score = blockchain.get_reputation(address)
    return {"address": address, "reputation": score}


# ── Enhanced Health Check (updated) ──────────────────────────

@app.get("/health/detailed")
async def health_detailed():
    """Extended health check showing all subsystem statuses."""
    return {
        "status": "healthy",
        "wordlist_size": encoder.word_count,
        "addressable_cells": encoder.word_count ** 3,
        "subsystems": {
            "redis": HAS_REDIS,
            "s2_encoder": HAS_S2,
            "h3_encoder": HAS_H3,
            "multi_language": HAS_MULTILANG,
            "fuzzy_search": HAS_FUZZY,
            "blockchain": HAS_BLOCKCHAIN,
            "lfsr_scrambler": HAS_LFSR,
        },
        "grid_systems": ["default"] + (["s2"] if HAS_S2 else []) + (["h3"] if HAS_H3 else []),
    }


# ── Grid System Comparison endpoint ──────────────────────────

@app.get("/compare-grids")
async def compare_grids(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
):
    """Encode the same location with all available grid systems for comparison."""
    results = {}

    # Default (Z-order + LCG)
    try:
        words = encoder.encode(lat, lon)
        results["default"] = {"words": words, "grid": encoder.get_grid_square(lat, lon)}
    except Exception as e:
        results["default"] = {"error": str(e)}

    # S2
    if HAS_S2:
        try:
            words = s2_encoder.encode(lat, lon)
            results["s2"] = {"words": words, "cell": s2_encoder.get_cell_info(lat, lon)}
        except Exception as e:
            results["s2"] = {"error": str(e)}

    # H3
    if HAS_H3:
        try:
            words = h3_encoder.encode(lat, lon)
            results["h3"] = {"words": words, "cell": h3_encoder.get_cell_info(lat, lon)}
        except Exception as e:
            results["h3"] = {"error": str(e)}

    return {"coordinates": {"lat": lat, "lon": lon}, "results": results}


# ── Serve frontend static files (if build exists) ───────────

frontend_build = os.path.join(os.path.dirname(__file__), "..", "frontend", "build")
if os.path.isdir(frontend_build):
    app.mount("/", StaticFiles(directory=frontend_build, html=True), name="frontend")


# ── Main entry point ─────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
