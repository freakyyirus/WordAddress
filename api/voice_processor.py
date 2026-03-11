"""
Voice Processor for Open3Words
Handles audio transcription via local Whisper or fallback to cloud.
Extracts 3-word addresses from natural speech.
"""

import re
import os
import tempfile
import asyncio
from typing import Optional, Dict
from dataclasses import dataclass

try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False


@dataclass
class VoiceResult:
    text: str
    confidence: float
    detected_language: str
    processed_words: Optional[str] = None
    coordinates: Optional[dict] = None
    method: str = "whisper"
    offline: bool = False


class VoiceProcessor:
    """
    Processes voice audio to extract 3-word addresses.
    Supports local Whisper server and speech pattern recognition.
    """

    def __init__(
        self,
        whisper_url: str = "http://localhost:9000/asr",
        ollama_url: str = "http://localhost:11434/api/generate",
    ):
        self.whisper_url = os.environ.get("WHISPER_URL", whisper_url)
        self.ollama_url = os.environ.get("OLLAMA_URL", ollama_url)

        # Patterns to extract 3-word addresses from speech
        self.location_patterns = [
            # Direct 3-word patterns
            r"(\w+)\s*(?:dot|point|\.)\s*(\w+)\s*(?:dot|point|\.)\s*(\w+)",
            # "I'm at X Y Z"
            r"(?:i'?m\s+at|location\s+is|find|navigate\s+to|go\s+to)\s+(\w+)\s+(\w+)\s+(\w+)",
            # Raw 3 words with separators
            r"^(\w+)[.\s]+(\w+)[.\s]+(\w+)$",
        ]

    async def transcribe_audio(self, audio_bytes: bytes, filename: str = "audio.wav") -> Dict:
        """
        Send audio to local Whisper service for transcription.
        """
        if not HAS_AIOHTTP:
            return {"text": "", "error": "aiohttp not installed"}

        tmp_path = None
        try:
            # Save to temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name

            async with aiohttp.ClientSession() as session:
                with open(tmp_path, "rb") as f:
                    data = aiohttp.FormData()
                    data.add_field("audio_file", f, filename=filename, content_type="audio/wav")
                    data.add_field("language", "en")

                    async with session.post(
                        self.whisper_url,
                        data=data,
                        timeout=aiohttp.ClientTimeout(total=30),
                    ) as response:
                        if response.status != 200:
                            error_text = await response.text()
                            return {"text": "", "error": f"Whisper error: {error_text}"}
                        return await response.json()

        except aiohttp.ClientError as e:
            return {"text": "", "error": f"Connection error: {str(e)}"}
        except Exception as e:
            return {"text": "", "error": str(e)}
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

    async def ai_extract_location(self, transcript: str) -> Dict:
        """
        Use local LLM (Ollama) to extract 3-word address from complex speech.
        """
        if not HAS_AIOHTTP:
            return {"extracted_words": None, "confidence": 0.0, "error": "aiohttp not installed"}

        prompt = (
            "You are a location extraction AI. Extract the 3-word address from this speech transcript.\n"
            "If the user says 3 words separated by 'dot', 'point', or pauses, combine them.\n"
            f'Transcript: "{transcript}"\n\n'
            "Rules:\n"
            "1. Return ONLY the 3-word address in format: word1.word2.word3\n"
            "2. If unclear, return: UNCLEAR\n"
            "3. Remove filler words like 'um', 'uh'\n"
            "4. Handle common mispronunciations\n\n"
            "Response:"
        )

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.ollama_url,
                    json={
                        "model": "phi3:mini",
                        "prompt": prompt,
                        "stream": False,
                        "options": {"temperature": 0.1},
                    },
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        extracted = result.get("response", "").strip().lower()

                        if re.match(r"^[a-z]+\.[a-z]+\.[a-z]+$", extracted):
                            return {
                                "extracted_words": extracted,
                                "confidence": 0.9,
                                "method": "ai_extraction",
                            }
                        return {
                            "extracted_words": None,
                            "confidence": 0.0,
                            "method": "ai_failed",
                            "raw_response": extracted,
                        }
                    return {"extracted_words": None, "confidence": 0.0, "error": "LLM unavailable"}

        except Exception as e:
            return {"extracted_words": None, "confidence": 0.0, "error": str(e)}

    def extract_direct_pattern(self, text: str) -> Optional[str]:
        """
        Fast regex extraction for obvious 3-word patterns in speech.
        """
        text = text.lower().strip()

        for pattern in self.location_patterns:
            match = re.search(pattern, text)
            if match:
                groups = match.groups()
                if len(groups) == 3:
                    return f"{groups[0]}.{groups[1]}.{groups[2]}"

        return None

    async def process_voice(self, audio_bytes: bytes, filename: str = "audio.wav") -> VoiceResult:
        """
        Full pipeline: Audio → Whisper → Pattern Extraction → Optional AI → Result
        """
        # Step 1: Transcribe
        transcription = await self.transcribe_audio(audio_bytes, filename)
        raw_text = transcription.get("text", "").strip()

        if not raw_text:
            return VoiceResult(
                text="",
                confidence=0.0,
                detected_language="unknown",
                method="failed",
            )

        # Step 2: Try direct pattern matching (fast)
        direct_match = self.extract_direct_pattern(raw_text)
        if direct_match:
            return VoiceResult(
                text=raw_text,
                confidence=0.95,
                detected_language=transcription.get("language", "en"),
                processed_words=direct_match,
                method="pattern_match",
            )

        # Step 3: Use AI for complex extraction
        ai_result = await self.ai_extract_location(raw_text)
        return VoiceResult(
            text=raw_text,
            confidence=ai_result.get("confidence", 0.3),
            detected_language=transcription.get("language", "en"),
            processed_words=ai_result.get("extracted_words"),
            method=ai_result.get("method", "ai_extraction"),
        )
