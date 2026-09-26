"""
Niche validator — scores niches for monetization and viral potential.

Validates a niche against:
  - RPM estimates (revenue per mille)
  - Trending signal strength
  - Competition level
  - Monetization eligibility
"""

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Niche viability scores (0-100)
NICHE_VIABILITY = {
    "health": 85,
    "wealth": 90,
    "relationships": 70,
    "sports": 65,
    "technology": 80,
    "finance": 92,
    "education": 75,
    "entertainment": 60,
    "gaming": 78,
    "roblox": 82,
    "ai": 88,
    "faceless": 72,
    "storytelling": 68,
    "animation": 74,
}

# Competition level (0-100, higher = more competitive)
NICHE_COMPETITION = {
    "health": 70,
    "wealth": 75,
    "relationships": 60,
    "sports": 65,
    "technology": 80,
    "finance": 72,
    "education": 55,
    "entertainment": 85,
    "gaming": 82,
    "roblox": 70,
    "ai": 78,
    "faceless": 50,
    "storytelling": 55,
    "animation": 60,
}

# Sub-niche database
SUB_NICHES = {
    "health": ["nutrition", "fitness", "mental health", "wellness", "supplements", "weight loss", "sleep", "longevity"],
    "wealth": ["investing", "real estate", "crypto", "passive income", "budgeting", "entrepreneurship", "side hustle", "stocks"],
    "relationships": ["dating", "marriage", "communication", "self-love", "attraction", "breakup recovery", "personality types"],
    "sports": ["football", "basketball", "soccer", "fitness", " MMA", "Olympics", "sports highlights", "training tips"],
    "finance": ["trading", "personal finance", "tax", "business", "investing", "cryptocurrency", "budgeting", "debt management"],
}

# RPM by content type (BRL per 1000 views)
CONTENT_RPM = {
    "shorts": 3.0,
    "long_form": 8.0,
    "tutorial": 10.0,
    "review": 7.0,
    "vlog": 5.0,
    "news": 6.0,
    "storytelling": 4.0,
}


class NicheValidator:
    """Validate and score niches for channel growth."""

    def __init__(self, tracker_file: Optional[Path] = None):
        self.tracker_file = tracker_file or Path("data/niche_scores.json")
        self.tracker_file.parent.mkdir(parents=True, exist_ok=True)
        self.scores = self._load()

    def _load(self) -> dict:
        if self.tracker_file.exists():
            try:
                with open(self.tracker_file, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        return {}

    def save(self):
        try:
            with open(self.tracker_file, "w") as f:
                json.dump(self.scores, f, indent=2)
        except OSError:
            pass

    def score(self, niche: str) -> dict:
        """Score a niche for viability and competition."""
        viability = NICHE_VIABILITY.get(niche, NICHE_VIABILITY.get("general", 50))
        competition = NICHE_COMPETITION.get(niche, NICHE_COMPETITION.get("general", 50))
        # Net score: high viability - moderate competition = good
        net_score = viability - (competition * 0.5)

        return {
            "niche": niche,
            "viability": viability,
            "competition": competition,
            "net_score": round(net_score, 1),
            "recommended": net_score >= 40,
        }

    def best_niche(self, niches: list) -> dict:
        """Return the best niche from a list."""
        scored = [(n, self.score(n)) for n in niches]
        scored.sort(key=lambda x: x[1]["net_score"], reverse=True)
        return scored[0] if scored else ("general", self.score("general"))

    def validate(self, niche: str, min_score: float = 30) -> dict:
        """Validate a niche meets minimum thresholds."""
        score = self.score(niche)
        passed = score["net_score"] >= min_score
        return {
            "niche": niche,
            "validated": passed,
            "score": score,
            "reason": "Net score meets threshold" if passed else f"Net score {score['net_score']} below {min_score}",
        }

    def batch_validate(self, niches: list) -> list:
        """Validate multiple niches, return sorted by score."""
        results = [self.validate(n) for n in niches]
        results.sort(key=lambda x: x["score"]["net_score"], reverse=True)
        return results

    def get_sub_niches(self, niche: str) -> list:
        """Return sub-niches for a given niche."""
        return SUB_NICHES.get(niche, [])

    def score_content_type(self, content_type: str) -> float:
        """Get RPM estimate for a content type."""
        return CONTENT_RPM.get(content_type, CONTENT_RPM.get("long_form", 8.0))

    def validate_content_type(self, content_type: str, niche: str) -> dict:
        """Validate a content type for a given niche."""
        rpm = self.score_content_type(content_type)
        niche_score = self.score(niche)
        return {
            "content_type": content_type,
            "niche": niche,
            "estimated_rpm": rpm,
            "niche_net_score": niche_score["net_score"],
            "viable": rpm >= 3.0 and niche_score["net_score"] >= 25,
        }

    # Viral content criteria (from viral case study analysis)
    VIRAL_CRITERIA = {
        "universally_relatable": True,
        "emotional_hook": True,
        "completion_compulsion": True,
    }

    # 5-phase content structure (Declare → Assess → Isolate → Process → Build → Reveal)
    FIVE_PHASE_STRUCTURE = [
        "declare",
        "assess",
        "isolate",
        "process",
        "build",
        "reveal",
    ]

    def check_viral_criteria(self, topic: str, niche: str) -> dict:
        """Check if a topic/niche meets the 3 viral criteria."""
        criteria_met = []
        reasons = {}
        universal_niches = {"health", "wealth", "relationships", "sports", "food"}
        if niche in universal_niches:
            criteria_met.append("universally_relatable")
            reasons["universally_relatable"] = f"{niche} is universally accessible"
        else:
            reasons["universally_relatable"] = f"{niche} may require niche knowledge"
        reasons["emotional_hook"] = "Topic has emotional hook potential"
        criteria_met.append("emotional_hook")
        reasons["completion_compulsion"] = "Declarative format creates completion compulsion"
        criteria_met.append("completion_compulsion")
        return {
            "topic": topic,
            "niche": niche,
            "all_criteria_met": len(criteria_met) == 3,
            "criteria_met": criteria_met,
            "reasons": reasons,
        }

    def get_five_phase_structure(self) -> list:
        """Return the 5-phase content structure template."""
        return self.FIVE_PHASE_STRUCTURE