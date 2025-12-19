
import httpx
import asyncio

API_URL = "http://127.0.0.1:50325"

ENDPOINTS = [
    "/api/v1/browser/start?user_id=test",
    "/api/v1/browser/active",
    "/api/v1/calendar/list",
    "/api/v1/user/start?user_id=test" # Retry with param
]

async def probe():
    async with httpx.AsyncClient() as client:
        print(f"Probing {API_URL}...")
        
        for ep in ENDPOINTS:
            url = f"{API_URL}{ep}"
            try:
                resp = await client.get(url, timeout=5)
                print(f"[{resp.status_code}] {ep} -> {resp.text[:100]}")
            except Exception as e:
                print(f"[ERR] {ep} -> {e}")

if __name__ == "__main__":
    asyncio.run(probe())
