
#!/usr/bin/env python3
"""
YouTube Sports Shorts Automated Pipeline (CLI)
Short-form content pipeline for finding, clipping, and uploading Shorts.
"""

import sys
import logging
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import argparse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("shorts-cli")

from src.shorts_pipeline import ShortsPipeline
from src.config import load_config


def run_pipeline(config: dict, dry_run: bool = False, niche: str = None, target_url: str = None, privacy: str = "unlisted"):
    """Run the Shorts pipeline."""
    pipeline = ShortsPipeline(config)
    
    if target_url:
        pipeline.process_url(target_url, dry_run=dry_run, privacy=privacy)
    else:
        pipeline.run(dry_run=dry_run, niche=niche, privacy=privacy)


def main():
    parser = argparse.ArgumentParser(description="YouTube Sports Shorts Automated Pipeline (CLI)")
    parser.add_argument("--dry-run", action="store_true", help="Run search, clip, thumbnail — no upload")
    parser.add_argument("--run-once", action="store_true", help="Run one full cycle immediately")
    parser.add_argument("--daemon", action="store_true", help="Run continuously in the background")
    parser.add_argument("--interval", type=float, help="Interval in hours for daemon mode")
    parser.add_argument("--niche", type=str, help="Target niche / category query")
    parser.add_argument("--url", type=str, help="Process a specific YouTube URL directly")
    parser.add_argument("--privacy", type=str, default="unlisted", help="Set upload privacy status")
    
    args = parser.parse_args()
    
    config = load_config()
    if args.interval:
        config.setdefault("scheduler", {})["interval_hours"] = args.interval
    
    if args.daemon:
        logger.info("Starting Shorts pipeline in DAEMON MODE. Will run every %s hours...", 
                    config.get("scheduler", {}).get("interval_hours", 1))
        while True:
            try:
                run_pipeline(config, dry_run=args.dry_run, niche=args.niche, target_url=args.url, privacy=args.privacy)
            except Exception as e:
                logger.error("Error in daemon cycle: %s", e)
            time.sleep(config.get("scheduler", {}).get("interval_hours", 1) * 3600)
    else:
        run_pipeline(config, dry_run=args.dry_run, niche=args.niche, target_url=args.url, privacy=args.privacy)


if __name__ == "__main__":
    main()
