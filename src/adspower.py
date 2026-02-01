
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
            "window_size": "1920,1080",
            "window_pos": "0,0",
            "resolution": "1920x1080",
            "launch_args": '["--start-maximized", "--window-size=1920,1080", "--force-device-scale-factor=1"]'
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
    async def get_profile_details(user_id):
        """
        Retrieves the full details of a profile.
        """
        url = f"{ADSPOWER_API_URL}/api/v1/user/list?user_id={user_id}"
        headers = {"Authorization": f"Bearer {ADSPOWER_API_KEY}"}
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, headers=headers, timeout=10)
                data = resp.json()
                if data.get("code") == 0 and "data" in data and "list" in data["data"]:
                    user_list = data["data"]["list"]
                    if user_list:
                        return user_list[0]
            return None
        except Exception as e:
            logger.error(f"AdsPower API Error (get_profile_details): {e}")
            return None

    @staticmethod
    async def update_proxy_config(user_id, proxy_config):
        """
        Updates the proxy configuration for a profile.
        """
        url = f"{ADSPOWER_API_URL}/api/v1/user/update"
        headers = {"Authorization": f"Bearer {ADSPOWER_API_KEY}"}
        payload = {
            "user_id": user_id,
            "user_proxy_config": proxy_config
        }
        try:
            logger.info(f"Updating proxy config for profile {user_id}...")
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, json=payload, headers=headers, timeout=20)
                data = resp.json()
                if data.get("code") == 0:
                    logger.info(f"Successfully updated proxy for {user_id}")
                    return True
                else:
                    logger.error(f"Failed to update proxy for {user_id}: {data}")
                    return False
        except Exception as e:
            logger.error(f"AdsPower API Error (update_proxy_config): {e}")
            return False

    @staticmethod
    async def get_profile_name(user_id):
        """
        Retrieves the friendly name of the profile.
        Returns user_id if name not found or on error.
        """
        details = await AdsPowerController.get_profile_details(user_id)
        if details:
            name = details.get("name")
            if name:
                return name
        return user_id # Fallback
