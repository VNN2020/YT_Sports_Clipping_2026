
"""
Video Clipper module.
Downloads YouTube videos using yt-dlp and clips them to target duration.
"""

import os
import re
import shutil
import logging
import subprocess
from pathlib import Path
from typing import Dict, Optional, Tuple

import yt_dlp

from src.rate_limiter import rate_limiter

logger = logging.getLogger(__name__)


class VideoClipper:
    """Downloads and clips YouTube videos."""

    def __init__(self, config: dict):
        self.config = config
        self.clip_config = config.get("clip", {})
        self.output_dir = Path("output/clips")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir = Path("temp")
        self.temp_dir.mkdir(exist_ok=True)

    def _get_ydl_options(self, output_path: Path) -> dict:
        return {
            "format": (
                "bestvideo[ext=mp4][vcodec^=avc][height<=1080]+bestaudio[ext=m4a]/"
                "best[ext=mp4][vcodec^=avc]/best[ext=mp4]/best"
            ),
            "outtmpl": str(output_path),
            "merge_output_format": "mp4",
            "quiet": True,
            "no_warnings": True,
            "sleep_interval": 3,
            "retry_sleep": 5,
            "extractor_retries": 3,
            "retries": 10,
            "http_chunk_size": 10 * 1024 * 1024,
            "throttled_rate": "500K",
            "noprogress": True,
            "buffersize": 1024 * 1024,
        }

    def download_video(self, url: str) -> Optional[Path]:
        video_id = self._extract_video_id(url)
        output_path = self.temp_dir / f"{video_id}_full.%(ext)s"
        
        ydl_opts = self._get_ydl_options(output_path)
        
        try:
            with rate_limiter.download_throttle("youtube"):
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    
            for f in self.temp_dir.glob(f"{video_id}_full.*"):
                return f
                
        except Exception as e:
            logger.error(f"Download failed for {url}: {e}")
            return None

    def _extract_video_id(self, url: str) -> str:
        patterns = [
            r"(?:v=|youtu\.be/|youtube\.com/watch\?v=)([a-zA-Z0-9_-]{11})",
            r"([a-zA-Z0-9_-]{11})",
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return "temp"

    def download_and_clip(
        self,
        url: str,
        target_duration: int = 300,
        start_offset: int = 0,
    ) -> Optional[Path]:
        video_path = self.download_video(url)
        if not video_path:
            return None
        
        duration = self._get_video_duration(video_path)
        if duration is None:
            logger.error(f"Could not determine duration for {url}")
            return None
        
        if duration < target_duration:
            logger.info(f"Video too short ({duration}s < {target_duration}s), using full video")
            clip_path = self.output_dir / f"{video_path.stem}_full.mp4"
            shutil.move(str(video_path), str(clip_path))
            return clip_path
        
        clip_path = self.output_dir / f"{video_path.stem}_clipped.mp4"
        self._process_video_with_ffmpeg(
            video_path, clip_path, "Unknown", duration,
            video_id=video_path.stem.replace("_full", ""),
            start_offset=start_offset,
            clip_duration=target_duration,
        )
        
        if video_path.exists():
            video_path.unlink()
        
        return clip_path if clip_path.exists() else None

    def _get_video_duration(self, video_path: Path) -> Optional[float]:
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "quiet",
                 "-show_entries", "format=duration",
                 "-of", "csv=p=0",
                 str(video_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=30,
            )
            if result.returncode == 0 and result.stdout:
                duration = result.stdout.strip()
                return float(duration) if duration else None
        except Exception as e:
            logger.error(f"ffprobe failed: {e}")
        return None

    def _process_video_with_ffmpeg(
        self,
        input_path: Path,
        output_path: Path,
        uploader: str,
        duration: float,
        video_id: str = "temp",
        vertical: bool = False,
        start_offset: int = 0,
        clip_duration: int = 300,
    ):
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(start_offset),
            "-i", str(input_path),
            "-t", str(clip_duration),
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "26",
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",
            "-threads", "0",
        ]
        
        if vertical:
            cmd.extend(["-vf", "scale=1080:1920,setsar=1"])
        
        cmd.append(str(output_path))
        
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                timeout=1800,
            )
            if result.returncode == 0:
                logger.info(f"Clipped video saved: {output_path}")
            else:
                logger.error(f"FFmpeg failed: {result.stderr[:500]}")
        except subprocess.TimeoutExpired:
            logger.error("FFmpeg timed out after 1800 seconds")
        except Exception as e:
            logger.error(f"FFmpeg error: {e}")

    def create_vertical(self, input_path: Path, output_path: Path):
        cmd = [
            "ffmpeg", "-y",
            "-i", str(input_path),
            "-vf", "scale=1080:1920,setsar=1",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "28",
            "-c:a", "aac",
            "-b:a", "128k",
            "-threads", "0",
            str(output_path),
        ]
        
        try:
            result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, timeout=1800)
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Vertical conversion failed: {e}")
            return False
