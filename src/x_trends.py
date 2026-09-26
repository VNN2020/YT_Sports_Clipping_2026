"""
X (Twitter) trends integration for South African trending topics.
Scrapes trending topics from getdaytrends.com (SA region).
"""

import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


def get_x_trends(config: dict) -> List[str]:
    """Get current X/Twitter trending topics for South Africa.

    Returns a list of trending topic strings.
    """
    try:
        try:
            from hermes_tools import web_extract
        except ImportError:
            web_extract = None

        if web_extract:
            result = web_extract(["https://getdaytrends.com/south-africa/"], char_limit=5000)
            if result and "results" in result and len(result["results"]) > 0:
                content = result["results"][0].get("content", "")
                trends = _parse_trends(content)
                logger.info(f"Found {len(trends)} X trends for SA")
                return trends[:10]
        else:
            # Fallback when hermes_tools unavailable (standalone script mode)
            import urllib.request
            url = "https://getdaytrends.com/south-africa/"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                content = resp.read().decode("utf-8", errors="replace")
            trends = _parse_trends(content)
            if trends:
                logger.info(f"Found {len(trends)} X trends for SA")
                return trends[:10]
    except Exception as e:
        logger.debug(f"X trends fetch skipped: {e}")

    # Fallback trends
    return [
        "viral", "trending", "breaking", "news", "sa trending",
    ]


def _parse_trends(content: str) -> List[str]:
    """Parse trend names from HTML/text content."""
    import re
    
    # Look for trend names in common patterns
    trends = []
    
    # Pattern 1: Topic name in various HTML structures
    patterns = [
        r'>([^<]{3,50})</a>',  # Anchor text
        r'"topic":"([^"]+)"',  # JSON-like
        r'data-trend="([^"]+)"',  # Data attributes
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, content)
        for match in matches:
            match = match.strip()
            if len(match) > 2 and len(match) < 100:
                trends.append(match)
    
    # Deduplicate while preserving order
    seen = set()
    unique_trends = []
    for t in trends:
        if t not in seen:
            seen.add(t)
            unique_trends.append(t)
    
    return unique_trends
