#!/usr/bin/env python3
"""One-time YouTube OAuth authorization script.
Run this ONCE in a terminal (not daemon) to generate token.json with upload permissions.
Keep this window open until the browser login completes.
"""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

TOKEN_FILE = BASE_DIR / "token.json"
CLIENT_SECRET_FILE = BASE_DIR / "client_secret.json"
SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]

def main():
    if not CLIENT_SECRET_FILE.exists():
        print(f"ERROR: {CLIENT_SECRET_FILE} not found")
        sys.exit(1)

    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if creds and creds.valid:
        print("Token already exists and is valid.")
    elif creds and creds.expired and creds.refresh_token:
        print("Refreshing expired token...")
        creds.refresh(Request())
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
        print("Token refreshed.")
    else:
        print("Starting OAuth flow - browser window will open...")
        print("Log in with the Google account linked to your YouTube channel.")
        print("If you have a Brand Account, select it when prompted.\n")

        flow = InstalledAppFlow.from_client_secrets_file(
            str(CLIENT_SECRET_FILE), SCOPES
        )
        print("Consent screen should appear. Select your account and grant permissions.\n")
        creds = flow.run_local_server(
            port=0, access_type='offline', prompt='consent'
        )

        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
        print(f"\nToken saved to {TOKEN_FILE}")

    # Verify
    youtube = build("youtube", "v3", credentials=creds)
    response = youtube.channels().list(part="snippet", mine=True).execute()
    items = response.get("items", [])
    if items:
        ch = items[0]["snippet"]
        print(f"\nAuthorized for: {ch['title']} ({items[0]['id']})")
    else:
        print("\nNo channels found. Check that you signed into the correct account.")

if __name__ == "__main__":
    main()
