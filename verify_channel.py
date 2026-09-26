"""
Verify YouTube channel - list channels for the authenticated account.
"""

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

TOKEN_FILE = BASE_DIR / "token.json"
CLIENT_SECRET_FILE = BASE_DIR / "client_secret.json"
# Allow fallback if client_secret.json isn't in project root
if not CLIENT_SECRET_FILE.exists():
    CLIENT_SECRET_FILE = Path("C:/Users/Lenov-2026/Documents/YT_VICTOR_PROJECTS/client_secret.json")
SCOPES = ["https://www.googleapis.com/auth/youtube.readonly"]


def authenticate():
    """Authenticate with YouTube Data API."""
    creds = None
    
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    
    if not creds or not valid_creds(creds):
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing expired credentials...")
            creds.refresh(Request())
        elif CLIENT_SECRET_FILE.exists():
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CLIENT_SECRET_FILE), SCOPES
            )
            creds = flow.run_local_server(port=0)
        else:
            print(f"Client secret file not found at {CLIENT_SECRET_FILE}")
            return None
        
        with open(TOKEN_FILE, "w", encoding="utf-8") as f:
            f.write(creds.to_json())
    
    return build("youtube", "v3", credentials=creds)


def valid_creds(creds):
    """Check if credentials are valid."""
    return creds and creds.valid


def list_channels():
    """List available channels for this account."""
    youtube = authenticate()
    if not youtube:
        print("❌ Authentication failed.")
        return
    
    print("\n--- Checking available channels for this account ---\n")
    
    response = youtube.channels().list(part="snippet,contentDetails", mine=True).execute()
    items = response.get("items", [])
    
    if not items:
        print("❌ No channels found. You may need to create the channel on YouTube.com first.")
        return
    
    print(f"Found {len(items)} channel(s):")
    for i, item in enumerate(items, 1):
        snippet = item.get("snippet", {})
        title = snippet.get("title", "Unknown")
        channel_id = item.get("id", "Unknown")
        print(f"  {i}. {title} (ID: {channel_id})")
    
    print("\nIf 'TaeFour Sports Viral' is not listed, it hasn't propagated to the API yet.")
    print("Wait 10-30 minutes and try again.")


if __name__ == "__main__":
    list_channels()
