"""
Monetization tracker — tracks progress toward YouTube Partner Program (YPP).

YPP requirements (2026):
  - 1,000 subscribers
  - 4,000 watch hours (or 10M Shorts views) in past 12 months
  - Follow YouTube monetization policies

Also tracks:
  - Video count toward milestones (100, 250, 500, 600, 1000)
  - Niche RPM potential scoring
  - Estimated revenue per niche/category
"""

import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# YPP thresholds
YPP_SUBSCRIPTHRESHOLD = 1_000
YPP_WATCH_HOURS = 4_000
YPP_SHORTS_VIEWS = 10_000_000

# Monetization milestones
VIDEO_MILESTONES = [100, 250, 500, 600, 1000]

# RPM estimates by niche (BRL per 1000 views, rough 2026 SA averages)
NICHE_RPM = {
    "health": 8.0,
    "wealth": 12.0,
    "relationships": 6.0,
    "sports": 5.0,
    "technology": 10.0,
    "finance": 14.0,
    "education": 7.0,
    "entertainment": 4.0,
    "general": 5.0,
}

# SA tax/platform fee estimate
PLATFORM_FEE = 0.45  # 45% YouTube cuts


class MonetizationTracker:
    """Track YPP progress and revenue estimates."""

    def __init__(self, tracker_file: Optional[Path] = None):
        self.tracker_file = tracker_file or Path("data/monetization.json")
        self.tracker_file.parent.mkdir(parents=True, exist_ok=True)
        self.data = self._load()

    def _load(self) -> dict:
        if self.tracker_file.exists():
            try:
                with open(self.tracker_file, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        return {
            "subscribers": 0,
            "watch_hours": 0.0,
            "shorts_views": 0,
            "video_count": 0,
            "niche_stats": {},
            "last_updated": "",
            "ypp_checked": False,
        }

    def save(self):
        self.data["last_updated"] = str(date.today())
        try:
            with open(self.tracker_file, "w") as f:
                json.dump(self.data, f, indent=2)
        except OSError:
            pass

    def update_stats(self, subscribers: int = None, watch_hours: float = None,
                     shorts_views: int = None, video_count: int = None):
        """Update channel stats."""
        if subscribers is not None:
            self.data["subscribers"] = subscribers
        if watch_hours is not None:
            self.data["watch_hours"] = watch_hours
        if shorts_views is not None:
            self.data["shorts_views"] = shorts_views
        if video_count is not None:
            self.data["video_count"] = video_count
        self.save()

    def ypp_status(self) -> dict:
        """Return current YPP eligibility status."""
        subs = self.data.get("subscribers", 0)
        hours = self.data.get("watch_hours", 0.0)
        shorts = self.data.get("shorts_views", 0)

        subs_needed = max(0, YPP_SUBSCRIPTHRESHOLD - subs)
        hours_needed = max(0, YPP_WATCH_HOURS - hours)
        shorts_needed = max(0, YPP_SHORTS_VIEWS - shorts)

        eligible = (subs >= YPP_SUBSCRIPTHRESHOLD and
                    (hours >= YPP_WATCH_HOURS or shorts >= YPP_SHORTS_VIEWS))

        return {
            "eligible": eligible,
            "subscribers": subs,
            "subs_needed": subs_needed,
            "watch_hours": hours,
            "hours_needed": hours_needed,
            "shorts_views": shorts,
            "shorts_needed": shorts_needed,
            "method": "shorts" if shorts >= YPP_SHORTS_VIEWS else "watch_hours",
        }

    def video_milestone(self, count: int = None) -> dict:
        """Check which milestones have been reached."""
        c = count or self.data.get("video_count", 0)
        reached = [m for m in VIDEO_MILESTONES if c >= m]
        next_milestone = next((m for m in VIDEO_MILESTONES if m > c), None)
        return {
            "video_count": c,
            "reached": reached,
            "next_milestone": next_milestone,
            "videos_to_next": next_milestone - c if next_milestone else 0,
        }

    def niche_rpm(self, niche: str) -> float:
        """Get estimated RPM for a niche (BRL per 1000 views)."""
        return NICHE_RPM.get(niche, NICHE_RPM.get("general", 5.0))

    def estimated_revenue(self, views: int, niche: str = "general") -> dict:
        """Estimate gross/net revenue for a view count and niche."""
        rpm = self.niche_rpm(niche)
        gross = (views / 1000) * rpm
        net = gross * (1 - PLATFORM_FEE)
        return {
            "views": views,
            "niche": niche,
            "rpm": rpm,
            "gross_brl": round(gross, 2),
            "net_brl": round(net, 2),
            "platform_cut_pct": PLATFORM_FEE * 100,
        }

    def record_video(self, video_id: str, title: str, niche: str = "general",
                     views: int = 0):
        """Record a video and update niche stats."""
        if "niche_stats" not in self.data:
            self.data["niche_stats"] = {}
        ns = self.data["niche_stats"]
        if niche not in ns:
            ns[niche] = {"videos": 0, "total_views": 0, "total_revenue": 0.0}
        ns[niche]["videos"] += 1
        ns[niche]["total_views"] += views
        if views > 0:
            rev = self.estimated_revenue(views, niche)
            ns[niche]["total_revenue"] += rev["net_brl"]
        self.data["video_count"] = self.data.get("video_count", 0) + 1
        self.save()

    def track_upload(self, video_id: str, title: str, test_variable: str = "",
                     retention_notes: str = "", hook_style: str = ""):
        """Record per-upload analytics for iterative testing.

        Tracks what changed between uploads (perception-breaking hooks,
        test variables, retention observations) — mirrors the Google Sheet
        approach from the viral case study.
        """
        if "upload_history" not in self.data:
            self.data["upload_history"] = []
        self.data["upload_history"].append({
            "video_id": video_id,
            "title": title,
            "test_variable": test_variable,
            "retention_notes": retention_notes,
            "hook_style": hook_style,
            "date_uploaded": str(date.today()),
        })
        if len(self.data["upload_history"]) > 100:
            self.data["upload_history"] = self.data["upload_history"][-100:]
        self.save()

    def get_upload_history(self) -> list:
        """Return upload history for analysis."""
        return self.data.get("upload_history", [])

    def record_apv(self, video_id: str, apv: float, view_count: int = 0):
        """Record Average Percentage Viewed for a video."""
        if "apv_records" not in self.data:
            self.data["apv_records"] = []
        self.data["apv_records"].append({
            "video_id": video_id,
            "apv_pct": apv,
            "view_count": view_count,
            "date_uploaded": str(date.today()),
        })
        if len(self.data["apv_records"]) > 50:
            self.data["apv_records"] = self.data["apv_records"][-50:]
        self.save()

    def get_apv_status(self) -> dict:
        """Return APV-based push status from viral case study."""
        records = self.data.get("apv_records", [])
        if not records:
            return {"has_data": False, "message": "No APV data recorded yet"}
        latest = records[-1]
        apv = latest["apv_pct"]
        if apv >= 85:
            status, message = "strong_push", f"APV {apv}% — YouTube pushing aggressively"
        elif apv >= 80:
            status, message = "moderate_push", f"APV {apv}% — YouTube pushing"
        elif apv >= 70:
            status, message = "stable", f"APV {apv}% — Push may be slowing"
        else:
            status, message = "declining", f"APV {apv}% — Push likely declining"
        return {
            "has_data": True,
            "latest_apv": apv,
            "status": status,
            "message": message,
            "total_uploads": len(records),
        }

    def monetization_report(self) -> str:
        """Generate a human-readable monetization report."""
        ypp = self.ypp_status()
        milestone = self.video_milestone()
        lines = [
            "=== Monetization Report ===",
            f"Subscribers: {ypp['subscribers']} (need {ypp['subs_needed']} more)",
            f"Watch Hours: {ypp['watch_hours']:.0f}h (need {ypp['hours_needed']:.0f}h more)",
            f"Shorts Views: {ypp['shorts_views']:,} (need {ypp['shorts_needed']:,} more)",
            f"YPP Eligible: {'YES' if ypp['eligible'] else 'NO'}",
            f"Videos: {milestone['video_count']} | Milestones: {milestone['reached']}",
            f"Next Milestone: {milestone['next_milestone']} "
            f"({milestone['videos_to_next']} more videos)",
        ]
        for niche, stats in self.data.get("niche_stats", {}).items():
            rpm = self.niche_rpm(niche)
            lines.append(
                f"  {niche}: {stats['videos']} videos, "
                f"{stats['total_views']:,} views, "
                f"RPM ~R${rpm:.0f}, "
                f"est. net R${stats['total_revenue']:.2f}"
            )
        return "\n".join(lines)