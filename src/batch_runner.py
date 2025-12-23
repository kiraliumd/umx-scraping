
import asyncio
import logging
import os
import sys

# Add project root to path to allow 'from src...' imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from supabase import create_client, Client
from dotenv import load_dotenv
from src.scraper import get_balance
from src.adspower import AdsPowerController
import src.clickup as clickup
from src.sheets_logger import SheetsLogger

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


async def process_account(account, stats, details_log, sheets_logger=None):
    username = account['username']
    adspower_id = account.get('adspower_user_id')
    
    if not adspower_id:
        logger.warning(f"Skipping {username}: No AdsPower ID.")
        details_log.append(f"❌ {username}: Sem AdsPower ID")
        stats['failed'] += 1
        if sheets_logger:
            try: sheets_logger.log_execution(username, 0, "FALHA", "Sem AdsPower ID")
            except: pass
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
        # LATAM is deactivated, so we just show N/A or skip
        logger.info(f"RESULT {username}: Livelo={livelo_val} (LATAM Deactivated) - Status: {status_str}")

        if result['status'] == 'success':
            new_livelo = result.get('livelo')
            # latam ignored
            
            liv_ok = (new_livelo is not None)
            
            if liv_ok:
                stats['success'] += 1
                if sheets_logger:
                     try: sheets_logger.log_execution(profile_name, new_livelo, "SUCESSO", "Extração OK")
                     except: pass
            else:
                stats['failed'] += 1
                details_log.append(f"❌ {username}: Falha ao extrair Livelo")
                if sheets_logger:
                     try: sheets_logger.log_execution(profile_name, 0, "FALHA", "Retorno ok mas saldo vazio")
                     except: pass

            # --- DB Comparison & Alerts ---
            changes = {}
            if liv_ok:
                old_val = account.get('livelo_balance') or 0
                if new_livelo != old_val:
                    changes['livelo'] = {'old': old_val, 'new': new_livelo}

            logger.info(f"RESULT {username}: Livelo={new_livelo}")

            if changes:
                logger.info(f"Divergence detected: {changes}")
                await clickup.create_task(account, changes)
            
            return True
        else:
            msg = result.get('message', 'Erro desconhecido')
            screenshot = result.get('error_screenshot')
            
            logger.error(f"FAILED {username}: {msg}")
            
            fail_msg = f"❌ {username}: {msg}"
            if screenshot:
                fname = os.path.basename(screenshot)
                # User requested format: "❌ [ID]: Falha na Extração - Print: nome_do_arquivo.png"
                # Replacing generic msg if it's the standard generic error, or appending if specific
                if "Failed to extract Livelo" in msg:
                    fail_msg = f"❌ {username}: Falha na Extração - Print: {fname}"
                else:
                    fail_msg = f"❌ {username}: {msg} - Print: {fname}"
                
            details_log.append(fail_msg)
            stats['failed'] += 1
            
            if sheets_logger:
                try: sheets_logger.log_execution(profile_name, 0, "FALHA", msg)
                except: pass
                
            return False
            
    except Exception as e:
        logger.error(f"CRITICAL ERROR for {username}: {e}")
        details_log.append(f"❌ {username}: Exception - {str(e)}")
        stats['failed'] += 1
        
        if sheets_logger:
            try: sheets_logger.log_execution(profile_name, 0, "CRITICAL", str(e))
            except: pass
            
        return False
        
    finally:
        logger.info(f"Closing AdsPower profile: {adspower_id}")
        await AdsPowerController.stop_profile(adspower_id)
        logger.info("Waiting 5s for cleanup...")
        await asyncio.sleep(5)

async def run_batch():
    logger.info(">>> Starting Batch Processing Routine <<<")
    
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
    logger.info(f"Found {total} active accounts.")
    
    # Init Sheets Logger
    sheets_logger = SheetsLogger()
    
    # Init Stats
    stats = {"success": 0, "failed": 0}
    details_log = []
    
    import time
    start_time = time.time()
    
    # 2. Loop
    for i, acc in enumerate(accounts):
        logger.info(f"--- Task {i+1}/{total} ---")
        await process_account(acc, stats, details_log, sheets_logger)
            
    end_time = time.time()
    duration = end_time - start_time
    duration_str = f"{int(duration // 60)}m {int(duration % 60)}s"

    # 3. Report Generation
    from datetime import datetime
    date_str = datetime.now().strftime("%d/%m/%Y")
    
    report_lines = []
    report_lines.append("🤖 **Relatório Diário de Execução**")
    report_lines.append(f"📅 {date_str}")
    report_lines.append("")
    report_lines.append("📊 **Resumo:**")
    report_lines.append(f"⏱️ Tempo Total: {duration_str}")
    report_lines.append(f"👥 Contas Analisadas: {total}")
    report_lines.append(f"✅ Sucesso Total: {stats['success']}")
    report_lines.append(f"❌ Falhas: {stats['failed']}")
    
    report_lines.append("")
    report_lines.append("📝 **Detalhamento de Problemas:**")
    if details_log:
        for line in details_log:
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
