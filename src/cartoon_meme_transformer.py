
"""
Cartoon/meme transformer for copyright-safe video transforms.
"""

import logging
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class CartoonMemeTransformer:
    """Applies cartoon/meme effects to videos for copyright safety."""

    def __init__(self, config: dict):
        self.config = config
        self.cartoon_config = config.get("cartoon", {})
        self.output_dir = Path("output/cartoon")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.ffmpeg = self._find_ffmpeg()

    def _find_ffmpeg(self) -> str:
        import shutil
        ffmpeg_path = shutil.which("ffmpeg")
        return ffmpeg_path or "ffmpeg"

    def transform(self, input_path: Path, style: str = "anime") -> Optional[Path]:
        if not self.ffmpeg or not Path(self.ffmpeg).exists():
            logger.error("ffmpeg not found")
            return None
        
        output_path = self.output_dir / f"{input_path.stem}_{style}.mp4"
        filter_chain = self._get_filter_chain(style)
        
        cmd = [
            self.ffmpeg, "-y",
            "-threads", "0",
            "-i", str(input_path),
            "-vf", filter_chain,
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "26",
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",
        ]
        
        cmd.append(str(output_path))
        
        try:
            result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, timeout=1800)
            if result.returncode == 0:
                logger.info(f"Cartoon transform complete: {output_path}")
                return output_path
            else:
                logger.error(f"Cartoon transform failed: {result.stderr[:500]}")
        except subprocess.TimeoutExpired:
            logger.error("Cartoon transform timed out after 1800 seconds — skipping")
            return output_path
        except Exception as e:
            logger.error(f"Cartoon transform error: {e}")
            return output_path

        return None

    def _get_filter_chain(self, style: str) -> str:
        filters = {
            "anime": (
                "eq=contrast=1.3:brightness=0.05:saturation=1.4,"
                "hqdn3d=4:3:6:4.5,"
            ),
            "comic": (
                "eq=contrast=1.5:brightness=0.1:saturation=1.8,"
            ),
            "sketch": (
                "edgedetect=low=0.1:high=0.3:"
                "negate,"
            ),
            "pop_art": (
                "hue=s=2,"
                "eq=contrast=1.8:brightness=0.1:saturation=2,"
            ),
        }
        
        return filters.get(style, filters["anime"])
