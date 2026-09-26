"""
Clickbait thumbnail generator with dynamic scaling.
Fixes the hardcoded overlay size issue that caused 'images do not match' errors.
Also generates title variants for A/B testing (Duodedos method).
"""

import os
import logging
import random
from pathlib import Path

import subprocess
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter

logger = logging.getLogger(__name__)

# Title power words for variant generation
POWER_WORDS = {
    "health": ["Hidden", "Secret", "Doctors Don't Tell You", "What They Don't", "Truth About", "Shocking", "Warning", "Must See", "Never Ignore", "Science Says"],
    "wealth": ["Earn", "Passive Income", "Millionaire", "Wealth", "Money", "Financial Freedom", "Rich", "Invest", "Build Wealth", "Cash Flow"],
    "relationships": ["Red Flags", "Toxic", "Attract", "Love", "Dating", "Marriage", "Signs", "Behavior", "Manipulation", "Trust"],
    "sports": ["Highlights", "Epic", "Unreal", "Incredible", "Best", "Top Plays", "Viral", "Amazing", "Spectacular", "Unbelievable"],
    "general": ["Shocking", "Amazing", "Incredible", "You Won't Believe", "Secret", "Warning", "Must See", "Hidden Truth", "Viral", "Extreme"],
}

TITLE_TEMPLATES = [
    "{power_word}: {topic}",
    "{topic} — {power_word}",
    "This {topic} Will {power_word} You",
    "{power_word} {topic} Strategy",
    "Why {topic} Is {power_word}",
    "{topic}: The {power_word} Method",
    "{power_word} Things About {topic}",
    "I Tried {topic} — {power_word} Results",
    # Perception-breaking hooks (proven format from viral case study)
    "{topic} Is Fake — Here's {count} Things That Prove It",
    "{topic} Is Lying To You — {count} Reasons Why",
    "I Tried {topic} For {days} Days — Here's What Happened",
    "{topic} Will Shock You — {count} Things You Didn't Know",
    "They Don't Want You To Know About {topic}",
]


def generate_title_variants(topic: str, niche: str = "general", count: int = 5) -> list:
    """Generate multiple title variants for A/B testing.

    Uses power words + templates to create clickable titles.
    """
    words = POWER_WORDS.get(niche, POWER_WORDS["general"])
    variants = []
    used = set()
    # Random values for perception-breaking templates
    count_val = random.choice([3, 5, 7, 10])
    days_val = random.choice([7, 14, 30, 60, 90])

    for _ in range(count * 3):  # oversample to avoid duplicates
        if len(variants) >= count:
            break
        template = random.choice(TITLE_TEMPLATES)
        power_word = random.choice(words)
        title = template.format(
            power_word=power_word, topic=topic,
            count=count_val, days=days_val,
        )

        # Deduplicate and length-limit
        title = title[:100]
        if title not in used:
            used.add(title)
            variants.append(title)

    return variants[:count]


class ClickbaitGenerator:
    """Generates clickbait thumbnails for video clips."""

    def __init__(self, config: dict):
        self.config = config
        self.thumb_config = config.get("thumbnails", {})
        self.output_dir = Path("output/thumbnails")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def create_thumbnail(self, video_path: Path) -> Path:
        """Create a thumbnail for a video clip."""
        thumb_path = self.output_dir / f"{video_path.stem}_thumbnail.jpg"
        
        # Extract a frame from the video
        temp_frame_path = self.output_dir / f"{video_path.stem}_frame.jpg"
        self._extract_frame(video_path, temp_frame_path)
        
        if not temp_frame_path.exists():
            logger.error(f"Failed to extract frame from {video_path}")
            return None
        
        try:
            img = Image.open(temp_frame_path).convert("RGB")
            img_w, img_h = img.size

            # Enhance colors
            enhancer = ImageEnhance.Color(img)
            img = enhancer.enhance(1.35)
            enhancer = ImageEnhance.Brightness(img)
            img = enhancer.enhance(1.1)
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(1.2)

            # Create overlay for effects
            overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
            draw_overlay = ImageDraw.Draw(overlay)

            # Scale badge/text positions relative to frame size
            badge_w = int(img_w * 0.22)
            badge_h = int(img_h * 0.08)
            badge_x = int(img_w * 0.02)
            badge_y = int(img_h * 0.02)

            # Red badge rectangle
            draw_overlay.rectangle(
                [(badge_x, badge_y), (badge_x + badge_w, badge_y + badge_h)],
                fill=(230, 20, 20, 200)
            )
            draw_overlay.rectangle(
                [(badge_x - 2, badge_y - 2), (badge_x + badge_w + 2, badge_y + badge_h + 2)],
                outline=(255, 255, 255, 220),
                width=3,
            )

            # Composite overlay onto image
            img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
            draw = ImageDraw.Draw(img)

            # Load font
            font_loaded = False
            badge_font = None
            title_font = None

            font_size = int(min(img_w, img_h) * 0.06)
            if font_size < 20:
                font_size = 20
            elif font_size > 72:
                font_size = 72

            font_path = "C:/Windows/Fonts/impact.ttf"
            if os.path.exists(font_path):
                try:
                    badge_font = ImageFont.truetype(font_path, font_size)
                    title_font = ImageFont.truetype(font_path, int(font_size * 1.3))
                    font_loaded = True
                except OSError:
                    pass

            if not font_loaded:
                badge_font = ImageFont.load_default()
                title_font = ImageFont.load_default()

            # Badge text
            badge_text = "VIRAL"
            badge_text_x = badge_x + int(badge_w * 0.15)
            badge_text_y = badge_y + int(badge_h * 0.2)
            draw.text((badge_text_x, badge_text_y), badge_text, fill=(255, 255, 255), font=badge_font)

            # Arrow pointing to interesting area
            arrow_color = (255, 30, 30)
            arrow_outline = (255, 255, 255)
            arrow_scale = min(img_w, img_h) / 720.0  # Scale relative to 720p
            pts = [
                (int(1100 * arrow_scale), int(300 * arrow_scale)),
                (int(980 * arrow_scale), int(360 * arrow_scale)),
                (int(1020 * arrow_scale), int(375 * arrow_scale)),
                (int(960 * arrow_scale), int(440 * arrow_scale)),
                (int(990 * arrow_scale), int(460 * arrow_scale)),
                (int(1050 * arrow_scale), int(395 * arrow_scale)),
                (int(1070 * arrow_scale), int(420 * arrow_scale)),
            ]
            draw.polygon(pts, fill=arrow_color, outline=arrow_outline)

            # Save thumbnail
            img.save(str(thumb_path), "JPEG", quality=85)
            logger.info(f"Thumbnail created: {thumb_path}")
            return thumb_path

        except Exception as e:
            logger.error(f"Thumbnail creation failed: {e}")
            return None
        finally:
            # Cleanup temp frame
            if temp_frame_path.exists():
                try:
                    temp_frame_path.unlink()
                except OSError:
                    pass

    def _extract_frame(self, video_path: Path, output_path: Path, timestamp: str = "00:00:05"):
        """Extract a frame from a video at the given timestamp."""
        cmd = [
            "ffmpeg", "-y",
            "-ss", timestamp,
            "-i", str(video_path),
            "-frames:v", "1",
            "-q:v", "2",
            str(output_path),
        ]
        try:
            result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, timeout=60)
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Frame extraction failed: {e}")
            return False
