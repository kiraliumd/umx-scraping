
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import logging
from datetime import datetime
from dotenv import load_dotenv

# Setup Logging
logger = logging.getLogger("SheetsLogger")

class SheetsLogger:
    def __init__(self):
        self.scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]
        self.creds_file = "service_account.json"
        self.spreadsheet_id = os.getenv("GOOGLE_SHEET_ID")
        self.client = None
        self.sheet = None
        
        # Load env if needed (should already be loaded by main, but safe to ensure)
        load_dotenv()
        
        if not self.spreadsheet_id:
            logger.error("GOOGLE_SHEET_ID missing from environment.")
            return

        try:
            self._connect()
        except Exception as e:
            logger.error(f"Failed to connect to Google Sheets: {e}")

    def _connect(self):
        if not os.path.exists(self.creds_file):
            logger.error(f"Credentials file '{self.creds_file}' not found.")
            return

        creds = ServiceAccountCredentials.from_json_keyfile_name(self.creds_file, self.scope)
        self.client = gspread.authorize(creds)
        
        try:
            doc = self.client.open_by_key(self.spreadsheet_id)
            # Try to get specific tab
            try:
                self.sheet = doc.worksheet("saldo dos programas")
            except gspread.WorksheetNotFound:
                # Create if missing
                logger.info("Tab 'saldo dos programas' not found. Creating...")
                self.sheet = doc.add_worksheet(title="saldo dos programas", rows=1000, cols=10)
                self.sheet.append_row(['Data', 'Username', 'Programa', 'Saldo', 'Status', 'Detalhe'])
                
        except Exception as e:
            logger.error(f"Error opening sheet: {e}")
            raise e

    def log_execution(self, username, balance, status, detail=""):
        if not self.sheet:
            logger.warning("SheetsLogger not authorized or connected. Skipping log.")
            return

        try:
            now = datetime.now().strftime("%d/%m/%Y %H:%M")
            
            # Handle None balance
            safe_balance = balance if balance is not None else "-"
            if safe_balance == 0: safe_balance = "0"
            
            row = [
                now,
                username,
                "Livelo",
                str(safe_balance),
                status,
                str(detail)
            ]
            
            self.sheet.insert_row(row, index=2)
            logger.info(f"Logged to Sheets: {username} - {status}")
            
        except Exception as e:
            logger.error(f"Failed to log row to sheets: {e}")
            # Optional: Retry logic could go here
