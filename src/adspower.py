
import httpx
import logging
import asyncio

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ADSPOWER_API_URL = "http://127.0.0.1:50325"
ADSPOWER_API_KEY = "e9d694deca25694a99bb4b6590725de4"

class AdsPowerController:
    @staticmethod
    async def start_profile(user_id):
        """
        Starts an AdsPower profile by user_id.
        Returns the WebSocket Endpoint for CDP connection (puppeteer/playwright).
        """

        # Endpoint Updated: /api/v1/browser/start
        url = f"{ADSPOWER_API_URL}/api/v1/browser/start"
        params = {
            "user_id": user_id,
            "open_tabs": "1",
            "launch_args": '["--start-maximized"]'
        }
        headers = {
            "Authorization": f"Bearer {ADSPOWER_API_KEY}"
        }
        try:
            logger.info(f"Starting AdsPower profile: {user_id} with maximized window...")
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, params=params, headers=headers, timeout=30)
                
                try:
                    data = resp.json()
                except Exception:
                    logger.error(f"Failed to parse JSON. Status: {resp.status_code}, Body: {resp.text}")
                    return None
                
                if data.get("code") == 0:
                    ws_endpoint = data["data"]["ws"]["puppeteer"]
                    logger.info(f"Profile {user_id} started. WS: {ws_endpoint}")
                    return ws_endpoint
                else:
                    logger.error(f"Failed to start profile {user_id}: {data}")
                    return None
        except Exception as e:
            logger.error(f"AdsPower API Error: {e}")
            return None

    @staticmethod
    async def stop_profile(user_id):
        """
        Stops an AdsPower profile by user_id.
        """
        # Endpoint Updated: /api/v1/browser/stop
        url = f"{ADSPOWER_API_URL}/api/v1/browser/stop?user_id={user_id}"
        headers = {
            "Authorization": f"Bearer {ADSPOWER_API_KEY}"
        }
        try:
            logger.info(f"Stopping AdsPower profile: {user_id}...")
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, headers=headers, timeout=10)
                data = resp.json()
                if data.get("code") == 0:
                    logger.info(f"Profile {user_id} stopped.")
                    return True
                else:
                    logger.warning(f"Failed to stop profile {user_id}: {data}")
                    return False
        except Exception as e:
            logger.error(f"AdsPower API Error: {e}")
            return False

    @staticmethod
    async def get_profile_name(user_id):
        """
        Retrieves the friendly name of the profile.
        Returns user_id if name not found or on error.
        """
        url = f"{ADSPOWER_API_URL}/api/v1/user/list?user_id={user_id}"
        headers = {
            "Authorization": f"Bearer {ADSPOWER_API_KEY}"
        }
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, headers=headers, timeout=10)
                data = resp.json()
                
                if data.get("code") == 0 and "data" in data and "list" in data["data"]:
                    user_list = data["data"]["list"]
                    if user_list and len(user_list) > 0:
                         name = user_list[0].get("name")
                         if name:
                             return name
                             
                logger.warning(f"Profile Name not found for {user_id}")
                return user_id # Fallback
        except Exception as e:
            logger.error(f"AdsPower API Error (get_profile_name): {e}")
            return user_id
