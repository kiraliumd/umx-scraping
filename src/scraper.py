import asyncio
import logging
import os
import time
import re
from playwright.async_api import async_playwright
from src.adspower import AdsPowerController
from supabase import create_client, Client
from dotenv import load_dotenv
from src.crypto_utils import decrypt_password

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Persistence Setup
load_dotenv()
url: str = os.environ.get("SUPABASE_URL", "")
key: str = os.environ.get("SUPABASE_KEY", "")
supabase: Client = create_client(url, key) if url and key else None


async def save_screenshot(page, name_prefix):
    try:
        os.makedirs("prints", exist_ok=True)
        timestamp = int(time.time())
        filename = f"prints/{name_prefix}_{timestamp}.png"
        await page.screenshot(path=filename)
        logger.info(f"Screenshot saved to {filename}")
        return filename
    except Exception as e:
        logger.error(f"Failed to save screenshot: {e}")
        return None

async def update_account_db(username, status, balance=None, logs=True):
    pass # Mantido conforme seu pedido anterior para simplificar o log aqui, ou restaure se necessário

async def update_account_db_multi(username, status, livelo_val=None, latam_val=None):
    if not supabase: return
    try:
        # 1. Update 'accounts' table
        data = {"status": status, "updated_at": "now()"}
        if livelo_val is not None:
            data["livelo_balance"] = livelo_val 
        if latam_val is not None:
            data["latam_balance"] = latam_val
            
        supabase.table("accounts").update(data).eq("username", username).execute()
        
        # 2. Log Balance
        acc_resp = supabase.table("accounts").select("id").eq("username", username).execute()
        
        if not acc_resp.data: return 

        account_id = acc_resp.data[0]['id']
        
        if livelo_val is not None:
             supabase.table("balance_logs").insert({
                 "account_id": account_id,
                 "new_balance": livelo_val,
                 "program": "livelo",
                 "checked_at": "now()"
             }).execute()

        if latam_val is not None:
             supabase.table("balance_logs").insert({
                 "account_id": account_id,
                 "new_balance": latam_val,
                 "program": "latam",
                 "checked_at": "now()"
             }).execute()

    except Exception as e:
        logger.error(f"DB Update Error: {e}")

async def _check_waf_block(page):
    """
    Verifica se a página atual é um bloqueio da Akamai/EdgeSuite.
    Usa estratégia de Whitelist (Títulos Válidos) vs Blacklist (Termos de Erro).
    """
    try:
        title = await page.title()
        content = await page.content()
        title_lower = title.lower()
        content_lower = content.lower()
        
        # 1. Whitelist (Prioridade Máxima): Se for um título válido, IGNORA qualquer outra coisa.
        whitelist_titles = [
            "livelo", 
            "programa de pontos", 
            "troque seus pontos",
            "clube livelo"
        ]
        
        if any(valid in title_lower for valid in whitelist_titles):
            return False

        # 2. Blacklist: Se não caiu na whitelist, procura por erros explícitos.
        block_terms = [
            "access denied", 
            "you don't have permission", 
            "edgesuite.net", 
            "reference #", 
            "akamai error",
            "403 forbidden"
        ]
        
        if any(term in content_lower for term in block_terms) or "access denied" in title_lower:
            logger.warning(f"🚫 BLOQUEIO WAF DETECTADO: {title}")
            return True
            
    except: pass
    return False

async def _extract_points(page):
    """
    CORREÇÃO CRÍTICA: Extração Estrita.
    Só retorna valor se encontrar a classe exata do saldo logado.
    """
    balance_int = None
    try:
        loc = page.locator(".l-header__user-profile-balance").first
        if await loc.is_visible(timeout=3000):
            text = await loc.text_content()
            if text:
                clean = re.sub(r'\D', '', text)
                if clean: balance_int = int(clean)
    except: pass
    return balance_int

async def perform_login(page, username, password):
    """
    Handles Livelo Login using robust 'fill' and checks for success.
    """
    try:
        logger.info("Starting Login process...")
        
        # 1. Garantir que estamos no formulário
        if not await page.locator("#username").is_visible(timeout=3000):
            logger.info("Botão 'Entrar' necessário...")
            if await page.locator("#l-header__button_login").is_visible():
                await page.click("#l-header__button_login")
            elif await page.get_by_text("Entrar").first.is_visible():
                await page.get_by_text("Entrar").first.click()
            
            try: await page.wait_for_selector("#username", state="visible", timeout=10000)
            except: pass

        # 2. Preenchimento
        logger.info("Filling credentials...")
        
        # CPF Sanitization Double-Check (Zero Padding)
        if username.isdigit() and len(username) < 11:
            username = username.zfill(11)
            
        await page.fill("#username", username)
        await asyncio.sleep(0.5)
        await page.fill("#password", password)
        await asyncio.sleep(0.5)
        await page.press("#password", "Enter")
        logger.info("Credentials submitted. Waiting...")
        
        # 3. Wait for redirect/load
        await asyncio.sleep(10)
        
        # 4. VALIDAÇÃO PÓS-LOGIN
        if await _check_waf_block(page):
            raise Exception("LOGIN BLOCKED: WAF Access Denied detectado.")

        if await page.locator("#username").is_visible(timeout=2000) or await page.get_by_text("Entrar").first.is_visible(timeout=2000):
            raise Exception("LOGIN FALHOU: Botão entrar ainda visível.")

    except Exception as e:
        logger.error(f"Login Interaction Failed: {e}")
        if "BLOCKED" in str(e): raise e
        await save_screenshot(page, "login_failed")
        raise e

async def _ensure_clean_tab(context, page=None):
    if page:
        try: await page.close()
        except: pass
    try: await context.clear_cookies()
    except: pass
    new_page = await context.new_page()
    await new_page.bring_to_front()
    return new_page

async def extract_livelo(context, username, password):
    logger.info(">>> Starting LIVELO Extraction (Smart Mode)...")
    page = None
    for p in context.pages:
        try:
            if "livelo.com.br" in p.url:
                page = p
                await page.bring_to_front()
                try: await p.evaluate("window.stop()")
                except: pass
                break
        except: pass
        
    max_retries = 2
    attempt = 0
    final_error = None
    final_screenshot = None

    try:
        access_token = None
        refresh_token = None
        cookies = await context.cookies()
        for cookie in cookies:
            if cookie['name'] == 'access_token':
                access_token = cookie['value']
            elif cookie['name'] == 'refresh_token':
                refresh_token = cookie['value']
            if access_token and refresh_token:
                break
        api_url_tokens_umx_receive = 'https://adm.skyvio.com.br/api/livelo/tokens/receive/'
        headers = { 'Content-Type': 'application/json' }
        response = await requests.post(
            url = api_url_tokens_umx_receive,
            headers = headers
        )
        if response.status_code == '200':
            logger.info(f"Tokens Livelo obtidos com sucesso!")
        else:
            logger.error(f'Erro ao obter tokens Livelo: {reponse.status_code}')
            logger.error(f'Erro tokens Livelo: {reponse.text}')
    except Exception as e::
        logger.error(f'Tentativa coleta tokens livelo {e}')
         
    while attempt < max_retries:
        attempt += 1
        logger.info(f"🔄 Tentativa {attempt}/{max_retries}")
        try:
            if not page or attempt > 1:
                if attempt > 1: logger.info("♻️ Retry: Abrindo aba limpa...")
                page = await _ensure_clean_tab(context, page)
                await page.goto("https://www.livelo.com.br/", timeout=60000)
            
            if await _check_waf_block(page):
                raise Exception("BLOQUEIO WAF INICIAL")

            if attempt == 1:
                points = await _extract_points(page)
                if points is not None:
                    logger.info(f"✅ SUCESSO RÁPIDO (Já logado): {points}")
                    return points, None

            if attempt == 1 and "acesso.livelo.com.br" not in page.url:
                logger.info("Atualizando página para garantir...")
                try: 
                    await page.reload(wait_until="domcontentloaded")
                    await asyncio.sleep(5)
                except: pass
                if await _check_waf_block(page): raise Exception("BLOQUEIO WAF PÓS-RELOAD")
                points = await _extract_points(page)
                if points is not None:
                    logger.info(f"✅ SUCESSO (Pós-Reload): {points}")
                    return points, None

            logger.info("Pontos não encontrados. Iniciando Login...")
            await perform_login(page, username, password)
            points = await _extract_points(page)
            if points is not None:
                logger.info(f"✅ SUCESSO (Pós-Login): {points}")
                return points, None
            raise Exception("Pontos não encontrados (Login pode ter falhado silenciosamente).")

        except Exception as e:
            err_msg = str(e)
            logger.error(f"Erro na tentativa {attempt}: {err_msg}")
            is_waf = "BLOQUEIO" in err_msg or "Access Denied" in err_msg
            if attempt < max_retries:
                if is_waf:
                    logger.warning("⚠️ Bloqueio WAF. Aguardando 5s...")
                    await asyncio.sleep(5)
                continue
            else:
                final_error = err_msg
                try: final_screenshot = await save_screenshot(page, f"erro_fatal_{username}")
                except: pass
                break
    return {"livelo": None, "error": final_error, "screenshot": final_screenshot}

async def extract_latam(context, username, password):
    """
    Scrapes LATAM Pass Miles:
    1. Fast Track: Check if already logged in via direct URL.
    2. Login: 2-step process (Username -> Password).
    3. Extract: Numeric balance from account page.
    """
    logger.info(">>> Starting LATAM Extraction...")
    page = await context.new_page()
    try:
        # --- Step 1: Navigate to Home and Check Login ---
        logger.info("Navigating to LATAM Home to check session...")
        await page.goto("https://www.latamairlines.com/br/pt", timeout=60000)
        await asyncio.sleep(5) # Give it a moment to load profile/login button
        
        login_btn = page.locator("#header__profile__lnk-sign-in")
        fazer_login_text = page.get_by_text("Fazer login").first
        
        is_logged_in = False
        if not await login_btn.is_visible(timeout=10000) and not await fazer_login_text.is_visible(timeout=2000):
            logger.info("Login button not found. Assuming already logged in.")
            is_logged_in = True
        else:
            logger.info("Login button found. Starting Login flow...")
            if await login_btn.is_visible(timeout=1000):
                await login_btn.click()
            else:
                await fazer_login_text.click()

            # Step 2.1: Username
            logger.info("Step 1: Filling Username...")
            await page.wait_for_selector("#form-input--alias", state="visible", timeout=20000)
            await page.fill("#form-input--alias", username)
            await page.click("#primary-button")
            
            # Step 2.2: Password
            logger.info("Step 2: Filling Password...")
            await page.wait_for_selector("#form-input--password", state="visible", timeout=20000)
            await page.fill("#form-input--password", password)
            await page.click("#primary-button")
            
            logger.info("Login submitted. Waiting for redirect...")
            await asyncio.sleep(10)
            is_logged_in = True # Assuming success for now, will verify on miles page

        # --- Step 2: Extraction ---
        logger.info("Navigating directly to miles page for extraction...")
        await page.goto("https://www.latamairlines.com/br/pt/sua-conta/miles/", timeout=60000)
        
        # Robust wait to ensure the SPA has finished loading data
        logger.info("Waiting for miles page to stabilize...")
        try:
             await page.wait_for_load_state("networkidle", timeout=20000)
        except:
             logger.warning("Networkidle timeout, proceeding with extraction...")

        # Increased timeouts significantly for slow renders (as per user feedback)
        miles_element = page.locator("#lbl-miles-amount strong").first
        if not await miles_element.is_visible(timeout=15000):
            logger.info("Selector #lbl-miles-amount strong not immediately visible, checking parent...")
            miles_element = page.locator("#lbl-miles-amount").first

        if await miles_element.is_visible(timeout=20000):
            text = await miles_element.text_content()
            clean = re.sub(r'\D', '', text)
            if clean:
                balance = int(clean)
                logger.info(f"LATAM SUCCESS: {balance}")
                return balance, None
        
        text_content = await page.content()
        match = re.search(r"Saldo de milhas.*?(\d+[\.\d]*)", text_content, re.IGNORECASE | re.DOTALL)
        if match:
            clean = re.sub(r'\D', '', match.group(1))
            balance = int(clean)
            logger.info(f"LATAM SUCCESS (Regex Match): {balance}")
            return balance, None

        logger.error("Failed to extract LATAM balance.")
        screenshot_path = await save_screenshot(page, f"error_latam_{username}")
        return None, screenshot_path

    except Exception as e:
        logger.error(f"LATAM Extraction Error: {e}")
        screenshot_path = await save_screenshot(page, f"error_latam_fatal_{username}")
        return None, screenshot_path
    finally:
        try:
            await page.close()
            logger.info("LATAM tab closed.")
        except: pass

async def get_balance(username, password, adspower_user_id=None, latam_password=None):
    if not adspower_user_id:
        return {"status": "error", "message": "Missing adspower_user_id"}
    ws_endpoint = await AdsPowerController.start_profile(adspower_user_id)
    if not ws_endpoint:
        return {"status": "error", "message": "Failed to start AdsPower profile"}
    playwright = await async_playwright().start()
    try:
        browser = await playwright.chromium.connect_over_cdp(ws_endpoint)
        
        # 1. Force Viewport and Window Optimization
        # Use an explicit 1080p viewport to ensure rendering matches targets
        context = browser.contexts[0] if browser.contexts else await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            device_scale_factor=1
        )

        # 2. Deep Maximization via CDP
        try:
            # We open a temp page just to ensure we have a "web content" target for the CDP commands
            # This helps avoid "No web contents in the target" errors
            temp_page = await context.new_page()
            session = await temp_page.context.new_cdp_session(temp_page)
            
            # Get the window ID for the current target
            window_info = await session.send("Browser.getWindowForTarget")
            window_id = window_info.get("windowId")
            
            if window_id:
                logger.info(f"Forcing window {window_id} to maximized state via CDP...")
                await session.send("Browser.setWindowBounds", {
                    "windowId": window_id,
                    "bounds": {"windowState": "maximized"}
                })
            await temp_page.close()
        except Exception as cdp_err:
            logger.warning(f"CDP Maximization failed (non-critical): {cdp_err}")
        
        # Decrypt passwords before using them
        decrypted_pass = decrypt_password(password)
        decrypted_latam_pass = decrypt_password(latam_password) if latam_password else decrypted_pass

        # 1. LIVELO
        result = await extract_livelo(context, username, decrypted_pass)
        livelo_balance = result[0] if isinstance(result, tuple) else result.get("livelo") if isinstance(result, dict) else result
        error_screenshot = result[1] if isinstance(result, tuple) else result.get("screenshot") if isinstance(result, dict) else None

        # 2. LATAM (TEMPORARILY DEACTIVATED)
        # Use specific latam_password if provided, else fallback to the shared password
        # latam_result = await extract_latam(context, username, decrypted_latam_pass)
        # latam_balance = latam_result[0] if isinstance(latam_result, tuple) else latam_result
        # latam_error_screenshot = latam_result[1] if isinstance(latam_result, tuple) else None
        
        logger.info("LATAM Extraction is currently deactivated. Skipping...")
        latam_balance = None
        latam_error_screenshot = None

        if livelo_balance is not None or latam_balance is not None: 
             await update_account_db_multi(username, "active", livelo_val=livelo_balance, latam_val=latam_balance)
             
             # Consolidate screenshots: if one failed, report that screenshot even on success
             final_screenshot = error_screenshot or latam_error_screenshot
             return {
                 "status": "success", 
                 "livelo": livelo_balance, 
                 "latam": latam_balance, 
                 "error_screenshot": final_screenshot
             }
        else:
            final_screenshot = error_screenshot or latam_error_screenshot
            return {
                "status": "error", 
                "message": "Failed to extract balances", 
                "livelo": None, 
                "latam": None, 
                "error_screenshot": final_screenshot
            }
    except Exception as e:
        logger.error(f"Global Scraper Error: {e}")
        return {"status": "error", "message": str(e), "livelo": None}
    finally:
        if playwright: await playwright.stop()
