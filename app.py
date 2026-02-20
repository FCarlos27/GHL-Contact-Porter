from flask import Flask, request, render_template, redirect, session
from datetime import datetime
from services.ghl_api import (
    ensure_location_name,
    fetch_calendar_events,
)
from services.gist_storage import (
    save_tokens,
    get_all_locations_name_id,
    get_location_data,
    token_is_stale
    )
from services.oauth import (
    exchange_code_for_tokens,
    refresh_if_needed
)
from services.appts import (
    compute_time_range,
    create_appointments_html,
    extract_contacts_scheduled
)
from services.sheets_api import (
    insert_contacts_after_row,
    insert_contacts_for_month,
    select_worksheet,
    get_location_sheet
)

app = Flask(__name__)
app.secret_key = "a-strong-secret-key"


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
def menu():
    if "location_id" not in session:
        return redirect("/")

    selected_location = session["location_id"]
    access_token= session["access_token"]
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
 
    # Get locationId + tokens from GH
    location_id, access, refresh = exchange_code_for_tokens(code)
    
    # Save tokens
    save_tokens(location_id, access, refresh)
   
    # Save location name (fetches from GHL if missing)
    ensure_location_name(location_id)

    return f"App installed successfully for location: {location_id}"

@app.route("/contacts/insert-in-sheet/day", methods=["GET", "POST"])
def contacts_for_day():
    if request.method == "GET":
        return render_template(
            "contacts_for_day.html",
            date=None,
            contacts=[]
        )

    date_str = request.form.get("date")
    if not date_str:
        return "Missing date", 400

    json_data = fetch_calendar_events(
        session["location_id"],
        session["calendar_id"],
        session["access_token"],
        *compute_time_range(date_str, "America/New_York")
    ).json()

    contacts = extract_contacts_scheduled(json_data) or []

    if contacts:
        sheet = get_location_sheet(session["sheet_id"])
        ws = select_worksheet(sheet)
        insert_contacts_after_row(ws, date_str, contacts)

    return render_template(
        "contacts_for_day.html",
        date=date_str,
        contacts=contacts
    )

@app.route("/contacts/insert-in-sheet/month")
def contacts_for_month():

    tz = "America/New_York"

    # Get current month in YYYY-MM format
    today = datetime.now()
    month_str = today.strftime("%Y-%m")

    # Compute start/end timestamps
    start_ms, end_ms = compute_time_range(month_str, tz, mode="month")

    # Fetch events
    response = fetch_calendar_events(
        session["location_id"],
        session["calendar_id"],
        session["access_token"],
        start_ms,
        end_ms
    )

    json_data = response.json()

    # Extract contacts
    contacts = extract_contacts_scheduled(json_data, month=True)

    if not contacts:
        return {"message": "No contacts found for this month."}, 200

    # Insert into sheet
    sheet = get_location_sheet(session["sheet_id"])
    ws = select_worksheet(sheet)

    inserted = insert_contacts_for_month(ws, contacts)

    return {
        "inserted_count": len(inserted),
        "month": month_str
    }, 200



if __name__ == '__main__':
    app.run(debug=True, port=5000)
