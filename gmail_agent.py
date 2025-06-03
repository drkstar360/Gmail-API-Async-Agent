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
import base64
import quopri
from bs4 import BeautifulSoup

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

# Helper function for decoding email body data
def _decode_part_data(data_string: str) -> str:
    """Decodes base64url encoded string, with fallback for quopri and utf-8 errors."""
    if not data_string:
        return ""
    
    # Add correct padding for base64url
    padding = '=' * (-len(data_string) % 4)
    try:
        decoded_bytes = base64.urlsafe_b64decode(data_string + padding)
    except Exception: # Catch base64 decoding errors
        # If base64 decoding itself fails, return empty or log an error
        return ""

    try:
        # Try decoding as UTF-8 first
        return decoded_bytes.decode('utf-8')
    except UnicodeDecodeError:
        # If UTF-8 fails, try quoted-printable, then decode its result as UTF-8
        try:
            # quopri.decodestring expects bytes
            quopri_decoded_bytes = quopri.decodestring(decoded_bytes)
            return quopri_decoded_bytes.decode('utf-8', errors='replace')
        except Exception:
            # If quopri or its subsequent decode fails, fallback to decoding original bytes with 'replace'
            return decoded_bytes.decode('utf-8', errors='replace')
    except Exception:
        # Catch any other unforeseen errors during decoding attempts
        return ""

def extract_message_text(payload: Dict[str, Any]) -> str:
    """
    Extracts and concatenates all plain text content from the message payload parts.
    Prioritizes text/plain parts using a depth-first traversal.
    """
    collected_texts = []
    parts_to_visit = [payload]  # Start with the main payload

    while parts_to_visit:
        current_part = parts_to_visit.pop() # Depth-First Search
        mime_type = current_part.get("mimeType", "")

        if mime_type == "text/plain":
            body = current_part.get("body", {})
            data = body.get("data")
            if data:
                decoded_text = _decode_part_data(data)
                if decoded_text:
                    collected_texts.append(decoded_text)
        elif mime_type == "text/html":
            body = current_part.get("body", {})
            data = body.get("data")
            if data:
                decoded_html = _decode_part_data(data)
                if decoded_html:
                    soup = BeautifulSoup(decoded_html, "html.parser")
                    extracted_text = soup.get_text(separator="\n", strip=True)
                    if extracted_text:
                        collected_texts.append(extracted_text)
        
        # If the current part is multipart, add its sub-parts to the stack for further processing.
        # Add them in reversed order so that pop() processes them in their original order (maintaining DFS behavior).
        if mime_type.startswith("multipart/"):
            sub_parts = current_part.get("parts", [])
            for sub_part in reversed(sub_parts): # Add children to stack
                parts_to_visit.append(sub_part)
                
    # The order of collected_texts might be reversed from the visual order in complex emails
    # depending on DFS traversal. Reversing here attempts to restore a more natural top-to-bottom flow.
    return "\n".join(reversed(collected_texts)).strip() 