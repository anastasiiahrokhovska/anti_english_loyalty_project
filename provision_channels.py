import csv
import json
import os
import re
import secrets
from datetime import datetime
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, auth, db

DATABASE_URL = os.getenv(
    "FIREBASE_DATABASE_URL",
    "https://aneienglishloyaltyproject-default-rtdb.europe-west1.firebasedatabase.app",
)
SERVICE_ACCOUNT_JSON = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")


def login_email(channel: str) -> str:
    value = channel.strip().removeprefix("@").lower()
    value = re.sub(r"[^a-z0-9._-]", "-", value)
    value = re.sub(r"-+", "-", value).strip("-.")
    if len(value) < 2:
        raise ValueError(f"Invalid channel handle: {channel}")
    return value + "@channels.aneienglish.com"


def main():
    if not SERVICE_ACCOUNT_JSON:
        raise SystemExit(
            "Set FIREBASE_SERVICE_ACCOUNT_JSON to the JSON contents of a Firebase "
            "service-account key. Never commit that key to GitHub."
        )
    if not firebase_admin._apps:
        firebase_admin.initialize_app(
            credentials.Certificate(json.loads(SERVICE_ACCOUNT_JSON)),
            {"databaseURL": DATABASE_URL},
        )

    seed_path = Path(__file__).with_name("channels_seed.json")
    seed = json.loads(seed_path.read_text(encoding="utf-8"))
    accounts = seed["accounts"]

    emails = [login_email(item["channel"]) for item in accounts]
    if len(set(emails)) != len(emails):
        raise SystemExit("Duplicate login IDs after normalization. Resolve them before provisioning.")

    credentials_to_deliver = []
    created_count = 0
    updated_count = 0
    for item in accounts:
        channel = item["channel"]
        email = login_email(channel)
        participations = int(item.get("recordedParticipations", item.get("stamps", 0)))
        stamps = min(participations, 7)
        try:
            user = auth.get_user_by_email(email)
            action = "existing"
        except auth.UserNotFoundError:
            password = secrets.token_urlsafe(12)
            user = auth.create_user(email=email, password=password, display_name=channel)
            credentials_to_deliver.append({
                "channel": channel,
                "login": channel,
                "password": password,
                "uid": user.uid,
            })
            action = "created"

        profile_ref = db.reference(f"channel_accounts/{user.uid}")
        old_profile = profile_ref.get() or {}
        profile_ref.update({
            "channel": channel,
            "stamps": min(int(old_profile.get("stamps", stamps)), 7),
            "recordedParticipations": int(old_profile.get("recordedParticipations", participations)),
            "freeRewardAvailable": stamps >= 7,
            "freeRewardsUsed": int(old_profile.get("freeRewardsUsed", 0)),
            "accountProvisioned": True,
        })
        if action == "created":
            created_count += 1
        else:
            updated_count += 1
            print(f"Existing login found for {channel}; password was not changed or exported.")

    if credentials_to_deliver:
        out = Path.home() / f"ANEI_channel_credentials_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        with out.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=["channel", "login", "password", "uid"])
            writer.writeheader()
            writer.writerows(credentials_to_deliver)
        try:
            out.chmod(0o600)
        except OSError:
            pass
        print(f"Created {created_count} accounts. New passwords saved locally to: {out}")
        print("Send each password privately to its channel owner, then securely delete the CSV.")
    else:
        print("No new accounts were created, so no password CSV was generated.")
    print(f"Updated {updated_count} existing account profiles.")
    print("Verify the Firebase Database Rules before giving anyone access.")


if __name__ == "__main__":
    main()
