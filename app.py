import os
from dotenv import load_dotenv
from flask import Flask, request, render_template, redirect, session, flash
from datetime import datetime
from functools import wraps

load_dotenv()

from services.ghl_api import (
    ensure_location_name,
    fetch_calendar_events,
)

from services.supabase import (
    save_tokens,
    save_location_name,
    get_all_locations_name_id,
    get_location_data,
    token_is_stale
)

from services.oauth import (
    exchange_code_for_credentials,
    get_company_locations,
    refresh_if_needed
)
from services.appts_format import (
    create_appointments_html,
    extract_contacts_scheduled
)
from services.sheets_api import (
    insert_day_contacts,
    insert_month_contacts,
    get_location_sheet,
    fetch_worksheets
)
from utils.formatting import (
    normalize_date,
    compute_time_range,
    build_timezone_map
)
from utils.helpers import (
    safe_google_call
)

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-fallback-only-use-locally")

GLOBAL_TZ_MAP = build_timezone_map()
REGIONS = list(GLOBAL_TZ_MAP.keys())

def session_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "location_id" not in session:
            flash("Please select a location first.", "info")
            return redirect("/")
        return f(*args, **kwargs)
    return decorated_function

@app.route("/", methods=["GET", "POST"])
def select_location():
    locations = get_all_locations_name_id()

    if request.method == "POST":
        chosen = request.form.get("location_id")
        loc_data = get_location_data(chosen)

        # Refresh only if needed
        if token_is_stale(loc_data.get("last_refresh")):
            new_access = refresh_if_needed(chosen, loc_data.get("refresh_token"))
            session["access_token"] = new_access
        else:
            session["access_token"] = loc_data.get("access_token")

        session["location_id"] = chosen
        session["calendar_id"] = loc_data.get("calendar_id")
        session["location_name"] = loc_data.get("name")
        session["sheet_id"] = loc_data.get("sheet_id")
        return redirect("/menu")

    return render_template("select_location.html", locations=locations)

@app.route("/menu", methods=["GET", "POST"])
@session_required
def menu():
    selected_location = session["location_id"]
    access_token = session["access_token"]
    calendar_id = session["calendar_id"]

    title = ""
    html = ""

    if request.method == "POST":
        option = request.form.get("option")
        date_input = request.form.get("date", "")

        # Determine date range
        if option == "1" and date_input:
            title = f"Appointments for {date_input}"
            start, end = compute_time_range(date_input, "America/New_York")

        elif option == "2":
            return redirect("/contacts/insert-in-sheet/day")

        elif option == "3":
            return redirect("/contacts/insert-in-sheet/month")

        elif option == "4":
            return "Exiting the program."

        # Fetch events
        response = fetch_calendar_events(
            selected_location,
            calendar_id,
            access_token,
            start,
            end
        )

        # Extract clean appointment data
        appointments = create_appointments_html(response.json())

        for i, desc in enumerate(appointments, start=1):
            html += f"{i}. {desc}<br><br>"

    return render_template(
        "menu.html",
        data=html,
        curr_year=datetime.now().year,
        title=title,
        selected_location=selected_location,
        location_name=session["location_name"]
    )

@app.route("/oauth/callback")
def oauth_callback():
    code = request.args.get("code")
    # Get credentials (tokens, locationId, companyId) from GHL
    credentials = exchange_code_for_credentials(code)

    access = credentials.get("accessToken")
    refresh = credentials.get("refreshToken")
    location_id = credentials.get("locationId")
    company_id = credentials.get("companyId")
    user_id = credentials.get("userId")

    if location_id:
        # Single-location install
        save_tokens(location_id, access, refresh, company_id, user_id)
        ensure_location_name(location_id)
        return f"App installed successfully for location: {location_id}"

    # Company-level install: save tokens for every accessible location
    locations = get_company_locations(access)
    for loc in locations:
        save_tokens(loc["id"], access, refresh, company_id, user_id)
        save_location_name(loc["id"], loc["name"])

    return f"App installed successfully for {len(locations)} locations."

@app.route("/contacts/insert-in-sheet/day", methods=["GET", "POST"])
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

@app.route("/contacts/insert-in-sheet/month", methods=["GET", "POST"])
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

if __name__ == '__main__':
    app.run(host="0.0.0.0", debug=True, port=5000)
