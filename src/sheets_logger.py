
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
        self.doc = None
        
        # Load env if needed (should already be loaded by main, but safe to ensure)
        load_dotenv()
        
        if not self.spreadsheet_id:
            logger.error("GOOGLE_SHEET_ID missing from environment.")
            return

        if not os.path.exists(self.creds_file):
            logger.error(f"Credentials file '{self.creds_file}' not found.")
            return

        try:
            creds = ServiceAccountCredentials.from_json_keyfile_name(self.creds_file, self.scope)
            self.client = gspread.authorize(creds)
            
            self.doc = self.client.open_by_key(self.spreadsheet_id)
            logger.info("Connected to Spreadsheet successfully.")
        except Exception as e:
            logger.error(f"Error opening sheet: {e}")
            raise e

    def log_execution(self, username, balance, status, program="Livelo", detail="", tab_name=None):
        """
        Logs an execution to a specific tab in Google Sheets.
        Default tab is 'saldo dos programas'.
        """
        if not self.doc:
            logger.warning("SheetsLogger not connected. Skipping log.")
            return

        # Define target tab based on program if not explicitly provided
        if not tab_name:
            if program.lower() == "latam":
                target_tab = "latam"
            else:
                target_tab = "saldo dos programas" # Keep default for Livelo/Others
        else:
            target_tab = tab_name

        try:
            # Robust case-insensitive worksheet detection
            worksheet_list = self.doc.worksheets()
            worksheet_titles = [w.title for w in worksheet_list]
            tab_map = {t.lower(): t for t in worksheet_titles}
            
            if target_tab.lower() in tab_map:
                actual_title = tab_map[target_tab.lower()]
                worksheet = self.doc.worksheet(actual_title)
            else:
                logger.info(f"Tab '{target_tab}' not found. Creating...")
                worksheet = self.doc.add_worksheet(title=target_tab, rows=1000, cols=10)
                worksheet.append_row(['Data', 'Username', 'Programa', 'Saldo', 'Status', 'Detalhe'])

            now = datetime.now().strftime("%d/%m/%Y %H:%M")
            
            # Handle None balance
            safe_balance = balance if balance is not None else "-"
            if safe_balance == 0: safe_balance = "0"
            
            row = [
                now,
                username,
                program,
                str(safe_balance),
                status,
                str(detail)
            ]
            
            worksheet.insert_row(row, index=2)
            logger.info(f"Logged to Sheets ({target_tab}): {username} - {program} - {status}")
            
        except Exception as e:
            logger.error(f"Failed to log row to sheets (tab: {target_tab}): {e}")
