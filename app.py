from flask import Flask, request, render_template
from datetime import datetime
from services.ghl_api import (
    ensure_location_name,
    fetch_calendar_events
)
from services.gist_storage import (
    save_tokens,
    get_tokens,
    get_all_location_ids,
    get_calendar_id,
    get_location_data
    )
from services.oauth import (
    exchange_code_for_tokens,
    refresh_if_needed
)
from services.appts import (
    compute_time_range,
    extract_appointments
)


app = Flask(__name__)


@app.route("/")
@app.route("/menu", methods=["GET", "POST"])
def menu():
    title = ""
    appointments = None
    html = ""

    # Load all locations from Gist
    location_ids = get_all_location_ids()

    # Build list of {id, name}
    locations = []
    for loc_id in location_ids:
        loc_data = get_location_data(loc_id)
        locations.append({"id": loc_id, "name": loc_data["name"]})
    
    # Determine selected location
    selected_location = request.form.get("location_id") or locations[0]["id"]

    # Load tokens from Gist
    access_token, refresh_token = get_tokens(selected_location)

    # Load calendar_id
    calendar_id = get_calendar_id(selected_location)

    if request.method == "POST":
        option = request.form.get("option")
        date_input = request.form.get("date", "")

        # Determine date range
        if option == "1":
            title = "Appointments for Today"
            start, end = compute_time_range("today")

        elif option == "2":
            title = "Appointments for Tomorrow"
            start, end = compute_time_range("tomorrow")

        elif option == "3" and date_input:
            try:
                curr_year = datetime.now().year
                formatted_date = f"{curr_year}-{date_input}"
                datetime.strptime(formatted_date, "%Y-%m-%d")

                title = f"Appointments for {date_input}"
                start, end = compute_time_range("specific", formatted_date)

            except ValueError:
                return render_template(
                    "menu.html",
                    data="<p style='color:red;'>Invalid date format. Please use MM-DD.</p>",
                    curr_year=datetime.now().year,
                    title="Invalid Date"
                )

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

        # Handle expired token
        if response.status_code == 401:
            access_token = refresh_if_needed(selected_location)
            response = fetch_calendar_events(
                selected_location,
                calendar_id,
                access_token,
                start,
                end
            )

        # Extract clean appointment data
        appointments = extract_appointments(response.json())

        for i, desc in enumerate(appointments, start=1):
            html += f"{i}. {desc}<br><br>"
        

    return render_template(
        "menu.html",
        data=html,
        curr_year=datetime.now().year,
        title=title,
        locations=locations
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


if __name__ == '__main__':
    app.run(debug=True, port=5000)
