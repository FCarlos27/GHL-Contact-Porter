import gspread
from typing import Dict, List
from utils.formatting import format_us_phone, normalize_date
from google.oauth2.service_account import Credentials

def get_location_sheet(sheet_id: str) -> gspread.Spreadsheet:
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_file(r"utils\credentials.json",
    scopes=scopes)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(sheet_id)
    
    return sheet

def select_worksheet(sheet:gspread.Spreadsheet, identifier: int|str =None) -> gspread.worksheet:
    """Select a worksheet from the Google Sheet"""

    # No identifier → return last worksheet
    if identifier is None:
        return sheet.worksheets()[-1]

    # Identifier is numeric → treat as gid
    if isinstance(identifier, int):
        for ws in sheet.worksheets():
            if ws.id == identifier:
                return ws
        raise ValueError(f"No worksheet found with gid={identifier}")

    # Identifier is string → treat as worksheet name
    if isinstance(identifier, str):
        return sheet.worksheet(identifier)

    raise TypeError("identifier must be None, int (gid), or str (worksheet name)")

def insert_contacts_after_row(worksheet: gspread.Worksheet,date: str,
    contacts: List[Dict[str, str]]) -> List[int]:
    """
    Inserts multiple contacts (name, phone) into the worksheet.
    Returns a list of row numbers where each contact was inserted.
    """
    
    inserted_rows = []

    start_row, is_mid = find_last_row_for_date(worksheet, date)

    # Extract target day
    target_day = int(normalize_date(date).split("/")[1])

    # Determine if the date actually exists in the sheet
    date_exists = False
    if start_row is not None:
        try:
            existing_day = int(worksheet.col_values(4)[start_row - 1].split("/")[1])
            date_exists = (existing_day == target_day)
        except:
            date_exists = False

    # Base insertion point
    if start_row is None:
        current_row = len(worksheet.col_values(1)) + 1
    else:
        current_row = start_row + 1

    # Insert separation row BEFORE only when this is a new date block
    if not date_exists and not is_mid:
        worksheet.insert_row(None, index=current_row)
        current_row += 1

    # Insert contacts
    for entry in contacts:
        name = entry.get("name", "")
        phone = entry.get("phone", "")

        worksheet.insert_row(
            [name, format_us_phone(phone), None, normalize_date(date)],
            index=current_row,
            inherit_from_before=True,
            value_input_option="USER_ENTERED"
        )
        inserted_rows.append(current_row)
        current_row += 1

    # Insert ONE separation row after only when this is a new date block
    if not date_exists:
        worksheet.insert_row(None, index=current_row)

    return inserted_rows


def find_last_row_for_date(ws: gspread.worksheet, target_date: str) -> tuple:
    """Returns the correct insertion row for a given date by scanning the sheet’s date column, 
    finding the last row with the same day, or—if no match exists—locating the next larger day so the new entry is placed in proper chronological order."""
    
    # target_date is MM/DD/YYYY
    target_day = int(normalize_date(target_date).split("/")[1])

    dates = ws.col_values(4)  # column D

    # Extract day numbers
    day_numbers = []
    for d in dates:
        try:
            day_numbers.append(int(d.split("/")[1]))
        except:
            day_numbers.append(None)

    last_match = None
    next_larger = None

    for i, day in enumerate(day_numbers):
        if day is None:
            continue

        # Track last exact match
        if day == target_day:
            last_match = i + 1

        # First larger day
        if day > target_day and next_larger is None:
            next_larger = i + 1

    # insert after last match
    if last_match is not None:
        return last_match, False

    # no match, but a larger day exists → mid insertion
    if next_larger is not None:
        # Insert BEFORE the larger date block
        return next_larger - 1, True

    # no match and no larger day → append at bottom, not mid
    return len(dates), False

