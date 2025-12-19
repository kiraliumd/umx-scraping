import os
import psycopg2
from dotenv import load_dotenv
from supabase import create_client

# Load env vars
load_dotenv()

def setup_db():
    print("Starting Database Setup...")
    
    # Check for Connection String
    db_url = os.getenv("DB_CONNECTION_STRING")
    
    if not db_url:
        print("WARNING: 'DB_CONNECTION_STRING' not found in .env.")
        return False

    # Helper to try connection
    def try_connect_and_execute(url, description):
        print(f"Attempting connection via {description}...")
        try:
            conn = psycopg2.connect(url)
            cur = conn.cursor()
            
            # DDL Statements
            ddl_commands = [
                """
                CREATE TABLE IF NOT EXISTS accounts (
                    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
                    username TEXT NOT NULL UNIQUE,
                    password TEXT NOT NULL,
                    last_balance INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'error', '2fa_required')),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                );
                """,
                # Add session_cookies column if not exists
                """
                ALTER TABLE accounts 
                ADD COLUMN IF NOT EXISTS session_cookies JSONB DEFAULT NULL;
                """,
                # Add adspower_user_id column if not exists (AdsPower Integration)
                """
                ALTER TABLE accounts 
                ADD COLUMN IF NOT EXISTS adspower_user_id TEXT UNIQUE DEFAULT NULL;
                """,
                """
                CREATE TABLE IF NOT EXISTS balance_logs (
                    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
                    account_id UUID REFERENCES accounts(id),
                    old_balance INTEGER,
                    new_balance INTEGER,
                    checked_at TIMESTAMPTZ DEFAULT NOW()
                );
                """,
                "ALTER TABLE accounts ENABLE ROW LEVEL SECURITY;",
                "ALTER TABLE balance_logs ENABLE ROW LEVEL SECURITY;",
                """
                DO $$ 
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_policies WHERE policyname = 'Service Role Full Access' AND tablename = 'accounts'
                    ) THEN
                        CREATE POLICY "Service Role Full Access" ON accounts
                        FOR ALL USING (auth.role() = 'service_role');
                    END IF;
                END $$;
                """
            ]
            
            for cmd in ddl_commands:
                # print(f"Executing: {cmd[:50]}...")
                cur.execute(cmd)
                
            conn.commit()
            print("DDL executed successfully.")
            
            # Seed Data
            print("Seeding test data...")
            try:
                cur.execute("""
                    INSERT INTO accounts (username, password, status)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (username) DO NOTHING;
                """, ('teste_livelo', '12345', 'active'))
                conn.commit()
                print("Seed data inserted.")
            except Exception as e:
                print(f"Error seeding data: {e}")
                conn.rollback()
                
            cur.close()
            conn.close()
            return True
        except Exception as e:
            print(f"Connection failed ({description}): {e}")
            return False

    # 1. Try Direct Connection
    if try_connect_and_execute(db_url, "Direct Connection"):
        return True

    # 2. Try Fallback to Supavisor (IPv4)
    # Parse original URL
    try:
        from urllib.parse import urlparse
        parsed = urlparse(db_url)
        
        # Extract project ref from hostname: db.[ref].supabase.co
        if 'supabase.co' in parsed.hostname:
            parts = parsed.hostname.split('.')
            if len(parts) >= 4:
                project_ref = parts[1]
                user = parsed.username
                password = parsed.password
                
                # Construct Pooler URL (Session Mode)
                # Try SA-EAST-1 (Brazil) first, then US-EAST-1
                regions = ['aws-0-sa-east-1', 'aws-0-us-east-1']
                
                for region in regions:
                    pooler_host = f"{region}.pooler.supabase.com"
                    # Username format for pooler: user.project_ref
                    pooler_user = f"{user}.{project_ref}"
                    
                    pooler_url = f"postgres://{pooler_user}:{password}@{pooler_host}:6543/postgres"
                    
                    if try_connect_and_execute(pooler_url, f"Pooler ({region})"):
                        return True
    except Exception as e:
        print(f"Error constructing fallback URL: {e}")

    print("All connection attempts failed.")
    return False

if __name__ == "__main__":
    success = setup_db()
    if not success:
        exit(1)
