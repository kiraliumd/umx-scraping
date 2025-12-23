import os
import sys
import asyncio

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from supabase import create_client, Client
from src.crypto_utils import encrypt_password

load_dotenv()

url: str = os.environ.get("SUPABASE_URL", "")
key: str = os.environ.get("SUPABASE_KEY", "")
supabase: Client = create_client(url, key)

async def migrate_vault():
    print(">>> Starting Password Encryption Migration...")
    
    # 1. Fetch all accounts
    response = supabase.table("accounts").select("id, username, password, latam_password").execute()
    accounts = response.data
    
    if not accounts:
        print("No accounts found for migration.")
        return

    print(f"Found {len(accounts)} accounts. Processing...")
    
    updated_count = 0
    for acc in accounts:
        acc_id = acc['id']
        username = acc['username']
        raw_pass = acc['password']
        raw_latam_pass = acc['latam_password']
        
        # Skip if already encrypted (Fernet strings usually start with gAAAA)
        # We check both to be safe
        is_encrypted = raw_pass.startswith("gAAAA")
        
        data_to_update = {}
        
        if not is_encrypted:
            data_to_update["password"] = encrypt_password(raw_pass)
            
        if raw_latam_pass and not raw_latam_pass.startswith("gAAAA"):
            data_to_update["latam_password"] = encrypt_password(raw_latam_pass)
            
        if data_to_update:
            print(f"Encrypting passwords for: {username}")
            supabase.table("accounts").update(data_to_update).eq("id", acc_id).execute()
            updated_count += 1
            
    print(f"Migration complete. {updated_count} accounts updated.")

if __name__ == "__main__":
    asyncio.run(migrate_vault())
