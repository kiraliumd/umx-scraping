import asyncio
import logging
import os
import time
import re
import random
import httpx
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

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")


async def _get_latam_code_from_supabase(start_time):
    """
    Polls Supabase 'sms_logs' table for the LATAM 2FA code.
    This replaces Telegram polling for better reliability.
    """
    if not supabase:
        logger.error("Supabase client not initialized. Cannot poll SMS logs.")
        return None

    timeout = 120 # 2 minutes
    poll_start = time.time()
    # Convert start_time (unix) to ISO for Supabase comparison
    start_iso = time.strftime('%Y-%m-%dT%H:%M:%S+00:00', time.gmtime(start_time - 30))
    
    logger.info(f"Polling Supabase 'sms_logs' for 2FA code since {start_iso}...")

    while time.time() - poll_start < timeout:
        try:
            # Query sms_logs for messages since start_time containing 'LATAM'
            response = supabase.table("sms_logs") \
                .select("*") \
                .filter("created_at", "gte", start_iso) \
                .order("created_at", desc=True) \
                .limit(1) \
                .execute()
            
            if response.data:
                msg = response.data[0]
                text = msg.get("text", "")
                created_at = msg.get("created_at")
                
                logger.info(f"Checking Supabase SMS: {text[:50]}... (Received at: {created_at})")
                
                # Regex for 6 digits
                match = re.search(r"(\d{6})", text)
                if match:
                    code = match.group(1)
                    if "LATAM" in text.upper() or "CÓDIGO" in text.upper():
                        logger.info(f"✅ SUCCESS: Code found in Supabase: {code}")
                        return code
            
            await asyncio.sleep(3) # Check database every 3 seconds
        except Exception as e:
            logger.error(f"Error polling Supabase 'sms_logs': {e}")
            await asyncio.sleep(5)
    
    logger.warning("Timeout reached without finding 2FA code in Supabase.")
    return None


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

# Removed update_account_db functionally as requested

async def update_account_db_multi(username, status, livelo_val=None, latam_val=None):
    # Supabase updates disabled as requested.
    pass

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

async def _send_livelo_tokens(context, username):
    """
    Collects access and refresh tokens from cookies and sends them to Skyvio API.
    """
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
        
        if access_token and refresh_token:
            logger.info(f"Fresh tokens found for {username}! Sending to Skyvio...")
            api_url_tokens_umx_receive = 'https://adm.skyvio.com.br/api/livelo/tokens/receive/'
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url=api_url_tokens_umx_receive,
                    json={
                        "username": username,
                        "access_token": access_token,
                        "refresh_token": refresh_token
                    },
                    timeout=30.0
                )
                if response.status_code == 200:
                    logger.info(f"✅ Tokens Livelo enviados com sucesso para {username}!")
                    return True
                else:
                    logger.error(f'❌ Erro ao enviar tokens Livelo: {response.status_code}')
                    logger.error(f'Resposta erro: {response.text}')
        else:
            logger.info(f"No access/refresh tokens found in session for {username} yet.")
    except Exception as e:
        logger.error(f'Erro na coleta/envio de tokens Livelo para {username}: {e}')
    return False

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

    # Try sending tokens if they already exist (pre-existing session)
    await _send_livelo_tokens(context, username)
         
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
                # No longer extracting points, checking if tokens can be sent immediately
                token_sent = await _send_livelo_tokens(context, username)
                if token_sent:
                    logger.info("✅ SUCESSO RÁPIDO (Tokens enviados, já logado)")
                    return 0, None

            if attempt == 1 and "acesso.livelo.com.br" not in page.url:
                logger.info("Atualizando página para garantir...")
                try: 
                    await page.reload(wait_until="domcontentloaded")
                    await asyncio.sleep(5)
                except: pass
                if await _check_waf_block(page): raise Exception("BLOQUEIO WAF PÓS-RELOAD")
                
                token_sent = await _send_livelo_tokens(context, username)
                if token_sent:
                    logger.info("✅ SUCESSO (Tokens enviados pós-Reload)")
                    return 0, None

            logger.info("Sessão não encontrada ou tokens não enviados. Iniciando Login...")
            await perform_login(page, username, password)
            
            # Send tokens AGAIN after successful login to ensure they are fresh
            token_sent = await _send_livelo_tokens(context, username)
            
            if token_sent:
                logger.info("✅ SUCESSO (Tokens enviados pós-Login)")
                return 0, None
                
            raise Exception("Tokens não encontrados após login.")

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

async def perform_latam_login(page, username, password):
    """
    Handles LATAM Login with 2-step process and 2FA support.
    """
    try:
        # Step 1: Username
        logger.info("Step 1: Filling Username (Humanized)...")
        await page.wait_for_selector("#form-input--alias", state="visible", timeout=20000)
        await asyncio.sleep(random.uniform(1.2, 2.5)) # Pause before typing
        await page.type("#form-input--alias", username, delay=random.randint(70, 160))
        
        await asyncio.sleep(random.uniform(0.5, 1.2)) # Pause before button
        await page.click("#primary-button")
        
        # Step 2: Password
        logger.info("Step 2: Filling Password (Humanized)...")
        await page.wait_for_selector("#form-input--password", state="visible", timeout=20000)
        await asyncio.sleep(random.uniform(1.0, 2.1)) # Pause before typing
        await page.type("#form-input--password", password, delay=random.randint(60, 150))
        
        await asyncio.sleep(random.uniform(0.6, 1.3)) # Pause before button
        await page.click("#primary-button")
        
        logger.info("Login submitted. Checking for 2FA...")
        
        # Step 3: Check for 2FA Selection or Code Input
        try:
            # Check if we are on the 2FA selection screen
            await asyncio.sleep(random.uniform(4.0, 6.0))
            
            # Try to detect which 2FA screen we are on
            logger.info("Waiting for 2FA selection or code input screen...")
            try:
                # Wait for either selector
                await page.wait_for_selector("#radio-SMS, #form-input--code-0", timeout=20000)
                
                if await page.locator("#radio-SMS").is_visible():
                    logger.info("2FA selection screen detected. Choosing SMS...")
                    await asyncio.sleep(random.uniform(0.8, 1.8))
                    await page.click("#radio-SMS")
                    await asyncio.sleep(random.uniform(0.5, 1.1))
                    await page.click("#form-button--primaryAction")
                    await asyncio.sleep(3)
                    # Now wait for the code input
                    await page.wait_for_selector("#form-input--code-0", timeout=15000)

                if await page.locator("#form-input--code-0").is_visible(timeout=5000):
                    logger.info("2FA Code Input screen detected. Polling Supabase...")
                    start_time = time.time()
                    
                    # --- WEBHOOK INTERCEPTION ---
                    code = await _get_latam_code_from_supabase(start_time)
                    if not code:
                        raise Exception("Failed to retrieve 2FA code from Supabase.")
                    
                    logger.info(f"Filling 2FA code (Humanized)...")
                    for i, digit in enumerate(code[:6]):
                        await asyncio.sleep(random.uniform(0.2, 0.5))
                        await page.fill(f"#form-input--code-{i}", digit)
                    
                    await asyncio.sleep(random.uniform(1.0, 2.0))
                    await page.click("#form-button--primaryAction")
                    await asyncio.sleep(5)

            except Exception as e:
                if "timeout" in str(e).lower():
                    logger.info("No 2FA screens detected. Checking if login was successful...")
                else:
                    logger.warning(f"Error during 2FA flow: {e}")
                    raise e
            
            # --- POST-LOGIN VERIFICATION ---
            logger.info("Verifying if session is active...")
            # Wait for profile name or logout button to indicate success
            try:
                # Common selectors for logged in state
                await page.wait_for_selector("#header__profile__lnk-profile, [data-testid='header-username']", timeout=15000)
                logger.info("Login confirmed! Session is active.")
            except:
                logger.warning("Could not definitively confirm login via profile selector. Will check miles page directly.")

        except Exception as e:
            if "Timeout" in str(e) or "visible" in str(e):
                logger.info("2FA flow not triggered, checking if login succeeded.")
            else:
                logger.warning(f"Error during 2FA flow: {e}")
                raise e

    except Exception as e:
        logger.error(f"LATAM Login Interaction Failed: {e}")
        await save_screenshot(page, f"latam_login_failed_{username}")
        raise e

async def extract_latam(context, username, password):
    """
    Scrapes LATAM Pass Miles with 2FA support.
    """
    logger.info(">>> Starting LATAM Extraction...")
    page = await context.new_page()
    try:
        # --- Step 1: Navigate to Home and Check Login ---
        logger.info("Navigating to LATAM Home to check session...")
        await page.goto("https://www.latamairlines.com/br/pt", timeout=90000)
        await asyncio.sleep(5)
        
        login_btn = page.locator("#header__profile__lnk-sign-in")
        fazer_login_text = page.get_by_text("Fazer login").first
        
        if await login_btn.is_visible(timeout=5000) or await fazer_login_text.is_visible(timeout=2000):
            logger.info("Login button found. Checking for cookie banner first...")
            # --- COOKIE BANNER CHECK ---
            try:
                cookie_btn = page.locator("#cookies-politics-button")
                if await cookie_btn.is_visible(timeout=5000):
                    logger.info("Cookie banner detected. Accepting all cookies...")
                    await cookie_btn.click()
                    await asyncio.sleep(2) # Wait for banner to close
            except:
                pass

            logger.info("Starting Login flow...")
            if await login_btn.is_visible(timeout=1000):
                await login_btn.click()
            else:
                await fazer_login_text.click()

            await perform_latam_login(page, username, password)
        else:
            logger.info("Login button not found. Assuming already logged in.")

        # --- Step 2: Extraction ---
        logger.info("Navigating directly to miles page for extraction...")
        await page.goto("https://www.latamairlines.com/br/pt/sua-conta/miles/", timeout=90000)
        
        logger.info("Waiting for miles page to stabilize...")
        await asyncio.sleep(random.uniform(5.0, 8.0)) # Extra wait for dashboard
        
        try:
             await page.wait_for_load_state("networkidle", timeout=30000)
        except:
             logger.warning("Networkidle timeout, checking if elements are interactive...")

        # Robust extraction - Multiple selector attempts
        selectors = [
            "#lbl-miles-amount strong",
            "#lbl-miles-amount",
            ".miles-balance__amount", # Possible new/alt selector
            "span:has-text('pontos') + strong" # Generic fallback
        ]
        
        miles_element = None
        for sel in selectors:
            try:
                elem = page.locator(sel).first
                if await elem.is_visible(timeout=5000):
                    miles_element = elem
                    logger.info(f"Found balance via selector: {sel}")
                    break
            except: continue

        if miles_element:
            text = await miles_element.text_content()
            logger.info(f"Raw extracted text: {text}")
            clean = re.sub(r'\D', '', text)
            if clean:
                balance = int(clean)
                logger.info(f"LATAM SUCCESS: {balance}")
                return balance, None
        
        # Final Fallback regex on whole content
        logger.info("Attempting Final Regex Fallback...")
        text_content = await page.content()
        # Look for patterns like "10.000 pontos" or "Saldo de milhas 10.000"
        patterns = [
            r"Saldo de milhas.*?(\d+[\.\d]*)",
            r"(\d+[\.\d]*)\s*pontos",
            r"(\d+[\.\d]*)\s*milhas"
        ]
        
        for pat in patterns:
            match = re.search(pat, text_content, re.IGNORECASE | re.DOTALL)
            if match:
                clean = re.sub(r'\D', '', match.group(1))
                if clean:
                    balance = int(clean)
                    logger.info(f"LATAM SUCCESS (Pattern '{pat}'): {balance}")
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
        # latam_result = await extract_latam(context, username, decrypted_latam_pass)
        # latam_balance = latam_result[0] if isinstance(latam_result, tuple) else latam_result
        # latam_error_screenshot = latam_result[1] if isinstance(latam_result, tuple) else None
        
        logger.info("LATAM Extraction is currently deactivated. Skipping...")
        latam_balance = None
        latam_error_screenshot = None

        if livelo_balance is not None or latam_balance is not None: 
             # DB Update skipped as requested.
             
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
