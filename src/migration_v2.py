
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def run_migration():
    print("Running Migration V2: Schema Refactoring for Multi-Program...")
    
    db_url = os.environ.get("DB_CONNECTION_STRING")
    if not db_url:
        print("Error: DB_CONNECTION_STRING not found in .env")
        exit(1)

    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        
        # 1. Drop old column
        print("- Dropping 'session_cookies'...")
        cur.execute("ALTER TABLE accounts DROP COLUMN IF EXISTS session_cookies;")
        
        # 2. Rename last_balance -> livelo_balance
        print("- Renaming 'last_balance' to 'livelo_balance'...")
        # Check if it exists first to avoid error if re-running
        try:
            cur.execute("ALTER TABLE accounts RENAME COLUMN last_balance TO livelo_balance;")
        except psycopg2.errors.UndefinedColumn:
            print("  (Column 'last_balance' might have already been renamed)")
            conn.rollback()
        except psycopg2.errors.DuplicateColumn:
            print("  (Column 'livelo_balance' already exists)")
            conn.rollback()
        
        # 3. Add latam_balance (if not exists)
        print("- Ensuring 'latam_balance' exists...")
        cur.execute("ALTER TABLE accounts ADD COLUMN IF NOT EXISTS latam_balance BIGINT DEFAULT 0;")
        
        # 4. Add 'program' to balance_logs
        print("- Adding 'program' column to balance_logs...")
        cur.execute("ALTER TABLE balance_logs ADD COLUMN IF NOT EXISTS program TEXT;")
        
        # Note: Adding CHECK constraint using DO block or just assume app logic handles it to avoid complex SQL errors on re-run
        # Use simple check constraint if adding new
        try:
             cur.execute("ALTER TABLE balance_logs ADD CONSTRAINT check_program CHECK (program IN ('livelo', 'latam'));")
        except psycopg2.errors.DuplicateObject:
             conn.rollback() # Constraint likely exists
        
        # 5. Backfill old logs
        print("- Backfilling old logs as 'livelo'...")
        cur.execute("UPDATE balance_logs SET program = 'livelo' WHERE program IS NULL;")
        
        conn.commit()
        print("Migration V2 Successful!")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"Migration Failed: {e}")
        exit(1)

if __name__ == "__main__":
    run_migration()
