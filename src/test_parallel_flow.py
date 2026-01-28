
import asyncio
import logging
import time
from src.scraper import get_balance
from src.adspower import AdsPowerController

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("TestParallelFlow")

import os
from supabase import create_client, Client
from dotenv import load_dotenv
import random

# Load environment variables
load_dotenv()
url: str = os.environ.get("SUPABASE_URL", "")
key: str = os.environ.get("SUPABASE_KEY", "")
supabase: Client = create_client(url, key) if url and key else None

async def test_full_flow_parallel():
    if not supabase:
        logger.error("Supabase credentials missing. Cannot fetch random accounts.")
        return

    # 1. Busca contas ativas no banco
    logger.info("Buscando contas ativas no Supabase...")
    try:
        response = supabase.table("accounts")\
            .select("*")\
            .eq("status", "active")\
            .execute()
        
        all_accounts = response.data
        if not all_accounts or len(all_accounts) < 2:
            logger.error(f"Contas insuficientes encontradas ({len(all_accounts)}).")
            return
            
        # Seleciona 2 contas aleatórias
        accounts = random.sample(all_accounts, 2)
    except Exception as e:
        logger.error(f"Erro ao buscar contas: {e}")
        return
    
    logger.info(f">>> Iniciando FLUXO COMPLETO paralelo para {len(accounts)} contas aleatórias.")
    for acc in accounts:
        logger.info(f" - Conta selecionada: {acc['username']} ({acc['adspower_user_id']})")
    
    start_time = time.time()
    
    async def run_with_cleanup(acc):
        username = acc['username']
        adspower_id = acc['adspower_user_id']
        try:
            logger.info(f"🚀 Iniciando raspagem para: {username} ({adspower_id})")
            
            # Chama a função REAL do scraper (abre adsPower, faz login e EXTRAI TOKENS)
            result = await get_balance(
                username, 
                acc['password'], 
                adspower_user_id=adspower_id,
                latam_password=acc.get('latam_password')
            )
            
            # No novo fluxo, sucesso significa que os tokens foram extraídos e enviados
            if result.get('status') == 'success':
                logger.info(f"✅ SUCESSO {username}: Tokens extraídos e enviados para Skyvio.")
            else:
                logger.error(f"❌ FALHA {username}: {result.get('message')}")
            return result
        finally:
            logger.info(f"🛑 Fechando perfil AdsPower: {adspower_id}")
            await AdsPowerController.stop_profile(adspower_id)

    # Executa as duas contas ao mesmo tempo
    tasks = [run_with_cleanup(acc) for acc in accounts]
    results = await asyncio.gather(*tasks)
    
    end_time = time.time()
    logger.info(f">>> Teste finalizado em {end_time - start_time:.2f}s")
    logger.info(f"Resultados consolidados: {results}")

if __name__ == "__main__":
    asyncio.run(test_full_flow_parallel())
