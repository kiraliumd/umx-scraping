
import asyncio
import logging
import os
import sys
import random

# Add project root to path to allow 'from src...' imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from supabase import create_client, Client
from dotenv import load_dotenv
from src.scraper import get_balance
from src.adspower import AdsPowerController
import src.clickup as clickup

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("BatchRunner")

# Init Supabase
load_dotenv()
url: str = os.environ.get("SUPABASE_URL", "")
key: str = os.environ.get("SUPABASE_KEY", "")
supabase: Client = create_client(url, key)


# Channel ID for Daily Reports (Chat)
CLICKUP_CHANNEL_ID = os.environ.get("CLICKUP_CHANNEL_ID", "")


async def process_account(account, stats, details_log):
    username = account['username']
    adspower_id = account.get('adspower_user_id')
    
    if not adspower_id:
        logger.warning(f"Skipping {username}: No AdsPower ID.")
        details_log.append(f"❌ {username}: Sem AdsPower ID")
        stats['failed'] += 1
        return False

    logger.info(f"========== Processing: {username} (ID: {adspower_id}) ==========")
    
    # Fetch Friendly Name for Sheets
    profile_name = username # Default
    try:
        profile_name = await AdsPowerController.get_profile_name(adspower_id)
    except: pass
    
    try:
        # Pass adspower_id and latam_password to get_balance logic
        result = await get_balance(
            username, 
            account['password'], 
            adspower_user_id=adspower_id,
            latam_password=account.get('latam_password')
        )
        
        # Log results
        status_str = "SUCCESS" if result['status'] == 'success' else "FAILED"
        livelo_val = result.get('livelo') if result.get('livelo') is not None else "N/A"
        latam_val = result.get('latam') if result.get('latam') is not None else "N/A"
        
        logger.info(f"RESULT {username}: Livelo={livelo_val}, LATAM={latam_val} - Status: {status_str}")

        if result['status'] == 'success':
            stats['success'] += 1
            return True
        else:
            msg = result.get('message', 'Erro desconhecido')
            screenshot = result.get('error_screenshot')
            
            logger.error(f"FAILED {username}: {msg}")
            
            fail_msg = f"❌ {username}: {msg}"
            if screenshot:
                fname = os.path.basename(screenshot)
                if "AUTH_FAILED" in fname:
                    fail_msg = f"🚫 {username}: Credenciais Inválidas 🔑"
                elif "RESET_REQUIRED" in fname:
                    fail_msg = f"⚠️ {username}: Precisa Redefinir Senha 🔄"
                elif "WAF_BLOCK" in fname:
                    fail_msg = f"🧱 {username}: Bloqueio de Rede (WAF) 🛑"
                else:
                    fail_msg = f"❌ {username}: {msg} - Print: {fname}"
                
            details_log.append(fail_msg)
            stats['failed'] += 1
            return False
            
    except Exception as e:
        logger.error(f"CRITICAL ERROR for {username}: {e}")
        details_log.append(f"❌ {username}: Exception - {str(e)}")
        stats['failed'] += 1
        
        return False
        
    finally:
        logger.info(f"Closing AdsPower profile: {adspower_id}")
        await AdsPowerController.stop_profile(adspower_id)
        logger.info("Waiting 5s for cleanup...")
        await asyncio.sleep(5)

async def run_batch(concurrency_limit=2):
    logger.info(">>> Starting Batch Processing Routine (Parallel) <<<")
    
    # 1. Fetch Active Accounts
    try:
        data = supabase.table("accounts")\
            .select("*")\
            .eq("status", "active")\
            .order("updated_at")\
            .execute()
        
        accounts = data.data
    except Exception as e:
        logger.error(f"Failed to fetch accounts: {e}")
        return

    total = len(accounts)
    logger.info(f"Found {total} active accounts. Concurrency limit: {concurrency_limit}")
    
    # Init Stats
    stats = {"success": 0, "failed": 0}
    details_log = []
    
    import time
    start_time = time.time()
    
    # 2. Parallel Processing with Semaphore
    semaphore = asyncio.Semaphore(concurrency_limit)
    waf_failed_accounts = []

    async def sem_process_account(acc, is_retry=False):
        async with semaphore:
            # Small staggered start to avoid API/CPU spikes
            if not is_retry:
                await asyncio.sleep(random.uniform(1, 3))
            
            success = await process_account(acc, stats, details_log)
            
            # Se falhou por WAF e não é uma tentativa de repescagem, adiciona na lista
            if not success and not is_retry:
                # Verificamos se o erro foi WAF através do log ou resultado
                # Como process_account adicionou no details_log, podemos checar
                if details_log and "Bloqueio de Rede (WAF)" in details_log[-1]:
                    waf_failed_accounts.append(acc)
            
            return success

    tasks = [sem_process_account(acc) for acc in accounts]
    
    # Run all tasks concurrently
    await asyncio.gather(*tasks)

    # 3. Repescagem Seletiva (Apenas WAF)
    if waf_failed_accounts:
        retry_total = len(waf_failed_accounts)
        logger.info(f"\n>>> INICIANDO REPESCAGEM: {retry_total} contas tiveram bloqueio WAF. <<<")
        
        # Resetamos as estatísticas de falha para estas contas antes da repescagem
        # (Elas serão re-contadas dentro do sem_process_account)
        stats['failed'] -= retry_total
        
        # Removemos as mensagens de erro de WAF originais para não duplicar no relatório
        # Filtramos o details_log para remover as linhas de WAF dessas contas
        waf_usernames = [a['username'] for a in waf_failed_accounts]
        details_log[:] = [line for line in details_log if not any(uname in line and "WAF" in line for uname in waf_usernames)]

        retry_tasks = [sem_process_account(acc, is_retry=True) for acc in waf_failed_accounts]
        await asyncio.gather(*retry_tasks)
        
        # Adiciona nota informativa para contas recuperadas
        # (Opcional, mas ajuda a entender o que aconteceu)
        logger.info(">>> Repescagem concluída. <<<")

    end_time = time.time()
    duration = end_time - start_time
    duration_str = f"{int(duration // 60)}m {int(duration % 60)}s"

    # 3. Report Generation
    from datetime import datetime
    date_str = datetime.now().strftime("%d/%m/%Y")
    
    report_lines = []
    report_lines.append("🤖 **Relatório Diário de Execução (Paralelo)**")
    report_lines.append(f"📅 {date_str}")
    report_lines.append("")
    report_lines.append("📊 **Resumo:**")
    report_lines.append(f"⏱️ Tempo Total: {duration_str}")
    report_lines.append(f"👥 Contas Analisadas: {total}")
    report_lines.append(f"✅ Sucesso Total: {stats['success']}")
    report_lines.append(f"❌ Falhas Finais: {stats['failed']}")
    
    report_lines.append("")
    report_lines.append("📝 **Detalhamento de Problemas:**")
    if details_log:
        # Sort details alphabetically by username for better readability since they finish at different times
        sorted_details = sorted(details_log)
        for line in sorted_details:
            report_lines.append(line)
    else:
        report_lines.append("Nenhum problema detectado.")
    
    report_text = "\n".join(report_lines)
    
    # Log to Console
    logger.info("=" * 40)
    logger.info(report_text)
    logger.info("=" * 40)
    
    # Send to ClickUp Chat
    if CLICKUP_CHANNEL_ID:
        logger.info(f"Sending report to ClickUp Channel {CLICKUP_CHANNEL_ID}...")
        await clickup.send_message(CLICKUP_CHANNEL_ID, report_text)
    else:
        logger.warning("CLICKUP_CHANNEL_ID not set. Report sent only to console.")

if __name__ == "__main__":
    if not url or not key:
        logger.error("Supabase credentials missing.")
        exit(1)
    asyncio.run(run_batch())
