
import httpx
import logging
import os

logger = logging.getLogger(__name__)

# Constants (Should be in .env)
# Using os.environ.get with defaults or raising warning if not present
CLICKUP_API_KEY = os.environ.get("CLICKUP_API_KEY", "")
CLICKUP_LIST_ID = os.environ.get("CLICKUP_LIST_ID", "")

async def create_task(account_data, changes):
    """
    Creates a task in ClickUp for balance divergence.
    """
    if not CLICKUP_API_KEY or not CLICKUP_LIST_ID:
        logger.warning("ClickUp credentials not found. Skipping task creation.")
        return False

    username = account_data.get('username', 'Unknown')
    adspower_id = account_data.get('adspower_user_id', 'N/A')
    
    # Build Description
    description = []
    description.append(f"**AdsPower ID:** `{adspower_id}`")
    description.append(f"**Conta:** {username}")
    description.append("")
    description.append("### 📊 Divergência de Saldo Detectada")
    description.append("")
    
    for program, diff in changes.items():
        old = diff['old']
        new = diff['new']
        delta = new - old
        
        icon = "🔵" if program == "livelo" else "🔴"
        arrow = "🔼" if delta > 0 else "🔻"
        
        description.append(f"{icon} **{program.capitalize()}**")
        description.append(f"- Anterior: {old}")
        description.append(f"- Atual: **{new}**")
        description.append(f"- Diferença: {arrow} {delta}")
        description.append("")
        
    description.append("---")
    description.append("*Tarefa gerada automaticamente pelo UMX Scraper.*")
    
    payload = {
        "name": f"Divergência: {username}",
        "description": "\n".join(description),
        "priority": 3 # Normal
    }
    
    url = f"https://api.clickup.com/api/v2/list/{CLICKUP_LIST_ID}/task"
    headers = {
        "Authorization": CLICKUP_API_KEY,
        "Content-Type": "application/json"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code in [200, 201]:
                logger.info(f"ClickUp task created for {username}")
                return True
            else:
                logger.error(f"ClickUp API Error: {resp.status_code} - {resp.text}")
                return False
    except Exception as e:
        logger.error(f"ClickUp Exception: {e}")
        return False


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
