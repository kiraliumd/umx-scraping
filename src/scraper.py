import asyncio
import logging
import os
import time
import re
from playwright.async_api import async_playwright
from src.adspower import AdsPowerController
from supabase import create_client, Client
from dotenv import load_dotenv

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
        # Isso previne falso positivo na Home Page que tem scripts da Akamai no código fonte.
        whitelist_titles = [
            "livelo", 
            "programa de pontos", 
            "troque seus pontos",
            "clube livelo"
        ]
        
        if any(valid in title_lower for valid in whitelist_titles):
            # É uma página válida da Livelo
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
        
        # Verifica se achou termos proibidos E o título sugere erro (ou não é whitelist)
        if any(term in content_lower for term in block_terms) or "access denied" in title_lower:
            logger.warning(f"🚫 BLOQUEIO WAF DETECTADO: {title}")
            return True
            
    except: pass
    return False

async def _extract_points(page):
    """
    CORREÇÃO CRÍTICA: Extração Estrita.
    Removemos a 'Strategy 2' (Regex) para evitar alucinações com banners.
    Só retorna valor se encontrar a classe exata do saldo logado.
    """
    balance_int = None
    
    # Strategy 1: Class Specific (High Confidence)
    try:
        # Este seletor só existe quando o usuário está logado
        loc = page.locator(".l-header__user-profile-balance").first
        if await loc.is_visible(timeout=3000):
            text = await loc.text_content()
            if text:
                clean = re.sub(r'\D', '', text)
                if clean: balance_int = int(clean)
    except: pass
    
    # Strategy 2 REMOVIDA: Causava falsos positivos em contas deslogadas.
        
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
            
            # Aguarda formulário
            try: await page.wait_for_selector("#username", state="visible", timeout=10000)
            except: pass

        # 2. Preenchimento (Mantendo o método FILL que funcionou para você)
        logger.info("Filling credentials...")
        await page.fill("#username", username)
        await asyncio.sleep(0.5)
        await page.fill("#password", password)
        await asyncio.sleep(0.5)
        await page.press("#password", "Enter")
        logger.info("Credentials submitted. Waiting...")
        
        # 3. Wait for redirect/load
        await asyncio.sleep(10)
        
        # 4. VALIDAÇÃO PÓS-LOGIN (Novo)
        # Se aparecer Access Denied, lança erro específico
        if await _check_waf_block(page):
            raise Exception("LOGIN BLOCKED: WAF Access Denied detectado.")

        # Se o botão entrar ainda estiver visível, o login falhou
        if await page.locator("#username").is_visible(timeout=2000) or await page.get_by_text("Entrar").first.is_visible(timeout=2000):
            raise Exception("LOGIN FALHOU: Botão entrar ainda visível.")

    except Exception as e:
        logger.error(f"Login Interaction Failed: {e}")
        # Se for bloqueio, repassa o erro para o retry pegar
        if "BLOCKED" in str(e): raise e
        await save_screenshot(page, "login_failed")
        raise e

async def _ensure_clean_tab(context, page=None):
    """Fecha aba atual e abre uma nova limpa."""
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
    
    # --- Passo 1: Identificar Aba Existente ---
    page = None
    for p in context.pages:
        try:
            if "livelo.com.br" in p.url:
                page = p
                await page.bring_to_front()
                # Stop suave para evitar travamentos de carregamento
                try: await p.evaluate("window.stop()")
                except: pass
                break
        except: pass
        
    max_retries = 2
    attempt = 0
    final_error = None
    final_screenshot = None

    while attempt < max_retries:
        attempt += 1
        logger.info(f"🔄 Tentativa {attempt}/{max_retries}")
        
        try:
             # Se não tem página ou é retry, abre nova
            if not page or attempt > 1:
                if attempt > 1: logger.info("♻️ Retry: Abrindo aba limpa...")
                page = await _ensure_clean_tab(context, page)
                await page.goto("https://www.livelo.com.br/", timeout=60000)
            
            # WAF Check Inicial
            if await _check_waf_block(page):
                raise Exception("BLOQUEIO WAF INICIAL")

            # --- Otimização: Já estamos logados? ---
            # Tenta extrair IMEDIATAMENTE. Como removemos o Regex, isso é seguro.
            # Se retornar numero, é porque achou a classe .l-header__user-profile-balance
            if attempt == 1:
                points = await _extract_points(page)
                if points is not None:
                    logger.info(f"✅ SUCESSO RÁPIDO (Já logado): {points}")
                    return points, None

            # Se chegamos aqui, ou não estamos logados, ou a página tá velha
            if attempt == 1 and "acesso.livelo.com.br" not in page.url:
                logger.info("Atualizando página para garantir...")
                try: 
                    await page.reload(wait_until="domcontentloaded")
                    await asyncio.sleep(5)
                except: pass
                
                if await _check_waf_block(page): raise Exception("BLOQUEIO WAF PÓS-RELOAD")
                
                # Tenta extrair de novo pós-reload
                points = await _extract_points(page)
                if points is not None:
                    logger.info(f"✅ SUCESSO (Pós-Reload): {points}")
                    return points, None

            # --- Login Obrigatório ---
            logger.info("Pontos não encontrados. Iniciando Login...")
            await perform_login(page, username, password)
            
            # Check final
            points = await _extract_points(page)
            if points is not None:
                logger.info(f"✅ SUCESSO (Pós-Login): {points}")
                if attempt > 1:
                    try: await page.close()
                    except: pass
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


async def extract_latam(context):
    """
    Mantido conforme original (desativado no orchestrator, mas o código fica aqui)
    """
    return None

async def get_balance(username, password, adspower_user_id=None):
    if not adspower_user_id:
        return {"status": "error", "message": "Missing adspower_user_id"}

    ws_endpoint = await AdsPowerController.start_profile(adspower_user_id)
    if not ws_endpoint:
        return {"status": "error", "message": "Failed to start AdsPower profile"}

    playwright = await async_playwright().start()
    browser = None
    
    try:
        logger.info(f"Connecting CDP: {ws_endpoint}")
        browser = await playwright.chromium.connect_over_cdp(ws_endpoint)
        context = browser.contexts[0] if browser.contexts else await browser.new_context()

        # --- 1. LIVELO ---
        result = await extract_livelo(context, username, password)
        
        livelo_balance = None
        error_screenshot = None
        
        if isinstance(result, tuple):
             livelo_balance, error_screenshot = result
        elif isinstance(result, dict):
             livelo_balance = result.get("livelo")
             error_screenshot = result.get("screenshot")
        else:
             livelo_balance = result

        latam_balance = None
        
        if livelo_balance is not None: 
             await update_account_db_multi(username, "active", 
                                           livelo_val=livelo_balance, 
                                           latam_val=latam_balance)
                           
             return {
                 "status": "success",
                 "livelo": livelo_balance,
                 "latam": latam_balance,
                 "error_screenshot": None
             }
        else:
            return {
                "status": "error", 
                "message": "Failed to extract Livelo",
                "livelo": None,
                "latam": None,
                "error_screenshot": error_screenshot
            }

    except Exception as e:
        logger.error(f"Global Scraper Error: {e}")
        return {"status": "error", "message": str(e), "livelo": None}
        
    finally:
        if playwright: await playwright.stop()