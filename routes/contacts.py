from datetime import datetime

from flask import Blueprint, request, render_template, session, flash, redirect

from routes.common import session_required, login_required, GLOBAL_TZ_MAP, REGIONS
from services.ghl_api import fetch_calendar_events
from services.appts_format import extract_contacts_scheduled
from services.sheets_api import (
    insert_day_contacts,
    insert_month_contacts,
    get_location_sheet,
    fetch_worksheets
)
from utils.formatting import normalize_date, compute_time_range
from utils.helpers import safe_google_call

contacts_bp = Blueprint("contacts", __name__)


@contacts_bp.route("/contacts/insert-in-sheet/day", methods=["GET", "POST"])
@login_required
@session_required
def contacts_for_day():
    # --- Handle Redirects First ---
    # Worksheet selection
    if request.method == "POST" and request.form.get("worksheet"):
        session["selected_ws"] = request.form.get("worksheet")
        return redirect("/contacts/insert-in-sheet/day")

    # Timezone change
    if request.method == "POST" and request.form.get("region"):
        session["tz_region"] = request.form.get("region")
        session["tz_zone"] = request.form.get("zone")
        return redirect("/contacts/insert-in-sheet/day")

    # --- Setup & Caching ---
    sheet_id = session.get("sheet_id")
    sheet = get_location_sheet(sheet_id)

    # Cache worksheet titles in the session
    if "ws_titles" not in session:
        worksheets = fetch_worksheets(sheet)
        session["ws_titles"] = [ws.title for ws in worksheets]

    ws_titles = session["ws_titles"]

    # Determine selected worksheet (default to the last one if none selected)
    selected_title = session.get("selected_ws")
    if not selected_title or selected_title not in ws_titles:
        selected_title = ws_titles[-1]
        session["selected_ws"] = selected_title

    # Lazy load ONLY the selected worksheet object
    current_ws = sheet.worksheet(selected_title)

    # Timezone resolution
    selected_region = session.get("tz_region", "America")
    selected_zone = session.get("tz_zone", "New_York")
    tz = f"{selected_region}/{selected_zone}"

    # --- GET request ---
    if request.method == "GET":
        return render_template(
            "contacts_for_day.html",
            date=None,
            contacts=[],
            worksheets=ws_titles,
            current_ws_title=selected_title,
            regions=REGIONS,
            zones=GLOBAL_TZ_MAP.get(selected_region, []),
            tz_map=GLOBAL_TZ_MAP,
            selected_region=selected_region,
            selected_zone=selected_zone
        )

    # --- POST request (Contact logic) ---
    date_str = request.form.get("date")
    if not date_str:
        return "Missing date", 400

    # Fetch Calendar Events
    json_data = fetch_calendar_events(
        session["location_id"],
        session["calendar_id"],
        session["access_token"],
        *compute_time_range(date_str, tz=tz)
    ).json()

    contacts = extract_contacts_scheduled(json_data) or []

    # Write to Google Sheets Safely
    if contacts:
        success = safe_google_call(
            insert_day_contacts,
            current_ws,
            normalize_date(date_str),
            contacts
        )

        # If the safe call returns None, it exhausted all retries
        if success is None:
            return "The Google Sheets API is currently busy. Please try again in a minute.", 503

    # Re-render with results
    return render_template(
        "contacts_for_day.html",
        date=date_str,
        contacts=contacts,
        worksheets=ws_titles,
        current_ws_title=selected_title,
        regions=REGIONS,
        zones=GLOBAL_TZ_MAP.get(selected_region, []),
        tz_map=GLOBAL_TZ_MAP,
        selected_region=selected_region,
        selected_zone=selected_zone
    )


@contacts_bp.route("/contacts/insert-in-sheet/month", methods=["GET", "POST"])
@login_required
@session_required
def contacts_for_month():
    sheet_id = session.get("sheet_id")
    sheet = get_location_sheet(sheet_id)

    if "ws_titles" not in session:
        worksheets = fetch_worksheets(sheet)
        session["ws_titles"] = [ws.title for ws in worksheets]

    ws_titles = session["ws_titles"]
    selected_title = session.get("selected_ws") or ws_titles[-1]

    # Handle GET request
    if request.method == "GET":
        return render_template(
            "contacts_for_month.html",
            worksheets=ws_titles,
            current_ws_title=selected_title,
            month_str=datetime.now().strftime("%Y-%m")
        )

    # Handle POST request
    month_str = request.form.get("month_select")  # From the template
    tz = "America/New_York"  # Or pull from session

    start_ms, end_ms = compute_time_range(month_str, tz, mode="month")

    # Safe Google Call for fetching
    response = safe_google_call(
        fetch_calendar_events,
        session["location_id"],
        session["calendar_id"],
        session["access_token"],
        start_ms,
        end_ms
    )

    if response is None:
        flash("The Google Calendar API is currently busy. Please try again in a minute.", "info")
        return render_template(
            "contacts_for_month.html",
            month_str=month_str,
            worksheets=ws_titles,
            current_ws_title=selected_title,
        )

    json_data = response.json()
    contacts = extract_contacts_scheduled(json_data, month=True)

    if not contacts:
        flash("No contacts found to insert", "info")
        return render_template(
            "contacts_for_month.html",
            month_str=month_str,
            worksheets=ws_titles,
            current_ws_title=selected_title,
        )

    ws = sheet.worksheet(selected_title)
    rows_inserted = safe_google_call(insert_month_contacts, ws, contacts)

    if rows_inserted is None:
        flash("The Google Sheets API is currently busy. Please try again in a minute.", "info")
    elif len(rows_inserted) >= 1:
        flash(f"Successfully added {len(rows_inserted)} rows to the sheet!", "success")
    else:
        flash("Sheet is already synced", "info")

    return render_template(
        "contacts_for_month.html",
        month_str=month_str,
        worksheets=ws_titles,
        current_ws_title=selected_title,
    )
