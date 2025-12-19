import os
import asyncio
from dotenv import load_dotenv
from supabase import create_client, Client
import logging

# Load environment variables
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

url: str = os.environ.get("SUPABASE_URL", "")
key: str = os.environ.get("SUPABASE_KEY", "")

# For DDL we might need direct connection string if RLS blocks us, 
# but let's try calling a SQL function or using postgres library directly if supabase-py doesn't support raw SQL easily.
# Actually, supabase-py is an interface to PostgREST. Standard client doesn't run arbitrary DDL easily unless via a stored procedure.
# We should use the DB_CONNECTION_STRING with psycopg2 or similar for Schema changes.

import psycopg2

def update_schema():
    db_string = os.environ.get("DB_CONNECTION_STRING", "")
    if not db_string:
        logger.error("DB_CONNECTION_STRING is required for schema updates.")
        return

    try:
        logger.info("Connecting to database...")
        conn = psycopg2.connect(db_string)
        cur = conn.cursor()
        
        logger.info("Adding session_cookies column if not exists...")
        cur.execute("ALTER TABLE accounts ADD COLUMN IF NOT EXISTS session_cookies JSONB;")
        
        conn.commit()
        cur.close()
        conn.close()
        logger.info("Schema updated successfully.")
        
    except Exception as e:
        logger.error(f"Failed to update schema: {e}")

if __name__ == "__main__":
    update_schema()
