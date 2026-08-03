from functools import wraps

from flask import session, flash, redirect

from utils.formatting import build_timezone_map

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


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "info")
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function
