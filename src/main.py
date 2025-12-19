from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from src.scraper import get_balance
import os
from supabase import create_client, Client

app = FastAPI()

# Supabase setup
url: str = os.environ.get("SUPABASE_URL", "")
key: str = os.environ.get("SUPABASE_KEY", "")
supabase: Client = None

if url and key:
    supabase = create_client(url, key)

class LoginRequest(BaseModel):
    username: str
    password: str

@app.get("/")
async def root():
    return {"message": "Livelo Scraper Service Running"}

@app.post("/check")
async def check_balance(request: LoginRequest):
    adspower_id = None
    if supabase:
        try:
            resp = supabase.table("accounts").select("adspower_user_id").eq("username", request.username).execute()
            if resp.data:
                adspower_id = resp.data[0].get("adspower_user_id")
        except Exception as e:
            print(f"DB Error in API: {e}")

    result = await get_balance(request.username, request.password, adspower_user_id=adspower_id)
    
    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result.get("message"))
        
    return result
