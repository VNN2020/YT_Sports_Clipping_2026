"""
Light moment detector for finding funny/memorable moments in videos.
"""

import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


class LightMomentDetector:
    """Detects light/funny moments in video content."""

    def __init__(self, config: dict):
        self.config = config
        self.light_config = config.get("light_moments", {})

    def detect_moments(self, video_path: str, transcript: str = None) -> List[Dict]:
        """Detect light moments in a video."""
        moments = []
        
        # If we have a transcript, use it to find funny moments
        if transcript:
            moments.extend(self._analyze_transcript(transcript))
        
        return moments[:10]

    def _analyze_transcript(self, transcript: str) -> List[Dict]:
        """Analyze transcript for light moments."""
        # Simple keyword-based detection
        funny_indicators = [
            "laugh", "funny", "hilarious", "joke", "comedy",
            "unexpected", "surprise", "oops", "fail", "win",
            "crazy", "insane", "unbelievable",
        ]
        
        moments = []
        lines = transcript.split("\n")
        
        for i, line in enumerate(lines):
            lower = line.lower()
            for indicator in funny_indicators:
                if indicator in lower:
                    moments.append({
                        "line_index": i,
                        "text": line,
                        "indicator": indicator,
                        "score": 0.7,
                    })
                    break
        
        return moments
