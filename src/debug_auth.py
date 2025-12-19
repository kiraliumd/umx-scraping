
import httpx
import asyncio

API_URL = "http://127.0.0.1:50325"
API_KEY = "e9d694deca25694a99bb4b6590725de4"

async def test_auth():
    async with httpx.AsyncClient() as client:
        print(f"Testing Auth on {API_URL}...\n")
        
        # Scenario 1: Query Param 'api_key' (Current)
        url = f"{API_URL}/api/v1/browser/active?api_key={API_KEY}"
        resp = await client.get(url)
        print(f"Query 'api_key': {resp.status_code} - {resp.json()}")

        # Scenario 2: Query Param 'key'
        url = f"{API_URL}/api/v1/browser/active?key={API_KEY}"
        resp = await client.get(url)
        print(f"Query 'key': {resp.status_code} - {resp.json()}")

        # Scenario 3: Header 'api-key'
        url = f"{API_URL}/api/v1/browser/active"
        headers = {"api-key": API_KEY}
        resp = await client.get(url, headers=headers)
        print(f"Header 'api-key': {resp.status_code} - {resp.json()}")

        # Scenario 4: Header 'Authorization'
        headers = {"Authorization": f"Bearer {API_KEY}"}
        resp = await client.get(url, headers=headers)
        print(f"Header 'Authorization': {resp.status_code} - {resp.json()}")

if __name__ == "__main__":
    asyncio.run(test_auth())
