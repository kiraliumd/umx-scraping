
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
                if "Failed to extract Livelo" in msg or "Tokens não encontrados" in msg:
                    fail_msg = f"❌ {username}: Falha no Token - Print: {fname}"
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
    
    # Init Stats
    stats = {"success": 0, "failed": 0}
    details_log = []
    
    import time
    start_time = time.time()
    
    # 2. Main Loop (First Pass)
    failed_accounts = []
    for i, acc in enumerate(accounts):
        logger.info(f"--- Task {i+1}/{total} ---")
        success = await process_account(acc, stats, details_log)
        if not success:
            failed_accounts.append(acc)
            
    # 3. Repescagem (Second Pass for failures)
    if failed_accounts:
        retry_total = len(failed_accounts)
        logger.info(f"\n>>> INICIANDO REPESCAGEM: {retry_total} contas falharam na primeira tentativa. <<<")
        
        # We need to temporarily "undo" the fail count for these to recount correctly if they succeed
        # Actually, it's easier to just keep the original fails and only decrement if they succeed now
        
        for i, acc in enumerate(failed_accounts):
            username = acc['username']
            logger.info(f"--- Repescagem {i+1}/{retry_total}: {username} ---")
            
            # Create a localized log for this account to avoid duplicate error lines in the final report
            # unless it fails again.
            retry_details = []
            final_success = await process_account(acc, stats, retry_details)
            
            if final_success:
                logger.info(f"✅ SUCESSO na Repescagem para {username}!")
                # Decrement original fail count since it's now a success
                stats['failed'] -= 1 
                # stats['success'] is already incremented inside process_account
                
                # Remove the failure message from details_log (it will be at the end)
                # This is tricky because the message might vary. We'll add a note instead.
                details_log.append(f"🔄 {username}: Recuperado na Repescagem")
            else:
                logger.warning(f"❌ Falha persistente na Repescagem para {username}.")
                # process_account already incremented stats['failed'] again, 
                # but we only want to count it ONCE in the final total fails.
                # So we decrement the "extra" fail.
                stats['failed'] -= 1
                if retry_details:
                    details_log.append(f"❌ {username}: Falha persistente na Repescagem")

    end_time = time.time()
    duration = end_time - start_time
    duration_str = f"{int(duration // 60)}m {int(duration % 60)}s"

    # 4. Report Generation
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
    report_lines.append(f"❌ Falhas Finais: {stats['failed']}")
    if failed_accounts:
        report_lines.append(f"🔄 Total Repescadas: {len(failed_accounts)}")
    
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
