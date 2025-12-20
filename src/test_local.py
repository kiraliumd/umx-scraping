import asyncio
import os
import sys
from dotenv import load_dotenv
from supabase import create_client, Client

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.scraper import get_balance

# Load environment variables
load_dotenv()

async def main():
    print("=== Livelo Scraper Local Test (Automated) ===")
    
    # Initialize Supabase
    url: str = os.environ.get("SUPABASE_URL", "")
    key: str = os.environ.get("SUPABASE_KEY", "")
    
    if not url or not key:
        print("Error: SUPABASE_URL and SUPABASE_KEY must be set in .env")
        return

    supabase: Client = create_client(url, key)

    # Fetch one account
    print("Fetching one account from Supabase...")
    try:
        # Busca especificamente contas que começam com 0 para teste de validação
        response = supabase.table("accounts")\
            .select("*")\
            .like("username", "0%")\
            .limit(1)\
            .execute()
        
        accounts = response.data
        
        if not accounts:
            print("Error: No accounts found in database starting with '0'.")
            return
            
        acc = accounts[0]
        username = acc['username']
        password = acc['password']
        cookies = acc.get('session_cookies')
        adspower_id = acc.get('adspower_user_id')
        
        print(f"\nConta Recuperada do Banco: {username}")
        print(f"Testando com a conta: {username}")
        # Mask password
        masked_pass = "*" * len(password) if password else "EMPTY"
        print(f"Password: {masked_pass}")
        if cookies:
            print(f"Cookies encontrados: {len(cookies)} itens.")
        else:
            print("Nenhum cookie salvo encontrado (Login completo será realizado).")

        if not adspower_id:
            print("SKIPPING: No AdsPower ID found for this account.")
            return # Changed from 'continue' as this is not a loop
            
        print(f"AdsPower ID: {adspower_id}")
        
    except Exception as e:
        print(f"Error fetching account from DB: {e}")
        return

    print(f"\nStarting scraper for user: {username}...")
    print("Check 'debug/' folder for screenshots if errors occur.\n")
    
    try:
        # Pass account_id if available to update specific record?
        # get_balance updates by username, so it's fine.
        result = await get_balance(username, password, adspower_user_id=adspower_id)
        
        print("\n=== Result ===")
        print(result)
        
        if result.get("status") == "success":
            print("\nSUCCESS: Balance retrieved and DB updated.")
        else:
            print("\nFAILURE: Scraper returned error.")
            
    except Exception as e:
        print(f"\nCRITICAL ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(main())
