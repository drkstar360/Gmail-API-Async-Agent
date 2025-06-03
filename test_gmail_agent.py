import pytest
import asyncio
from typing import Dict, Any, List
from unittest.mock import patch, AsyncMock
from gmail_agent import fetch_gmail_summary, GMAIL_FIELDS, httpx

@pytest.mark.asyncio
async def test_fetch_gmail_summary_normal():
    """
    Test fetch_gmail_summary with all fields present in the payload.
    """
    labels_data = {"labels": [{"id": "INBOX", "name": "INBOX"}]}
    profile_data = {"emailAddress": "user@example.com", "messagesTotal": 100}
    messages_data = {"messages": [{"id": "msg1"}, {"id": "msg2"}]}
    message_detail_1 = {
        "id": "msg1",
        "threadId": "th1",
        "internalDate": "1680000000000",
        "labelIds": ["INBOX"],
        "payload": {
            "headers": [
                {"name": "From", "value": "sender1@example.com"},
                {"name": "Subject", "value": "Test Subject 1"}
            ],
            "body": {"data": "SGVsbG8gd29ybGQh"}  # "Hello world!"
        }
    }
    message_detail_2 = {
        "id": "msg2",
        "threadId": "th2",
        "internalDate": "1680000001000",
        "labelIds": ["INBOX"],
        "payload": {
            "headers": [
                {"name": "From", "value": "sender2@example.com"},
                {"name": "Subject", "value": "Test Subject 2"}
            ],
            "body": {"data": "VGVzdCBib2R5"}  # "Test body"
        }
    }

    async def mock_side_effect_func(client_instance_self, url_passed, *args, **kwargs):
        class MockResp:
            def __init__(self, data):
                self._data = data
            def json(self):
                return self._data
            @property
            def status_code(self):
                return 200

        if not isinstance(url_passed, str):
            raise TypeError(f"URL argument in mock_side_effect is not a string! Got: {type(url_passed)}")

        if url_passed.endswith('/labels'):
            return MockResp(labels_data)
        elif url_passed.endswith('/profile'):
            return MockResp(profile_data)
        elif url_passed.endswith('/messages') and kwargs.get("params", {}).get("maxResults") == 10:
            return MockResp(messages_data)
        elif url_passed.endswith('/messages/msg1'):
            return MockResp(message_detail_1)
        elif url_passed.endswith('/messages/msg2'):
            return MockResp(message_detail_2)
        else:
            return MockResp({})

    with patch.object(httpx.AsyncClient, 'get', autospec=True) as mock_get_call:
        mock_get_call.side_effect = mock_side_effect_func
        
        result = await fetch_gmail_summary('dummy_token')
        assert 'labels' in result
        assert 'profile' in result
        assert 'emails' in result
        assert len(result['emails']) == 2
        for email in result['emails']:
            for field in GMAIL_FIELDS:
                assert field in email
        assert result['emails'][0]['messageText'] == 'Hello world!'
        assert result['emails'][1]['messageText'] == 'Test body'

@pytest.mark.asyncio
async def test_fetch_gmail_summary_missing_fields():
    """
    Test fetch_gmail_summary with some optional fields missing in the payload.
    """
    labels_data = {"labels": []}
    profile_data = {"emailAddress": "user@example.com"}
    messages_data = {"messages": [{"id": "msg1"}]}
    message_detail_1 = {
        "id": "msg1",
        "payload": {
            "headers": [
                {"name": "Subject", "value": "No Sender"}
            ],
            "parts": [
                {
                    "mimeType": "text/plain",
                    "body": {"data": "V2l0aG91dCBib2R5"}  # "Without body"
                }
            ]
        }
    }

    async def mock_side_effect_func(client_instance_self, url_passed, *args, **kwargs):
        class MockResp:
            def __init__(self, data):
                self._data = data
            def json(self):
                return self._data
            @property
            def status_code(self):
                return 200
        
        if not isinstance(url_passed, str):
            raise TypeError(f"URL argument in mock_side_effect is not a string! Got: {type(url_passed)}")

        if url_passed.endswith('/labels'):
            return MockResp(labels_data)
        elif url_passed.endswith('/profile'):
            return MockResp(profile_data)
        elif url_passed.endswith('/messages') and kwargs.get("params", {}).get("maxResults") == 10:
            return MockResp(messages_data)
        elif url_passed.endswith('/messages/msg1'):
            return MockResp(message_detail_1)
        else:
            return MockResp({})

    with patch.object(httpx.AsyncClient, 'get', autospec=True) as mock_get_call:
        mock_get_call.side_effect = mock_side_effect_func

        result = await fetch_gmail_summary('dummy_token')
        assert 'labels' in result
        assert 'profile' in result
        assert 'emails' in result
        assert len(result['emails']) == 1
        email = result['emails'][0]
        assert email['messageId'] == 'msg1'
        assert email['threadId'] is None
        assert email['messageTimestamp'] is None
        assert email['labelIds'] == []
        assert email['sender'] is None
        assert email['subject'] == 'No Sender'
        assert email['messageText'] == 'Without body' 