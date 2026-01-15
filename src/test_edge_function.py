import httpx
import asyncio
import json

async def test_edge_function():
    # Nova URL da Edge Function
    url = "https://upvivegiqubfdddnnuie.supabase.co/functions/v1/sms_receiver"
    
    payload = {
        "from_number": "EDGE_TEST_SENDER",
        "text": "123456 é o seu código LATAM (Teste via Edge Function)"
    }
    
    print(f"--- TESTANDO EDGE FUNCTION ---")
    print(f"URL: {url}")
    print(f"Payload: {payload}")
    
    async with httpx.AsyncClient() as client:
        try:
            # Testando se ela está aberta ao público (sem JWT)
            response = await client.post(url, json=payload, timeout=20)
            
            print(f"Status Code: {response.status_code}")
            print(f"Response Body: {response.text}")
            
            if response.status_code in [200, 201]:
                print("✅ SUCESSO! A Edge Function recebeu e salvou o SMS corretamente.")
            elif response.status_code == 401:
                print("❌ ERRO 401: JWT Verification ainda está ATIVO. Desative 'Enforce JWT Verification' no painel do Supabase!")
            else:
                print(f"❌ ERRO {response.status_code}: {response.text}")
                
        except Exception as e:
            print(f"❌ Erro na requisição: {e}")

if __name__ == "__main__":
    asyncio.run(test_edge_function())
