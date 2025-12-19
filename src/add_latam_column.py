
import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

url: str = os.environ.get("SUPABASE_URL", "")
key: str = os.environ.get("SUPABASE_KEY", "")

if not url or not key:
    print("Error: Supabase credentials not found.")
    exit(1)

supabase: Client = create_client(url, key)

def run_migration():
    print("Running migration: ADD COLUMN latam_balance...")
    
    # Supabase-py client doesn't support direct DDL via `table()...` easily without RPC or similar.
    # However, we can use the PostgreSQL driver `psycopg2` if available or try to assume it might be done via dashboard.
    # But since we have `src/setup_db.py` using `psycopg2`, let's check if we can reuse that approach or just use SQL via an RPC if available.
    # The previous setup_db used psycopg2. I will implement this using psycopg2 for direct execution.
    
    import psycopg2
    
    # Connection string usually available in Supabase settings, but here we might rely on the one from .env if it exists.
    # Check if DB_CONNECTION_STRING is in .env (it was in previous logs).
    db_url = os.environ.get("DB_CONNECTION_STRING")
    if not db_url:
        print("DB_CONNECTION_STRING not found in .env. Attempting to construct from components or fail.")
        # Fallback to direct supabase URL parsing if possible, but connection string is safer.
        # Let's assume user has it or we guide them.
        # Previous summary showed DB_CONNECTION_STRING variable exists.
        pass

    if db_url:
        try:
            conn = psycopg2.connect(db_url)
            cur = conn.cursor()
            
            sql = "ALTER TABLE accounts ADD COLUMN IF NOT EXISTS latam_balance BIGINT DEFAULT NULL;"
            cur.execute(sql)
            conn.commit()
            
            print("Migration successful: 'latam_balance' column added.")
            cur.close()
            conn.close()
        except Exception as e:
            print(f"Migration failed: {e}")
    else:
        print("Skipping direct DDL (No Connection String). Please run SQL manually:")
        print("ALTER TABLE accounts ADD COLUMN IF NOT EXISTS latam_balance BIGINT DEFAULT NULL;")

if __name__ == "__main__":
    run_migration()
