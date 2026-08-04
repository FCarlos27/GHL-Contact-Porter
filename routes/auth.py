from flask import Blueprint, request, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash

from services.supabase import (
    get_user_by_email,
    get_allowed_location_ids,
    set_user_password,
    get_valid_verification_code,
    mark_verification_used,
)
from utils.helpers import issue_verification_code

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def _user_profile(user):
    return {
        "id": user["id"],
        "ghl_user_id": user.get("ghl_user_id"),
        "email": user.get("email"),
        "first_name": user.get("first_name"),
        "last_name": user.get("last_name"),
        "is_agency_owner": user.get("is_agency_owner"),
    }


def _normalize_email(payload):
    return (payload.get("email") or "").lower().strip()


@auth_bp.route("/check-email", methods=["POST"])
def check_email():
    data = request.get_json(silent=True) or {}
    email = _normalize_email(data)
    if not email:
        return jsonify({"error": "Email is required"}), 400

    user = get_user_by_email(email)
    if not user or user.get("is_deleted"):
        return jsonify({"error": "User not authorized for this dashboard"}), 403

    if not user.get("password_hash"):
        return jsonify({"status": "needs_registration"})
    return jsonify({"status": "needs_password"})


@auth_bp.route("/register", methods=["POST"])
def register():
    """Step 1: email the user a one-time verification code."""
    data = request.get_json(silent=True) or {}
    email = _normalize_email(data)
    if not email:
        return jsonify({"error": "Email is required"}), 400

    user = get_user_by_email(email)
    if not user or user.get("is_deleted"):
        return jsonify({"error": "User not authorized for this dashboard"}), 403

    if user.get("password_hash"):
        return jsonify({"error": "User is already registered"}), 400

    issue_verification_code(email)
    return jsonify({"status": "code_sent"})


@auth_bp.route("/verify-registration", methods=["POST"])
def verify_registration():
    """Step 2: confirm the emailed code, set the password, and log in."""
    data = request.get_json(silent=True) or {}
    email = _normalize_email(data)
    code = (data.get("code") or "").strip()
    password = data.get("password") or ""

    if not email or not code or not password:
        return jsonify({"error": "Email, code, and password are required"}), 400

    user = get_user_by_email(email)
    if not user or user.get("is_deleted"):
        return jsonify({"error": "User not authorized for this dashboard"}), 403

    if user.get("password_hash"):
        return jsonify({"error": "User is already registered"}), 400

    verification = get_valid_verification_code(email, code)
    if not verification:
        return jsonify({"error": "Invalid or expired verification code"}), 400

    set_user_password(user["id"], generate_password_hash(password))
    mark_verification_used(verification["id"])

    session["user_id"] = user["id"]
    session["email"] = user["email"]
    session["is_agency_owner"] = user["is_agency_owner"]

    return jsonify({"status": "registered", "user": _user_profile(user)})


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email = _normalize_email(data)
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    user = get_user_by_email(email)
    if not user or user.get("is_deleted") or not user.get("password_hash"):
        return jsonify({"error": "Invalid credentials"}), 401

    if not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "Invalid credentials"}), 401

    location_ids = get_allowed_location_ids(user)

    session["user_id"] = user["id"]
    session["email"] = user["email"]
    session["is_agency_owner"] = user["is_agency_owner"]

    return jsonify({
        "user": _user_profile(user),
        "location_ids": location_ids,
    })
