
import httpx
import logging
import os

logger = logging.getLogger(__name__)

# Constants (Should be in .env)
# Using os.environ.get with defaults or raising warning if not present
CLICKUP_API_KEY = os.environ.get("CLICKUP_API_KEY", "")

async def send_message(list_id, message_text):
    """
    Sends a message (comment) to a ClickUp List (Chat).
    """
    if not CLICKUP_API_KEY or not list_id:
        logger.warning("ClickUp credentials or List ID missing for message.")
        return False

    if str(list_id).isdigit():
        url = f"https://api.clickup.com/api/v2/list/{list_id}/comment"
    else:
        # Assumes View ID (Chat)
        url = f"https://api.clickup.com/api/v2/view/{list_id}/comment"
    headers = {
        "Authorization": CLICKUP_API_KEY,
        "Content-Type": "application/json"
    }
    
    payload = {
        "comment_text": message_text,
        "notify_all": False
    }
    
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code == 200:
                logger.info("ClickUp message sent successfully.")
                return True
            else:
                logger.error(f"ClickUp Message Error: {resp.status_code} - {resp.text}")
                return False
    except Exception as e:
        logger.error(f"ClickUp Message Exception: {e}")
        return False
