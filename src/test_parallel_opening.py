
import asyncio
import logging
import time
from src.adspower import AdsPowerController

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("TestParallel")

async def test_opening_parallel():
    # IDs de perfis reais encontrados no seu banco
    profile_ids = ["k17ttb23", "k17ttb2l"]
    
    logger.info(f">>> Iniciando teste de abertura paralela para: {profile_ids}")
    
    start_time = time.time()
    
    async def start_and_wait(user_id):
        logger.info(f"Tentando abrir perfil: {user_id}")
        ws = await AdsPowerController.start_profile(user_id)
        if ws:
            logger.info(f"✅ Perfil {user_id} aberto com sucesso!")
            # Mantém aberto por 15 segundos para você conseguir ver as duas janelas
            await asyncio.sleep(15)
            logger.info(f"Fechando perfil: {user_id}")
            await AdsPowerController.stop_profile(user_id)
        else:
            logger.error(f"❌ Falha ao abrir perfil: {user_id}")

    # Despacha as duas aberturas simultaneamente
    tasks = [start_and_wait(pid) for pid in profile_ids]
    await asyncio.gather(*tasks)
    
    end_time = time.time()
    logger.info(f">>> Teste finalizado em {end_time - start_time:.2f}s")

if __name__ == "__main__":
    asyncio.run(test_opening_parallel())
