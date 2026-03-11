"""
AI Location Engine for Open3Words
Converts natural language descriptions to/from 3-word addresses.
Uses local LLM (Ollama) for zero-cost, private AI processing.
"""

import re
import os
from typing import Dict, List, Optional, Tuple

try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False


class AILocationEngine:
    """
    AI-powered natural language location understanding.

    Examples:
    - "the cafe near Central Park" → finds matching address
    - "200 meters north of my location" → computes relative position
    - Contextual suggestions based on user intent
    """

    def __init__(self, ollama_url: str = "http://localhost:11434/api/generate"):
        self.ollama_url = os.environ.get("OLLAMA_URL", ollama_url)
        self.model = os.environ.get("OLLAMA_MODEL", "phi3:mini")
        self.contexts: Dict[str, dict] = {}  # Per-user conversation context

    async def natural_language_to_location(
        self,
        query: str,
        context_id: Optional[str] = None,
        user_location: Optional[Tuple[float, float]] = None,
    ) -> Dict:
        """
        Convert a natural language description into a structured location result.
        """
        if not HAS_AIOHTTP:
            return {"success": False, "error": "aiohttp not installed"}

        # Build context
        context_str = ""
        if context_id and context_id in self.contexts:
            ctx = self.contexts[context_id]
            context_str = f"Previous context: {ctx}\n"
        if user_location:
            context_str += f"User is currently at coordinates: ({user_location[0]}, {user_location[1]})\n"

        prompt = (
            "You are a location intelligence AI.\n"
            "Given a natural language query, extract the most likely geographic coordinates.\n\n"
            f"{context_str}"
            f'User query: "{query}"\n\n'
            "Instructions:\n"
            "1. Identify the location type: landmark, relative, address, or general area\n"
            "2. Estimate the latitude and longitude\n"
            "3. Provide a confidence score\n\n"
            "IMPORTANT: Respond with ONLY a JSON object in this exact format:\n"
            '{"lat": 51.5074, "lon": -0.1278, "confidence": 0.85, '
            '"location_type": "landmark", "explanation": "Brief reason"}\n\n'
            "Response:"
        )

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.ollama_url,
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "format": "json",
                        "stream": False,
                        "options": {"temperature": 0.2},
                    },
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        raw = result.get("response", "{}")

                        import json
                        try:
                            ai_response = json.loads(raw)
                        except json.JSONDecodeError:
                            return {"success": False, "error": "Invalid AI response", "raw": raw}

                        lat = ai_response.get("lat")
                        lon = ai_response.get("lon")

                        if lat is not None and lon is not None:
                            # Update context
                            if context_id:
                                self.contexts[context_id] = {
                                    "last_query": query,
                                    "last_coords": (lat, lon),
                                }

                            return {
                                "success": True,
                                "coordinates": {"lat": lat, "lon": lon},
                                "confidence": ai_response.get("confidence", 0.5),
                                "location_type": ai_response.get("location_type", "unknown"),
                                "explanation": ai_response.get("explanation", ""),
                                "method": "ai_nl_processing",
                            }

                        return {"success": False, "error": "No coordinates in AI response"}
                    return {"success": False, "error": f"LLM returned status {response.status}"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def smart_suggestions(
        self,
        partial: str,
        user_intent: str = "general",
        limit: int = 5,
    ) -> List[Dict]:
        """
        AI-powered autocomplete suggestions based on partial input and intent.
        """
        if not HAS_AIOHTTP:
            return []

        prompt = (
            f'Given partial input "{partial}" and user intent "{user_intent}", '
            f"suggest {limit} most likely location descriptions.\n\n"
            "Intent categories:\n"
            "- navigation: User wants to go somewhere\n"
            "- sharing: User wants to tell someone where they are\n"
            "- emergency: User needs urgent help\n"
            "- exploration: User is browsing\n\n"
            "Respond with a JSON array of objects with 'description' and 'confidence' keys.\n"
            "Response:"
        )

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.ollama_url,
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "format": "json",
                        "stream": False,
                    },
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        import json
                        try:
                            suggestions = json.loads(result.get("response", "[]"))
                            if isinstance(suggestions, list):
                                return suggestions[:limit]
                        except json.JSONDecodeError:
                            pass
            return []
        except Exception:
            return []

    def clear_context(self, context_id: str):
        """Clear conversation context for a user."""
        self.contexts.pop(context_id, None)
