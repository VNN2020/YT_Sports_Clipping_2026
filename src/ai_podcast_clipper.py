"""
AI Podcast Clipper — replaces Clips Kitty's Ollama pipeline.

Uses Whisper (local transcription, no server) + Gemini (LLM moment scoring)
to detect and extract highlight moments from videos. No Ollama, no api.exe.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import List, Dict

logger = logging.getLogger(__name__)


class AIPodcastClipper:
    """Replaces Clips Kitty with Whisper + Gemini local pipeline."""

    def __init__(self, config: dict):
        self.config = config
        self.podcast_config = config.get("podcast", {})
        self.gemini_model = self.podcast_config.get("gemini_model", "gemini-3.6-flash")
        self.whisper_model = self.podcast_config.get("whisper_model", "base")
        self.clip_count = self.podcast_config.get("clip_count", 3)
        self.content_type = self.podcast_config.get("content_type", "funny")
        self._gemini = None
        self._whisper = None

    def _get_whisper(self) -> whisper.Model:
        """Get or load the Whisper model (cached after first load)."""
        if self._whisper is None:
            try:
                import whisper as _whisper_lib
                logger.info(f"Loading Whisper model: {self.whisper_model}")
                self._whisper = _whisper_lib.load_model(self.whisper_model)
            except ImportError:
                logger.error("whisper not installed — run: pip install openai-whisper")
                return None
        return self._whisper

    def _get_gemini(self):
        """Get or initialize the Gemini client."""
        if self._gemini is None:
            try:
                import google.generativeai as _genai
                api_key = self.podcast_config.get("gemini_api_key")
                if not api_key:
                    logger.warning("No Gemini API key configured, skipping AI analysis")
                    return None
                self._gemini = _genai.GenerativeModel(self.gemini_model)
            except ImportError:
                logger.error("google-generativeai not installed — run: pip install google-generativeai")
                return None
        return self._gemini

    def transcribe(self, video_path: str) -> Dict:
        """Transcribe video audio using Whisper. Returns word-level timestamps."""
        try:
            whisper_model = self._get_whisper()
            logger.info(f"Transcribing {Path(video_path).name} with Whisper...")
            result = whisper_model.transcribe(video_path, word_timestamps=True)
            segments = result["segments"]

            word_list = []
            for segment in segments:
                if "words" in segment:
                    for w in segment["words"]:
                        word_list.append({"word": w["word"], "start": w["start"], "end": w["end"]})

            sentences = [{"text": s["text"].strip(), "start": s["start"], "end": s["end"]} for s in segments]

            logger.info(f"Transcription complete: {len(word_list)} words, {len(sentences)} segments")
            return {"words": word_list, "sentences": sentences}
        except Exception as e:
            logger.error(f"Whisper transcription failed: {e}")
            return {"words": [], "sentences": []}

    def score_moments(self, transcript: Dict) -> List[Dict]:
        """Use Gemini to score and rank transcript segments by engagement."""
        gemini = self._get_gemini()
        if not gemini or not transcript["sentences"]:
            return []

        sentences = transcript["sentences"]
        batch_size = 5
        scored_segments = []

        for i in range(0, len(sentences), batch_size):
            batch = sentences[i:i + batch_size]
            batch_text = "\n".join(f"[{s['start']:.0f}-{s['end']:.0f}s] {s['text']}" for s in batch)

            prompt = (
                "Analyze this video transcript segment and identify the most engaging moments.\n\n"
                "For each sentence, score it 1-10 on: emotional intensity, entertainment value, "
                "virality potential, completion compulsion.\n\n"
                "Respond in JSON format: [{\"sentence_index\": N, \"score\": X, \"reason\": \"brief explanation\"}]\n"
                "Only include sentences scoring 7+.\n\nTranscript:\n" + batch_text
            )

            try:
                response = gemini.generate_content(prompt)
                import json as _json
                text = response.text.strip()
                start = text.find("[")
                end = text.rfind("]") + 1
                if start >= 0 and end > start:
                    segments = _json.loads(text[start:end])
                    for s in segments:
                        if "sentence_index" in s and s["sentence_index"] < len(sentences):
                            idx = s["sentence_index"] + i
                            scored_segments.append({
                                "start_time": sentences[idx]["start"],
                                "end_time": sentences[idx]["end"],
                                "text": sentences[idx]["text"],
                                "score": s["score"],
                                "reason": s["reason"],
                            })
                logger.info(f"Gemini scored batch {i//batch_size}: {len(segments)} high-score moments")
            except Exception as e:
                logger.error(f"Gemini scoring failed for batch {i//batch_size}: {e}")

        scored_segments.sort(key=lambda x: x["score"], reverse=True)
        return scored_segments[:self.clip_count]

    def extract_clip(self, video_path: str, start_time: float, duration: float, output_path: Path) -> bool:
        """Extract a clip segment from video using FFmpeg."""
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(start_time),
            "-i", str(video_path),
            "-t", str(duration),
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "26",
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart", "-threads", "0",
            str(output_path),
        ]
        try:
            result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, timeout=300)
            if result.returncode == 0:
                logger.info(f"AI clip extracted: {output_path} ({start_time:.0f}s, {duration:.0f}s)")
                return True
            else:
                logger.error(f"FFmpeg clip extraction failed: {result.stderr[:200]}")
                return False
        except Exception as e:
            logger.error(f"Clip extraction error: {e}")
            return False

    def clip_podcast(self, video_path: str, output_dir: Path, video_info: Dict = None) -> List[Dict]:
        """Full pipeline: transcribe → score → extract. Returns list of extracted clips."""
        clips = []
        transcript = self.transcribe(video_path)
        if not transcript["sentences"]:
            logger.warning("No transcript generated, falling back to LightMomentDetector")
            return clips

        moments = self.score_moments(transcript)
        if not moments:
            logger.warning("No high-score moments found via Gemini, falling back")
            return clips

        for i, moment in enumerate(moments):
            start_time = moment["start_time"]
            clip_duration = max(15, min(30, moment["end_time"] - start_time + 5))
            clip_path = output_dir / f"ai_clip_{i}_{int(start_time)}.mp4"
            if self.extract_clip(video_path, start_time, clip_duration, clip_path):
                clips.append({
                    "path": str(clip_path),
                    "start_time": start_time,
                    "duration": clip_duration,
                    "text": moment["text"][:200],
                    "score": moment["score"],
                    "reason": moment["reason"],
                })

        logger.info(f"AI clip generation complete: {len(clips)} clips extracted")
        return clips

    def find_interesting_segments(self, transcript) -> List[Dict]:
        """Backward compatibility — uses Whisper+Gemini pipeline."""
        if isinstance(transcript, str):
            transcript = {"words": [], "sentences": [{"text": transcript, "start": 0, "end": 0}]}
        return self.score_moments(transcript)
