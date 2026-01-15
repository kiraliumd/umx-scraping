import httpx
import asyncio
import json

async def test_webhook():
    # URL completa com a chave anon que você forneceu
    url = "https://upvivegiqubfdddnnuie.supabase.co/rest/v1/sms_logs?apikey=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InVwdml2ZWdpcXViZmRkZG5udWllIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjUwMzI3NjEsImV4cCI6MjA4MDYwODc2MX0.D43Wr23LymXlxEqGQOScUeaMCvZwkR7mC6obclvdoyI"
    
    payload = {
        "from_number": "TEST_SENDER",
        "text": "999888 é o seu código de verificação na LATAM Airlines."
    }
    
    print(f"--- SIMULANDO ENVIO DE WEBHOOK ---")
    print(f"URL: {url[:60]}...")
    print(f"Payload: {payload}")
    
    async with httpx.AsyncClient() as client:
        try:
            # Simulando o que o app Android faria
            response = await client.post(url, json=payload)
            
            print(f"Status Code: {response.status_code}")
            
            if response.status_code in [200, 201]:
                print("✅ SUCESSO! O banco de dados aceitou o SMS.")
                print("Isso confirma que a tabela existe e as chaves estão certas.")
            elif response.status_code == 404:
                print("❌ ERRO 404: Tabela 'sms_logs' não encontrada. Você rodou o SQL no Supabase?")
            elif response.status_code == 403 or response.status_code == 401:
                print("❌ ERRO 401/403: Problema de permissão ou chave inválida.")
            else:
                print(f"❌ ERRO DESCONHECIDO: {response.text}")
                
        except Exception as e:
            print(f"❌ Erro na requisição: {e}")

if __name__ == "__main__":
    asyncio.run(test_webhook())
