"""
Location Assistant for Open3Words
Context-aware AI assistant that understands navigation, sharing, and search intents.
"""

import math
from typing import Dict, List, Optional, Tuple


class LocationAssistant:
    """
    Smart location assistant with:
    - Navigation routing
    - Distance/direction calculation
    - User context memory
    - Intent classification
    """

    def __init__(self):
        self.user_contexts: Dict[str, dict] = {}

    async def process_query(
        self,
        user_id: str,
        query: str,
        current_location: Optional[Tuple[float, float]] = None,
    ) -> Dict:
        """Main assistant interface."""

        # Get or create user context
        if user_id not in self.user_contexts:
            self.user_contexts[user_id] = {
                "history": [],
                "favorites": [],
                "common_locations": {},
            }

        ctx = self.user_contexts[user_id]
        ctx["history"].append({"query": query, "location": current_location})

        # Keep history bounded
        if len(ctx["history"]) > 100:
            ctx["history"] = ctx["history"][-50:]

        intent = self._classify_intent(query)

        handlers = {
            "navigate": self._handle_navigation,
            "share": self._handle_share,
            "save": self._handle_save,
            "nearby": self._handle_nearby,
        }
        handler = handlers.get(intent, self._handle_general)
        return await handler(query, ctx, current_location)

    # ── Intent classification ────────────────────────────────

    @staticmethod
    def _classify_intent(query: str) -> str:
        """Rule-based intent classification (fast, no LLM needed)."""
        q = query.lower()
        if any(kw in q for kw in ("navigate", "go to", "take me", "drive to", "walk to", "directions")):
            return "navigate"
        if any(kw in q for kw in ("share", "send", "tell")):
            return "share"
        if any(kw in q for kw in ("save", "bookmark", "remember", "favorite")):
            return "save"
        if any(kw in q for kw in ("nearby", "near me", "closest", "nearest", "around")):
            return "nearby"
        return "general"

    # ── Handlers ─────────────────────────────────────────────

    async def _handle_navigation(self, query: str, ctx: dict, loc: Optional[Tuple]) -> Dict:
        return {
            "intent": "navigation",
            "response": "Navigation support requires a destination. Provide a 3-word address or tap on the map.",
            "current_location": loc,
        }

    async def _handle_share(self, query: str, ctx: dict, loc: Optional[Tuple]) -> Dict:
        if loc:
            return {
                "intent": "share",
                "response": f"Your current location is ({loc[0]:.6f}, {loc[1]:.6f}). Encode it to get a shareable 3-word address.",
                "coordinates": {"lat": loc[0], "lon": loc[1]},
            }
        return {
            "intent": "share",
            "response": "Enable location services to share your position.",
        }

    async def _handle_save(self, query: str, ctx: dict, loc: Optional[Tuple]) -> Dict:
        # Extract label from query (e.g., "save as home")
        label = "unnamed"
        for keyword in ("as ", "called ", "named "):
            if keyword in query.lower():
                label = query.lower().split(keyword, 1)[1].strip()
                break

        if loc:
            ctx["favorites"].append({"label": label, "lat": loc[0], "lon": loc[1]})
            return {
                "intent": "save",
                "response": f"Location saved as '{label}'.",
                "saved": {"label": label, "lat": loc[0], "lon": loc[1]},
            }
        return {"intent": "save", "response": "No location to save. Enable GPS first."}

    async def _handle_nearby(self, query: str, ctx: dict, loc: Optional[Tuple]) -> Dict:
        return {
            "intent": "nearby",
            "response": "Nearby search requires location services and a POI database.",
            "current_location": loc,
        }

    async def _handle_general(self, query: str, ctx: dict, loc: Optional[Tuple]) -> Dict:
        return {
            "intent": "general",
            "response": "I can help with navigation, sharing locations, and saving favorites. What would you like to do?",
        }

    # ── Utility methods ──────────────────────────────────────

    @staticmethod
    def calculate_distance(loc1: Tuple[float, float], loc2: Tuple[float, float]) -> float:
        """Haversine distance in kilometers."""
        R = 6371.0  # Earth radius in km
        lat1, lon1 = math.radians(loc1[0]), math.radians(loc1[1])
        lat2, lon2 = math.radians(loc2[0]), math.radians(loc2[1])

        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c

    @staticmethod
    def calculate_bearing(from_loc: Tuple[float, float], to_loc: Tuple[float, float]) -> float:
        """Calculate bearing in degrees (0 = North, 90 = East)."""
        lat1 = math.radians(from_loc[0])
        lat2 = math.radians(to_loc[0])
        dlon = math.radians(to_loc[1] - from_loc[1])

        y = math.sin(dlon) * math.cos(lat2)
        x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)

        bearing = math.degrees(math.atan2(y, x))
        return (bearing + 360) % 360

    @staticmethod
    def bearing_to_cardinal(bearing: float) -> str:
        """Convert bearing to cardinal direction."""
        directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
        idx = round(bearing / 45) % 8
        return directions[idx]

    def get_navigation_info(
        self,
        from_loc: Tuple[float, float],
        to_loc: Tuple[float, float],
    ) -> Dict:
        """Get full navigation info between two points."""
        distance = self.calculate_distance(from_loc, to_loc)
        bearing = self.calculate_bearing(from_loc, to_loc)
        cardinal = self.bearing_to_cardinal(bearing)

        return {
            "distance_km": round(distance, 3),
            "distance_m": round(distance * 1000, 1),
            "bearing_degrees": round(bearing, 1),
            "direction": cardinal,
            "walking_minutes": round(distance / 5 * 60, 1),  # 5 km/h
            "driving_minutes": round(distance / 40 * 60, 1),  # 40 km/h avg
        }
