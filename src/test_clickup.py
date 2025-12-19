
import asyncio
import os
import httpx
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.environ.get("CLICKUP_API_KEY")
LIST_ID = os.environ.get("CLICKUP_LIST_ID")

async def test_clickup():
    print(f"Testing ClickUp Integration...")
    print(f"API Key: {API_KEY[:5]}...{API_KEY[-5:] if API_KEY else ''}")
    print(f"List ID: {LIST_ID}")
    
    if not API_KEY or not LIST_ID:
        print("Missing credentials in .env")
        return

    url = f"https://api.clickup.com/api/v2/list/{LIST_ID}"
    headers = {"Authorization": API_KEY}
    
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=headers)
        
        if resp.status_code == 200:
            print("✅ SUCCESS: Credentials are valid!")
            data = resp.json()
            print(f"List Name: {data.get('name')}")
        else:
            print(f"❌ FAILED: Status {resp.status_code}")
            print(f"Response: {resp.text}")
            print("Hint: Check if API Key starts with 'pk_' and List ID is numeric.")

if __name__ == "__main__":
    asyncio.run(test_clickup())
