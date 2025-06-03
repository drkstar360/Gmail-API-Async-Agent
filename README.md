# Gmail API Async Agent

This project provides an async Python agent to fetch a Gmail user's labels, profile, and last 10 emails, returning only essential message details. It is designed for efficient integration with the Gmail API and filters out verbose data.

## Features
- Fetches user's labels and profile
- Fetches the last 10 emails (async, concurrent requests)
- Returns only the following fields for each email:
  - `messageId`
  - `threadId`
  - `messageTimestamp`
  - `labelIds`
  - `sender`
  - `subject`
  - `messageText`
- Handles missing/optional fields gracefully

## Usage
### **This script environment is initialized with `uv`. python version was 3.12

1. Install dependencies if you have `uv`:
   ```bash
   uv sync
   ```
   or
    ```bash
    pip install -r requirements.txt
    ```

2. Use the main function in your async code:
   ```python
   from gmail_agent import fetch_gmail_summary
   import asyncio

   # Replace with your OAuth2 access token
   access_token = "YOUR_ACCESS_TOKEN"
   result = asyncio.run(fetch_gmail_summary(access_token))
   print(result)
   ```

## Running Tests

Run all tests with:
```bash
pytest
```

The tests mock Gmail API responses and cover both normal and missing-field scenarios. 