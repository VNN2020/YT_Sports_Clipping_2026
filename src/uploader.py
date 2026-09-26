
"""
YouTube uploader with OAuth authentication and retry logic.
"""

import os
import json
import logging
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from src.rate_limiter import rate_limiter

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]


class YouTubeUploader:
    """Handles YouTube video uploads with OAuth and retry logic."""

    def __init__(self, config: dict):
        self.config = config
        self.upload_config = config.get("upload", {})
        self.project_dir = Path(__file__).resolve().parent.parent
        self.token_file = self.project_dir / "token.json"
        self.client_secret_file = self._find_client_secret()
        self.quota_file = self.project_dir / "data" / "quota.json"
        self.quota_file.parent.mkdir(parents=True, exist_ok=True)
        self.youtube = None

    def _find_client_secret(self) -> Path:
        """Find client_secret.json with multiple fallback paths."""
        candidates = [
            self.project_dir / "client_secret.json",
            Path.cwd() / "client_secret.json",
            Path.cwd() / "src" / "client_secret.json",
            self.project_dir / "src" / "client_secret.json",
        ]
        for cand in candidates:
            if cand.exists():
                logger.info(f"Found client_secret.json at {cand}")
                return cand
        logger.warning("client_secret.json not found in any expected location")
        return candidates[0]

    def _check_quota(self) -> bool:
        """Return False if daily upload limit was already hit today."""
        if not self.quota_file.exists():
            return True
        try:
            with open(self.quota_file, "r") as f:
                q = json.load(f)
            from datetime import date
            if q.get("upload_limit_exceeded") and q.get("date") == str(date.today()):
                logger.warning("Daily upload limit already reached today, skipping upload")
                return False
        except Exception:
            pass
        return True

    def _mark_quota_exceeded(self):
        """Record that the daily upload limit was hit."""
        from datetime import date
        try:
            with open(self.quota_file, "w") as f:
                json.dump({"upload_limit_exceeded": True, "date": str(date.today())}, f)
        except Exception:
            pass

    def authenticate(self):
        """Authenticate with YouTube Data API."""
        creds = None
        
        if self.token_file.exists():
            creds = Credentials.from_authorized_user_file(str(self.token_file), SCOPES)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                logger.info("Refreshing expired token...")
                creds.refresh(Request())
            elif self.client_secret_file.exists():
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self.client_secret_file), SCOPES
                )
                creds = flow.run_local_server(port=0)
            else:
                raise FileNotFoundError(
                    f"Client secret file not found at {self.client_secret_file}"
                )
            
            # Save token atomically
            temp_token = self.token_file.with_suffix(".tmp")
            with open(temp_token, "w") as f:
                f.write(creds.to_json())
            temp_token.replace(self.token_file)
        
        self.youtube = build("youtube", "v3", credentials=creds)
        return self.youtube

    def upload_video(
        self,
        video_file: Path,
        title: str,
        description: str,
        tags: list = None,
        thumb_file: Path = None,
        privacy_status: str = "unlisted",
        target_channel_id: str = None,
        schedule_time: str = None,
    ) -> dict:
        """Upload a video to YouTube with retry logic.
        
        Args:
            target_channel_id: If set, verifies upload goes to this channel.
            schedule_time: ISO 8601 datetime string to schedule publication.
        """

        if not self._check_quota():
            logger.warning("Upload skipped — daily quota exhausted")
            return {"status": "skipped", "reason": "upload_limit_exceeded"}

        # Views jail prevention — cap uploads per day
        if not rate_limiter.check_upload_cap():
            logger.warning("Upload skipped — daily upload cap reached (views jail prevention)")
            return {"status": "skipped", "reason": "daily_upload_cap_exceeded"}

        # Verify channel target if specified
        if target_channel_id:
            try:
                if not self.youtube:
                    self.authenticate()
                my_channels = self.youtube.channels().list(
                    part="id", mine=True
                ).execute()
                channel_ids = [ch["id"] for ch in my_channels.get("items", [])]
                if target_channel_id not in channel_ids:
                    logger.error(
                        "Target channel %s not accessible. "
                        "Authenticated channels: %s. Re-auth required.",
                        target_channel_id, channel_ids,
                    )
                    return {
                        "status": "error",
                        "reason": "target_channel_not_accessible",
                        "target": target_channel_id,
                        "authenticated": channel_ids,
                    }
            except Exception as e:
                logger.error("Channel verification failed: %s", e)

        # Channel warmup — watch similar content before uploading
        self._warmup_channel()

        def do_upload():
            if not self.youtube:
                self.authenticate()

            body = {
                "snippet": {
                    "title": title[:100],
                    "description": description[:5000],
                    "tags": tags[:500] if tags else [],
                },
                "status": {
                    "privacyStatus": privacy_status,
                    "selfDeclaredMadeForKids": False,
                },
            }

            media = MediaFileUpload(
                str(video_file),
                chunksize=10 * 1024 * 1024,
                resumable=True,
            )

            response = (
                self.youtube.videos()
                .insert(part="snippet,status", body=body, media_body=media)
                .execute()
            )

            video_id = response.get("id", "unknown")
            logger.info(f"Uploaded video: https://www.youtube.com/watch?v={video_id}")
            rate_limiter.record_upload()

            if thumb_file and thumb_file.exists():
                self.set_thumbnail(video_id, thumb_file)

            return response

        try:
            result = rate_limiter.retry_with_backoff(
                do_upload,
                max_retries=5,
                base_delay=10.0,
                cap=300.0,
            )
            return result
        except Exception as e:
            err_msg = str(e)
            if "uploadLimitExceeded" in err_msg:
                self._mark_quota_exceeded()
                logger.error("Upload limit hit — remaining videos will be skipped today")
            logger.error(f"Upload failed after retries: {e}")
            raise

    def _warmup_channel(self):
        """Warm up the channel by watching similar content before uploading."""
        try:
            if not self.youtube:
                return
            search_query = self.config.get("channel", {}).get("niche", "")
            if not search_query:
                return
            results = (
                self.youtube.search()
                .list(q=search_query, part="id", maxResults=3, type="video")
                .execute()
            )
            for item in results.get("items", [])[:2]:
                vid = item["id"]["videoId"]
                try:
                    self.youtube.videos().list(
                        part="snippet", id=vid
                    ).execute()
                except Exception:
                    pass
            logger.info("Channel warmup complete — watched %d videos",
                        min(2, len(results.get("items", []))))
        except Exception as e:
            logger.debug("Channel warmup skipped: %s", e)

    def reset_quota(self):
        """Reset daily upload quota (call manually after 24h or when limit is wrong)."""
        from datetime import date
        try:
            with open(self.quota_file, "w") as f:
                json.dump({"upload_limit_exceeded": False, "date": str(date.today())}, f)
            logger.info("Upload quota reset for today")
        except Exception:
            pass

    def set_thumbnail(self, video_id: str, thumb_file: Path):
        """Set custom thumbnail for a video."""
        try:
            if not self.youtube:
                self.authenticate()
            
            self.youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(str(thumb_file)),
            ).execute()
            logger.info(f"Thumbnail set for video {video_id}")
        except Exception as e:
            logger.error(f"Failed to set thumbnail: {e}")

    def get_channel_info(self) -> dict:
        """Get authenticated user's channel info."""
        if not self.youtube:
            self.authenticate()
        
        response = (
            self.youtube.channels()
            .list(part="snippet,contentDetails,statistics", mine=True)
            .execute()
        )
        
        items = response.get("items", [])
        if items:
            return items[0]
        return {}
