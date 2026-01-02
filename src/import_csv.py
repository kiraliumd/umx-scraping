import csv
import os
import sys
import asyncio
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from supabase import create_client, Client
from src.crypto_utils import encrypt_password

# Load environment variables
load_dotenv()

# Supabase setup
url: str = os.environ.get("SUPABASE_URL", "")
key: str = os.environ.get("SUPABASE_KEY", "")

if not url or not key:
    print("Error: SUPABASE_URL and SUPABASE_KEY must be set in .env")
    exit(1)

supabase: Client = create_client(url, key)

async def import_accounts(csv_path: str):
    if not os.path.exists(csv_path):
        print(f"Error: File {csv_path} not found.")
        return

    print(f"Reading {csv_path}...")
    
    count = 0
    updated = 0
    errors = 0
    
    with open(csv_path, mode='r', encoding='utf-8') as f:
        reader = csv.reader(f)
        # Skip header if it exists and looks like a header
        # We can peek or just assume user knows.
        # Let's just read and check if first row is header-like
        rows = list(reader)
        
        start_index = 0
        if rows and len(rows) > 0:
            if "username" in rows[0][0].lower():
                print("Header detected, skipping first row.")
                start_index = 1
        
        for row_num, row in enumerate(rows[start_index:]):
            if not row: # Skip empty rows
                continue

            # Format: username,password,adspower_id,latam_password
            if len(row) < 2:
                print(f"Warning: Row {row_num + 1} has less than 2 columns, skipping.")
                errors += 1
                continue

            username = row[0].strip()
            
            # 1. Sanitization (Zero Pad)
            if username.isdigit() and len(username) < 11:
                username = username.zfill(11)
            
            password = row[1].strip()
            adspower_id = row[2].strip() if len(row) > 2 else None
            latam_password = row[3].strip() if len(row) > 3 else None
            
            if not username or not password:
                print(f"Warning: Row {row_num + 1} has empty username or password, skipping.")
                errors += 1
                continue
                
            try:
                # 2. AdsPower ID Conflict Resolution (Smart Fix)
                if adspower_id:
                    # Check who currently owns this ID
                    owner_check = supabase.table("accounts").select("username").eq("adspower_user_id", adspower_id).execute()
                    if owner_check.data:
                        owner_username = owner_check.data[0]['username']
                        
                        if owner_username != username:
                            # Conflict detected!
                            # Check if the CSV username already exists in DB
                            target_check = supabase.table("accounts").select("username").eq("username", username).execute()
                            
                            if not target_check.data:
                                # Scenario A: Same person, CPF corrected/changed. Rename old record.
                                print(f"♻️ Renaming account {owner_username} to {username} based on AdsPower ID...")
                                supabase.table("accounts").update({"username": username}).eq("username", owner_username).execute()
                            else:
                                # Scenario B: ID Transfer/Conflict. Free the ID from the old owner.
                                print(f"⚠️ Unlinking AdsPower ID {adspower_id} from obsolete account {owner_username}...")
                                supabase.table("accounts").update({"adspower_user_id": None}).eq("username", owner_username).execute()

                # 3. Persistence (Upsert)
                data = {
                    "username": username,
                    "password": encrypt_password(password),
                    "status": "active",
                    "updated_at": "now()"
                }
                if adspower_id:
                    data["adspower_user_id"] = adspower_id
                if latam_password:
                    data["latam_password"] = encrypt_password(latam_password)
                
                # Upsert ensures passwords and IDs are updated from CSV
                response = supabase.table("accounts").upsert(data, on_conflict="username").execute()
                
                if response.data:
                    count += 1
                    print(f"✅ Processed: {username} (AdsPower: {adspower_id if adspower_id else 'N/A'})")
                else:
                    updated += 1
                    
            except Exception as e:
                print(f"❌ Error processing {username}: {e}")
                errors += 1
                
    print(f"Import complete.")
    print(f"Processed: {count + updated}")
    print(f"Errors: {errors}")

if __name__ == "__main__":
    csv_file = sys.argv[1] if len(sys.argv) > 1 else "contas.csv"
    asyncio.run(import_accounts(csv_file))
