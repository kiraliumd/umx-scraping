from fastapi import FastAPI, Request
import uvicorn
import os
import re
from supabase import create_client, Client
from dotenv import load_dotenv

# Carregar configurações
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

app = FastAPI()

@app.get("/")
async def root():
    return {"status": "online", "message": "Servidor de SMS pronto!"}

@app.post("/sms")
async def receive_sms(request: Request):
    try:
        # Recebe os dados do App Android
        data = await request.json()
        print(f"\n📩 SMS RECEBIDO: {data}")
        
        from_number = data.get("from_number", "Desconhecido")
        text = data.get("text", "")
        
        # Salva no Supabase
        res = supabase.table("sms_logs").insert({
            "from_number": from_number,
            "text": text
        }).execute()
        
        print(f"✅ Salvo no Supabase com sucesso!")
        return {"status": "success"}
        
    except Exception as e:
        print(f"❌ Erro ao processar SMS: {e}")
        return {"status": "error", "message": str(e)}, 400

if __name__ == "__main__":
    # Roda o servidor na porta 8080
    print("Iniciando servidor na porta 8080...")
    uvicorn.run(app, host="0.0.0.0", port=8080)
