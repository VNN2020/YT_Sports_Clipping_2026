
"""
Configuration loader for YouTube Sports Clipping Bot.
"""

import os
import yaml
from pathlib import Path
from typing import Any


def load_config(config_path: str = None) -> dict:
    """Load configuration from YAML file."""
    if config_path is None:
        config_path = Path(__file__).resolve().parent.parent / "config.yaml"
    
    config_path = Path(config_path)
    
    if not config_path.exists():
        return get_default_config()
    
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    
    return config or get_default_config()


def get_default_config() -> dict:
    """Return default configuration."""
    return {
        "clip": {
            "target_duration_seconds": 300,
            "min_duration_seconds": 240,
            "max_duration_seconds": 360,
            "enabled": True,
        },
        "upload": {
            "enabled": True,
            "privacy": "unlisted",
        },
        "cartoon": {
            "enabled": True,
            "style": "anime",
        },
        "thumbnails": {
            "enabled": True,
            "style": "clickbait",
        },
        "daemon": {
            "enabled": True,
            "interval_seconds": 3600,
        },
        "youtube_api": {
            "quota_per_day": 10000,
        },
        "facebook_reels": {
            "enabled": False,
        },
    }


def save_config(config: dict, config_path: str = None):
    """Save configuration to YAML file."""
    if config_path is None:
        config_path = Path(__file__).resolve().parent.parent / "config.yaml"
    
    config_path = Path(config_path)
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
