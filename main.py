
#!/usr/bin/env python3
"""
YouTube Sports Trending Clipper & Automation Bot
Downloads trending YouTube videos, detects highlights, clips, transforms,
generates thumbnails, and uploads to YouTube.
"""

import os
import sys
import time
import argparse
import logging
import gc
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from src.config import load_config
from src.trending_finder import TrendingFinder
from src.clipper import VideoClipper
from src.clickbait_generator import ClickbaitGenerator, generate_title_variants
from src.uploader import YouTubeUploader
from src.cartoon_meme_transformer import CartoonMemeTransformer
from src.niche_validator import NicheValidator
from src.monetization_tracker import MonetizationTracker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("yt-sports-clipper")


def run_pipeline(
    config: dict,
    upload: bool = True,
    privacy_status: str = "unlisted",
    dry_run: bool = False,
    niche: str = None,
    target_url: str = None,
    use_x_trends: bool = False,
    podcast_mode: bool = False,
    schedule_time: str = None,
):
    """Run the full pipeline."""
   
    clip_config = config.get("clip", {})
    target_duration = clip_config.get("target_duration_seconds", 300)
    min_duration = clip_config.get("min_duration_seconds", 240)
    max_duration = clip_config.get("max_duration_seconds", 360)

    logger.info("=" * 60)
    logger.info("YOUTUBE SPORTS TRENDING CLIPPER & AUTOMATION BOT")
    logger.info("Mode: %s", "DRY RUN (No Upload)" if dry_run else "LIVE RUN")
    logger.info("Target Duration: %ss (4-6m slot)", target_duration)

    if target_url:
        logger.info("Processing specific video URL: %s", target_url)

    finder = TrendingFinder(config)
    clipper = VideoClipper(config)
    clickbait = ClickbaitGenerator(config)
    uploader = YouTubeUploader(config) if upload else None
    transformer = CartoonMemeTransformer(config)
    niche_validator = NicheValidator()
    monetracker = MonetizationTracker()

    # Validate niche before processing
    niche_name = niche or config.get("channel", {}).get("niche", "general")
    validation = niche_validator.validate(niche_name)
    logger.info("Niche validation: %s (score: %.1f, recommended: %s)",
                niche_name, validation["score"].get("net_score", 0),
                validation["score"].get("recommended", True))

    # Viral criteria check (from viral case study)
    viral_check = niche_validator.check_viral_criteria(niche_name, niche_name)
    logger.info("Viral criteria: all_met=%s, criteria=%s",
                viral_check["all_criteria_met"], viral_check["criteria_met"])
    if viral_check["all_criteria_met"]:
        logger.info("5-phase structure: %s",
                    ", ".join(niche_validator.get_five_phase_structure()))

    # USA audience targeting for higher RPM
    target_audience = config.get("channel", {}).get("target_audience", "SA")
    if target_audience == "US":
        logger.info("USA audience targeting enabled — higher RPM expected")

    target_channel = config.get("channel", {}).get("target_channel_id")

    if target_url:
        videos = [{
            "id": target_url.split("v=")[-1] if "v=" in target_url else "unknown",
            "title": "Direct URL",
            "webpage_url": target_url,
            "uploader": "Unknown",
            "duration": 0,
            "view_count": 0,
            "description": "",
            "tags": [],
            "heatmap": None,
            "chapters": None,
        }]
    else:
        videos = finder.find_trending(limit=10, niche=niche)

    # RPM-based prioritization — sort by view count desc (Saad method)
    videos.sort(key=lambda v: v.get("view_count", 0) or 0, reverse=True)
    logger.info("Videos prioritized by RPM potential: %s",
                [(v.get("title", "?"), v.get("view_count", 0)) for v in videos[:5]])

    if not videos:
        logger.info("No new qualified trending videos found to process in this cycle.")
        return

    for i, video in enumerate(videos):
        logger.info("Processing Candidate %d: %s", i + 1, video.get("title", "Unknown"))

        # Zero-views check — skip videos with no engagement
        view_count = video.get("view_count", 0) or 0
        if view_count == 0:
            logger.warning("Skipping '%s' — zero views (zero-views issue fix)", video.get("title"))
            continue

        try:
            clip_path = clipper.download_and_clip(
                video["webpage_url"],
                target_duration=target_duration,
            )

            if clip_path:
                thumb_path = clickbait.create_thumbnail(clip_path)

                # Title A/B variants (Duodedos method)
                topic = video.get("title", "Video")
                title_variants = generate_title_variants(topic, niche_name, count=3)
                best_title = title_variants[0] if title_variants else topic
                logger.info("Title variants: %s", title_variants)

                # Track video in monetization tracker
                monetracker.record_video(
                    video_id=video.get("id", "unknown"),
                    title=video.get("title", ""),
                    niche=niche or "general",
                    views=video.get("view_count", 0),
                )

                # Track per-upload analytics for iterative testing
                monetracker.track_upload(
                    video_id=video.get("id", "unknown"),
                    title=best_title,
                    test_variable="perception_break_hook",
                    retention_notes="flat_retention_target",
                    hook_style="fake_exposure_listicle",
                )

                if uploader and not dry_run:
                    title = best_title
                    description = video.get("description", "")[:5000]
                    tags = video.get("tags", [])

                    result = uploader.upload_video(
                        video_file=clip_path,
                        title=title,
                        description=description,
                        tags=tags,
                        thumb_file=thumb_path,
                        privacy_status=privacy_status,
                        target_channel_id=target_channel,
                        schedule_time=schedule_time,
                    )
                    logger.info("Upload result: %s", result)

        except Exception as e:
            logger.error("Error processing video %s: %s", video.get("title"), e)


def main():
    parser = argparse.ArgumentParser(description="YouTube Sports Clipping Bot")
    parser.add_argument("--dry-run", action="store_true", help="Run without uploading")
    parser.add_argument("--niche", type=str, help="Target niche/category")
    parser.add_argument("--url", type=str, help="Process specific YouTube URL")
    parser.add_argument("--privacy", type=str, default="unlisted", help="Privacy status")
    parser.add_argument("--x-trends", action="store_true", help="Use X/Twitter trends")
    parser.add_argument("--podcast", action="store_true", help="Podcast mode")
    parser.add_argument("--daemon", action="store_true", help="Run as daemon")
    parser.add_argument("--schedule", type=str, default=None, help="ISO 8601 publish time")

    args = parser.parse_args()

    config = load_config()

    if args.daemon:
        logger.info("Starting daemon mode...")
        while True:
            try:
                run_pipeline(
                    config,
                    upload=True,
                    privacy_status=args.privacy,
                    dry_run=args.dry_run,
                    niche=args.niche,
                    target_url=args.url,
                    use_x_trends=args.x_trends,
                    podcast_mode=args.podcast,
                    schedule_time=args.schedule,
                )
            except Exception as e:
                logger.error("Error in daemon cycle: %s", e)
            gc.collect()
            time.sleep(config.get("daemon", {}).get("interval_seconds", 3600))
    else:
        run_pipeline(
            config,
            upload=True,
            privacy_status=args.privacy,
            dry_run=args.dry_run,
            niche=args.niche,
            target_url=args.url,
            use_x_trends=args.x_trends,
            podcast_mode=args.podcast,
            schedule_time=args.schedule,
        )


if __name__ == "__main__":
    main()
