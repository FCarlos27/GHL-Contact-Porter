import base64
import json
import os
from pathlib import Path
import gspread
from collections import defaultdict
from datetime import datetime
from typing import Dict, List
from dotenv import load_dotenv
from utils.helpers import format_us_phone, parse_date_value, format_date_key
from google.oauth2.service_account import Credentials

load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env")

scopes = ["https://www.googleapis.com/auth/spreadsheets"]

def _build_credentials():
    encoded = os.getenv("GOOGLE_CREDENTIALS_JSON_B64")
    if not encoded:
        raise RuntimeError("GOOGLE_CREDENTIALS_JSON_B64 is not set in .env")
    info = json.loads(base64.b64decode(encoded).decode("utf-8"))
    return Credentials.from_service_account_info(info, scopes=scopes)

creds = _build_credentials()
gspread_client = gspread.authorize(creds)

def get_location_sheet(sheet_id: str) -> gspread.Spreadsheet:
    return gspread_client.open_by_key(sheet_id)

def fetch_worksheets(sheet: gspread.Spreadsheet):
    """Returns a list of all worksheets <gspread.worksheet.Worksheet> in a spreadsheet."""
    worksheets = sheet.worksheets()
    return worksheets

def insert_month_contacts(
    worksheet: gspread.Worksheet,
    contacts: List[Dict[str, str]]
) -> List[List]:
    """
    Insert contacts into the worksheet grouped by date (MM/DD/YYYY).

    Contacts are sorted chronologically and inserted day by day.
    Existing entries are checked to avoid duplicates. The KPI block
    is snapshotted and restored to prevent unintended changes.

    Args:
        worksheet: Target Google Sheets worksheet.
        contacts: List of contact dicts containing a "date" key.

    Returns:
        List of inserted row values.
    """
    inserted_rows = []
    inserted_contacts = already_inserted_for_date(worksheet)
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
    row_data, sheet_id = snapshot_kpi_block(worksheet)

    for date in sorted_dates:
        rows = insert_day_contacts(
            worksheet,
            date,
            grouped[date],
            inserted_contacts=inserted_contacts
        )
        inserted_rows.extend(rows)

    restore_kpi_block(worksheet, row_data, sheet_id) # Ensures KPI cells are not altered
    return inserted_rows

def insert_day_contacts(
    worksheet: gspread.Worksheet,
    date: str,
    contacts: List[Dict[str, str]],
    inserted_contacts: dict[str, set[str]] | None = None
) -> List[List]:
    """
    Insert contacts for a specific date into the worksheet.

    Phone numbers are normalized and checked against already inserted
    contacts to prevent duplicates. New rows are batch-inserted at the
    appropriate position for the given date.

    Args:
        worksheet: Target Google Sheets worksheet.
        date: Date string in "MM/DD/YYYY" format.
        contacts: List of contact dicts containing "name" and "phone".
        inserted_contacts: Optional mapping of dates to existing phone sets.

    Returns:
        List of rows that were inserted (as raw row values).
    """
    if inserted_contacts is None:
        inserted_contacts = already_inserted_for_date(worksheet)

    existing_phones = inserted_contacts.setdefault(date, set())

    # Filter out duplicates FIRST
    rows_to_insert = []
    for entry in contacts:
        name = entry.get("name", "")
        phone = format_us_phone(entry.get("phone", ""))

        if phone in existing_phones:
            continue

        rows_to_insert.append([name, phone, None, date])
        existing_phones.add(phone)

    if not rows_to_insert:
        return []

    # Determine insertion row
    start_row, _ = find_insertion_row(worksheet, date)
    start_row = 2 if start_row <= 1 else start_row

    # Batch insert
    worksheet.insert_rows(
        rows_to_insert,
        row=start_row,
        value_input_option="USER_ENTERED"
    )

    return rows_to_insert

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
        current_dt = parse_date_value(value)
        if current_dt is None:
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
    phones = ws.col_values(2)  # column B

    result = defaultdict(set)

    for d, p in zip(dates, phones):
        if not d or not p:
            continue

        date_key = format_date_key(d)
        if date_key is None:
            continue

        result[date_key].add(p.strip())

    return dict(result)

def snapshot_kpi_block(worksheet):
    """
    Snapshot K1:P7 including formulas and formatting.
    """

    spreadsheet_id = worksheet.spreadsheet.id
    sheet_id = worksheet._properties["sheetId"]

    response = worksheet.spreadsheet.client.request(
        "get",
        f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}",
        params={
            "ranges": f"{worksheet.title}!K1:P7",
            "includeGridData": True
        }
    )

    data = response.json()

    row_data = data["sheets"][0]["data"][0].get("rowData", [])

    return row_data, sheet_id

def restore_kpi_block(worksheet, snapshot_row_data, sheet_id):
    """
    Restores K1:P7 with formatting and clears K8:P downward.
    """

    requests = []

    max_rows = worksheet.row_count
    # Clear everything below row 7 in K:P
    requests.append({
        "updateCells": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": 7,      # row 8
                "endRowIndex": max_rows,
                "startColumnIndex": 10,   # column K
                "endColumnIndex": 16
            },
            "fields": "userEnteredValue,userEnteredFormat"
        }
    })

    # Restore KPI block
    requests.append({
        "updateCells": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": 0,
                "endRowIndex": 8,
                "startColumnIndex": 10,
                "endColumnIndex": 16
            },
            "rows": snapshot_row_data,
            "fields": "userEnteredValue,userEnteredFormat"
        }
    })

    worksheet.spreadsheet.batch_update({
        "requests": requests
    })
