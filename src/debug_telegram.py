import httpx
import asyncio
import os
import re
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

async def debug_telegram():
    print(f"--- INICIANDO DEBUG TELEGRAM ---")
    if not TOKEN:
        print("❌ Erro: TELEGRAM_BOT_TOKEN não encontrado no .env")
        return
    
    print(f"Token: {TOKEN[:5]}... (ok)")
    print(f"Target Chat ID: {CHAT_ID}")
    print("Aguardando mensagens... (Envie um SMS teste agora)")
    
    last_update_id = 0
    
    async with httpx.AsyncClient() as client:
        url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
        
        for i in range(30):
            try:
                # offset=last_update_id+1 garante que não leremos a mesma msg 2 vezes
                params = {"timeout": 1}
                if last_update_id:
                    params["offset"] = last_update_id + 1
                
                resp = await client.get(url, params=params)
                data = resp.json()
                
                if not data.get("ok"):
                    print(f"Erro na API: {data}")
                    continue
                
                result = data.get("result", [])
                
                if not result:
                    print(".", end="", flush=True)
                else:
                    print(f"\n📩 {len(result)} ATUALIZAÇÃO(ÕES) RECEBIDA(S)!")
                    for update in result:
                        print(f"DEBUG RAW JSON: {update}") # Mostrar o JSON bruto para vermos a estrutura
                        last_update_id = update["update_id"]
                        
                        # Tentar capturar conteúdo de qualquer tipo de mensagem
                        message = update.get("message") or update.get("channel_post") or update.get("business_message")
                        if not message:
                            print("⚠️ Mensagem sem conteúdo reconhecido (pode ser comando ou outro tipo).")
                            continue
                            
                        text = message.get("text", "")
                        chat_info = message.get("chat", {})
                        cid = str(chat_info.get("id"))
                        
                        print(f"--- DETALHES ---")
                        print(f"Remetente: {message.get('from', {}).get('first_name', 'Desconhecido')}")
                        print(f"Chat ID da msg: {cid} | Esperado no .env: {CHAT_ID}")
                        print(f"Texto: {text}")
                        
                        # Teste de Regex
                        code_match = re.search(r"(\d{6})", text)
                        if code_match:
                            print(f"✅ CÓDIGO 6 DÍGITOS ENCONTRADO: {code_match.group(1)}")
                        else:
                            print(f"❌ NENHUM CÓDIGO DE 6 DÍGITOS ENCONTRADO.")
                            
                        if str(cid).strip() != str(CHAT_ID).strip():
                            print("🚨 ALERTA: Esta mensagem veio de um Chat ID DIFERENTE do que está no seu .env!")
                            
            except Exception as e:
                print(f"\nErro no loop: {e}")
            
            await asyncio.sleep(1)
    
    print(f"\n--- FIM DO DEBUG ---")

if __name__ == "__main__":
    asyncio.run(debug_telegram())
