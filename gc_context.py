"""
Init gspread
The service account JSON file can be retrieved from the Google Developers Console.
See https://docs.gspread.org/en/latest/oauth2.html
"""

import gspread
from pathlib import Path

gc = gspread.service_account(str(Path(__file__).parent / '.service_account.json'))
