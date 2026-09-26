
"""
Facebook Reels finder using yt-dlp.
Extracts trending reels from Facebook.
"""

import json
import logging
from pathlib import Path
from typing import List, Optional

import yt_dlp

from src.rate_limiter import rate_limiter

logger = logging.getLogger(__name__)


class FacebookReelsFinder:
    """Finds and downloads Facebook Reels."""

    def __init__(self, config: dict):
        self.config = config
        self.fb_config = config.get("facebook_reels", {})
        self.cookie_file = self.fb_config.get("cookie_file", "cookies.txt")
        self.history_file = config.get("facebook_reels_history", "data/facebook_reels_history.json")
        self.output_dir = Path("output/facebook_reels")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        Path("data").mkdir(exist_ok=True)

    def _get_ydl_options(self) -> dict:
        """Get yt-dlp options for Facebook."""
        opts = {
            "format": "best",
            "outtmpl": str(self.output_dir / "%(id)s.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
            "sleep_interval": 3,
            "retry_sleep": 5,
            "extractor_retries": 3,
            "retries": 5,
        }
        if Path(self.cookie_file).exists():
            opts["cookiefile"] = self.cookie_file
        return opts

    def find_trending(self, limit: int = 5) -> List[str]:
        """Find trending Facebook Reels."""
        clips = []
        try:
            with rate_limiter.http_throttle("facebook"):
                ydl_opts = self._get_ydl_options()
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    # Facebook reels extraction
                    result = ydl.extract_info(
                        "https://www.facebook.com/reels/",
                        download=False,
                    )
                    if result and "entries" in result:
                        for entry in result["entries"][:limit]:
                            if entry:
                                reel_url = entry.get("url") or entry.get("webpage_url")
                                if reel_url:
                                    downloaded = self.download_reel(reel_url)
                                    if downloaded:
                                        clips.append(downloaded)
        except Exception as e:
            logger.error(f"Facebook trending search failed: {e}")
        return clips

    def download_reel(self, url: str) -> Optional[str]:
        """Download a specific Facebook reel."""
        try:
            with rate_limiter.http_throttle("facebook"):
                ydl_opts = self._get_ydl_options()
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    if info:
                        video_id = info.get("id", "unknown")
                        for f in self.output_dir.glob(f"{video_id}.*"):
                            return str(f)
        except Exception as e:
            logger.error(f"Facebook reel download failed: {e}")
        return None

    def is_processed(self, video_id: str) -> bool:
        """Check if reel was already processed."""
        if Path(self.history_file).exists():
            with open(self.history_file, "r") as f:
                history = json.load(f)
            return video_id in history
        return False

    def mark_processed(self, video_id: str):
        """Mark reel as processed."""
        if Path(self.history_file).exists():
            with open(self.history_file, "r") as f:
                history = json.load(f)
        else:
            history = {}
        import time
        history[video_id] = time.time()
        with open(self.history_file, "w") as f:
            json.dump(history, f)
