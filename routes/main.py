from datetime import datetime

from flask import Blueprint, request, render_template, redirect, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

from services.supabase import (
    get_all_locations_name_id,
    get_location_data,
    token_is_stale,
    get_user_by_email,
    set_user_password,
)
from services.oauth import refresh_if_needed
from services.ghl_api import fetch_calendar_events
from services.appts_format import create_appointments_html
from utils.formatting import compute_time_range
from utils.verification import issue_verification_code
from services.supabase import (
    get_all_locations_name_id,
    get_location_data,
    token_is_stale,
    get_user_by_email,
    set_user_password,
    get_valid_verification_code,
    mark_verification_used,
)
from routes.common import session_required, login_required

main_bp = Blueprint("main", __name__)


@main_bp.route("/login", methods=["GET", "POST"])
def login_page():
    if request.method == "POST":
        email = (request.form.get("email") or "").lower().strip()
        password = request.form.get("password") or ""

        user = get_user_by_email(email)
        if (
            not user
            or user.get("is_deleted")
            or not user.get("password_hash")
            or not check_password_hash(user["password_hash"], password)
        ):
            flash("Invalid credentials", "danger")
            return redirect("/login")

        session["user_id"] = user["id"]
        session["email"] = user["email"]
        session["is_agency_owner"] = user["is_agency_owner"]
        return redirect("/")

    return render_template("login.html")


@main_bp.route("/register", methods=["GET", "POST"])
def register_page():
    if request.method == "POST":
        email = (request.form.get("email") or "").lower().strip()

        user = get_user_by_email(email)
        if not user or user.get("is_deleted"):
            flash("User not authorized for this dashboard", "danger")
            return redirect("/register")

        if user.get("password_hash"):
            flash("User is already registered", "warning")
            return redirect("/login")

        issue_verification_code(email)
        flash(f"Verification code sent to {email}", "success")
        return redirect("/register/verify")

    return render_template("register.html")


@main_bp.route("/register/verify", methods=["GET", "POST"])
def register_verify():
    if request.method == "POST":
        email = (request.form.get("email") or "").lower().strip()
        code = (request.form.get("code") or "").strip()
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm_password") or ""

        user = get_user_by_email(email)
        if not user or user.get("is_deleted"):
            flash("User not authorized for this dashboard", "danger")
            return redirect("/register")

        if password != confirm or not password:
            flash("Passwords do not match", "danger")
            return redirect("/register/verify")

        verification = get_valid_verification_code(email, code)
        if not verification:
            flash("Invalid or expired verification code", "danger")
            return redirect("/register/verify")

        set_user_password(user["id"], generate_password_hash(password))
        mark_verification_used(verification["id"])

        session["user_id"] = user["id"]
        session["email"] = user["email"]
        session["is_agency_owner"] = user["is_agency_owner"]
        flash("Registration complete. You are now logged in.", "success")
        return redirect("/")

    return render_template("register_verify.html")


@main_bp.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect("/login")


@main_bp.route("/", methods=["GET", "POST"])
@login_required
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


@main_bp.route("/menu", methods=["GET", "POST"])
@login_required
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
