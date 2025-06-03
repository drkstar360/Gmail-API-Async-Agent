"""
Gmail Agent: Fetches user's labels, profile, and last 10 emails (async)

This module provides an async function to fetch a Gmail user's labels, profile, and the last 10 emails,
returning only essential fields for each email. It is designed for integration with the Gmail API and
filters out verbose data, returning only the following fields for each message:

GMAIL_FIELDS = [
    "messageId",
    "threadId",
    "messageTimestamp",
    "labelIds",
    "sender",
    "subject",
    "messageText",
]

Usage:
    await fetch_gmail_summary(access_token)

Args:
    access_token (str): OAuth2 access token for Gmail API.

Returns:
    dict: Dictionary with 'labels', 'profile', and 'emails' (list of dicts with only the required fields).
"""

from typing import List, Dict, Any
import httpx
import asyncio

GMAIL_FIELDS = [
    "messageId",
    "threadId",
    "messageTimestamp",
    "labelIds",
    "sender",
    "subject",
    "messageText",
]

async def fetch_gmail_summary(access_token: str) -> Dict[str, Any]:
    """
    Fetch user's labels, profile, and last 10 emails from Gmail API, returning only essential fields.

    Args:
        access_token (str): OAuth2 access token for Gmail API.

    Returns:
        dict: Dictionary with 'labels', 'profile', and 'emails' (list of dicts with only the required fields).
    """
    headers = {"Authorization": f"Bearer {access_token}"}
    base_url = "https://gmail.googleapis.com/gmail/v1/users/me"

    async with httpx.AsyncClient(headers=headers, timeout=30.0) as client:
        # Fetch labels, profile, and message list concurrently
        labels_task = client.get(f"{base_url}/labels")
        profile_task = client.get(f"{base_url}/profile")
        messages_task = client.get(f"{base_url}/messages", params={"maxResults": 10, "q": ""})
        labels_resp, profile_resp, messages_resp = await asyncio.gather(labels_task, profile_task, messages_task)
        labels = labels_resp.json()
        profile = profile_resp.json()
        messages = messages_resp.json()

        # Fetch each message's details concurrently
        message_ids = [msg["id"] for msg in messages.get("messages", [])]
        message_tasks = [client.get(f"{base_url}/messages/{msg_id}") for msg_id in message_ids]
        message_responses = await asyncio.gather(*message_tasks)
        message_jsons = [resp.json() for resp in message_responses]

        emails = [extract_essential_fields(msg) for msg in message_jsons]

        return {
            "labels": labels.get("labels", []),
            "profile": profile,
            "emails": emails,
        }

def extract_essential_fields(message: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract only the essential fields from a Gmail message resource.
    """
    payload = message.get("payload", {})
    headers = {h["name"]: h["value"] for h in payload.get("headers", [])}
    message_text = extract_message_text(payload)
    return {
        "messageId": message.get("id"),
        "threadId": message.get("threadId"),
        "messageTimestamp": int(message.get("internalDate", 0)) // 1000 if message.get("internalDate") else None,
        "labelIds": message.get("labelIds", []),
        "sender": headers.get("From"),
        "subject": headers.get("Subject"),
        "messageText": message_text,
    }

def extract_message_text(payload: Dict[str, Any]) -> str:
    """
    Extract plain text from the message payload.
    """
    if payload.get("body", {}).get("data"):
        import base64
        import quopri
        data = payload["body"]["data"]
        try:
            decoded_bytes = base64.urlsafe_b64decode(data + '==')
            try:
                return decoded_bytes.decode("utf-8")
            except UnicodeDecodeError:
                return quopri.decodestring(decoded_bytes).decode("utf-8", errors="replace")
        except Exception:
            return ""
    # If multipart, recursively search for text/plain
    for part in payload.get("parts", []):
        if part.get("mimeType") == "text/plain":
            return extract_message_text(part)
    return "" 