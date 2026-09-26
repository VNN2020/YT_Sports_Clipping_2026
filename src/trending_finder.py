
"""
Trending video finder using YouTube search API and yt-dlp.
"""

import logging
from typing import List, Dict, Optional

import yt_dlp

from src.rate_limiter import rate_limiter

logger = logging.getLogger(__name__)


class TrendingFinder:
    """Finds trending videos on YouTube."""

    def __init__(self, config: dict):
        self.config = config
        self.search_config = config.get("search", {})

    def find_trending(
        self,
        limit: int = 10,
        niche: str = None,
        min_views: int = 10000,
        max_results: int = 50,
    ) -> List[Dict]:
        queries = []
        if niche:
            queries.append(niche)
        else:
            queries = self.search_config.get("queries", ["viral", "trending"])
        
        videos = []
        seen_ids = set()
        
        for query in queries:
            if len(videos) >= limit:
                break
            
            try:
                with rate_limiter.http_throttle("youtube-search"):
                    ydl_opts = {
                        "quiet": True,
                        "no_warnings": True,
                        "extract_flat": True,
                        "playlistend": max_results,
                    }
                    
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        result = ydl.extract_info(
                            f"ytsearch{max_results}:{query}",
                            download=False,
                        )
                
                if not result or "entries" not in result:
                    continue
                
                for entry in result["entries"]:
                    if not entry:
                        continue
                    
                    video_id = entry.get("id", "")
                    if video_id in seen_ids:
                        continue
                    
                    seen_ids.add(video_id)
                    
                    video = {
                        "id": video_id,
                        "title": entry.get("title", "Unknown"),
                        "webpage_url": f"https://www.youtube.com/watch?v={video_id}",
                        "uploader": entry.get("uploader", "Unknown"),
                        "duration": entry.get("duration", 0) or 0,
                        "view_count": entry.get("view_count", 0) or 0,
                        "description": entry.get("description", "")[:500],
                        "tags": entry.get("tags", [])[:10],
                        "heatmap": None,
                        "chapters": None,
                    }
                    
                    if video["view_count"] >= min_views:
                        videos.append(video)
                    
                    if len(videos) >= limit:
                        break
                        
            except Exception as e:
                logger.error(f"Search failed for query '{query}': {e}")
        
        return videos[:limit]

    def get_video_details(self, video_id: str) -> Optional[Dict]:
        try:
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(
                    f"https://www.youtube.com/watch?v={video_id}",
                    download=False,
                )
            
            return info
        except Exception as e:
            logger.error(f"Failed to get video details: {e}")
            return None
