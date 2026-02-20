import gspread
from collections import defaultdict
from datetime import datetime
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

def insert_contacts_for_month(
    worksheet: gspread.Worksheet,
    contacts: List[Dict[str, str]]
) -> List[int]:

    inserted_rows = []

    grouped = defaultdict(list)

    for contact in contacts:
        if not contact.get("date"):
            continue

        grouped[contact["date"]].append(contact)

    # Sort chronologically
    sorted_dates = sorted(
        grouped.keys(),
        key=lambda d: datetime.strptime(d, "%m/%d/%Y")
    )
    
    for date in sorted_dates:
        rows = insert_contacts_after_row(
            worksheet,
            date,
            grouped[date]
        )
        inserted_rows.extend(rows)

    return inserted_rows

def insert_contacts_after_row(
    worksheet: gspread.Worksheet,
    date: str,
    contacts: List[Dict[str, str]]
) -> List[int]:

    inserted_rows = []

    start_row, _= find_insertion_row(worksheet, date)
    current_row = start_row + 1

    already = already_inserted_for_date(worksheet)
    existing_phones = already.get(date, set())

    for entry in contacts:
        name = entry.get("name", "")
        phone = format_us_phone(entry.get("phone", ""))

        if phone in existing_phones:
            continue

        worksheet.insert_row(
            [name, phone, None, date],
            index=current_row,
            inherit_from_before=True if current_row > 2 else None,
            value_input_option="USER_ENTERED"
        )

        inserted_rows.append(current_row)
        current_row += 1

    return inserted_rows

def find_insertion_row(ws: gspread.Worksheet, target_date: str) -> tuple[int, bool]:
    """
    Returns:
        (row_index, date_exists)

    row_index → the row AFTER which new rows should be inserted
    date_exists → whether this exact date already exists
    """

    dates = ws.col_values(4)

    last_match = None
    next_larger = None

    target_date = datetime.strptime(target_date, "%m/%d/%Y").date()
    
    for i, value in enumerate(dates):
        try:
            current_dt = datetime.strptime(value, "%m/%d/%Y").date()
        except:
            continue

        if current_dt == target_date:
            last_match = i + 1

        elif current_dt > target_date and next_larger is None:
            next_larger = i + 1

    if last_match is not None:
        return last_match, True

    if next_larger is not None:
        return next_larger - 1, False

    return len(dates), False


def already_inserted_for_date(ws: gspread.Worksheet) -> dict[str, set[str]]:
    """
    Returns a dict mapping:
    {
        "MM/DD/YYYY": {"+15551234567", "+15559876543", ...}
    }
    """
    dates = ws.col_values(4)   # column D
    phones = ws.col_values(2) # column B

    result = defaultdict(set)

    for d, p in zip(dates, phones):
        if not d or not p:
            continue
        result[d].add(p.strip())

    return dict(result)