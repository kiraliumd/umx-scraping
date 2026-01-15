import asyncio
import os
import sys
import logging
import time
from dotenv import load_dotenv
from supabase import create_client, Client
from playwright.async_api import async_playwright

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.scraper import extract_latam, AdsPowerController
from src.crypto_utils import decrypt_password

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

async def test_latam():
    print("=== LATAM Scraper Fast Test (LATAM ONLY) ===")
    
    # 1. Setup Supabase
    url: str = os.environ.get("SUPABASE_URL", "")
    key: str = os.environ.get("SUPABASE_KEY", "")
    supabase: Client = create_client(url, key)

    TARGET_ADSPOWER_ID = "k17ttays"
    
    # 2. Fetch Account
    response = supabase.table("accounts").select("*").eq("adspower_user_id", TARGET_ADSPOWER_ID).execute()
    if not response.data:
        print(f"Error: Account {TARGET_ADSPOWER_ID} not found.")
        return
    
    acc = response.data[0]
    username = acc['username']
    password = decrypt_password(acc['password'])
    latam_password = decrypt_password(acc['latam_password']) if acc.get('latam_password') else password

    print(f"Testing LATAM for: {username}")

    # 3. Start AdsPower
    ws_endpoint = await AdsPowerController.start_profile(TARGET_ADSPOWER_ID)
    if not ws_endpoint:
        print("Failed to start AdsPower profile.")
        return

    # 4. Run Playwright
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(ws_endpoint)
        context = browser.contexts[0] if browser.contexts else await browser.new_context(
            viewport={'width': 1920, 'height': 1080}
        )
        
        # Opcional: Maximizar via CDP se necessário
        try:
            temp_page = await context.new_page()
            session = await temp_page.context.new_cdp_session(temp_page)
            window_info = await session.send("Browser.getWindowForTarget")
            window_id = window_info.get("windowId")
            if window_id:
                await session.send("Browser.setWindowBounds", {
                    "windowId": window_id,
                    "bounds": {"windowState": "maximized"}
                })
            await temp_page.close()
        except: pass

        print("\nStarting LATAM Extraction...")
        start_time = time.time()
        
        result = await extract_latam(context, username, latam_password)
        
        duration = time.time() - start_time
        print(f"\nExtraction finished in {duration:.2f}s")
        print(f"Result: {result}")

if __name__ == "__main__":
    asyncio.run(test_latam())
