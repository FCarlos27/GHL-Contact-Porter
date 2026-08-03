"""Seed a test user and exercise the /api/auth endpoints via Flask's test client."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.supabase import supabase, get_user_by_email
from app import app

import utils.verification as verification

# Prevent real email delivery during tests; the code is read from the DB instead.
verification.send_verification_email = lambda to, code: print(f"[mock] emailed verification code {code} to {to}")

TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "testpass123"
TEST_GHL_USER_ID = "test-ghl-id"
TEST_FIRST_NAME = "Test"
TEST_LAST_NAME = "User"


def get_latest_verification_code(email):
    response = (
        supabase.table("email_verifications")
        .select("*")
        .eq("email", email)
        .eq("used", False)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    return response.data[0]["code"] if response.data else None


def seed_test_user():
    user = get_user_by_email(TEST_EMAIL)
    if not user:
        lookup = supabase.table("users").select("id").eq("ghl_user_id", TEST_GHL_USER_ID).limit(1).execute()
        if lookup.data:
            user = {"id": lookup.data[0]["id"]}

    if user:
        supabase.table("users").update({
            "email": TEST_EMAIL,
            "first_name": TEST_FIRST_NAME,
            "last_name": TEST_LAST_NAME,
            "is_agency_owner": False,
            "password_hash": None,
        }).eq("id", user["id"]).execute()
        print(f"[seed] reset existing user (id={user['id']})")
        return

    response = supabase.table("users").insert({
        "ghl_user_id": TEST_GHL_USER_ID,
        "email": TEST_EMAIL,
        "first_name": TEST_FIRST_NAME,
        "last_name": TEST_LAST_NAME,
        "is_agency_owner": False,
    }).execute()
    print(f"[seed] inserted user (id={response.data[0]['id']})")


def run_tests():
    client = app.test_client()
    passed = 0
    failed = 0

    def check(label, condition, detail=""):
        nonlocal passed, failed
        status = "PASS" if condition else "FAIL"
        if condition:
            passed += 1
        else:
            failed += 1
        print(f"[{status}] {label}{' - ' + detail if detail and not condition else ''}")

    # 1. check-email before registration -> needs_registration
    r = client.post("/api/auth/check-email", json={"email": TEST_EMAIL.upper()})
    check("check-email returns 200", r.status_code == 200, f"got {r.status_code}")
    check("check-email -> needs_registration", r.get_json().get("status") == "needs_registration", str(r.get_json()))

    # 2. register -> sends a verification code
    r = client.post("/api/auth/register", json={"email": TEST_EMAIL})
    body = r.get_json()
    check("register returns 200", r.status_code == 200, f"got {r.status_code}")
    check("register sends code (code_sent)", body.get("status") == "code_sent", str(body))

    code = get_latest_verification_code(TEST_EMAIL)
    check("verification code stored in DB", code is not None)

    # 3. register without a valid code -> 400
    r = client.post("/api/auth/verify-registration", json={"email": TEST_EMAIL, "code": "000000", "password": TEST_PASSWORD})
    check("verify-registration rejects bad code (400)", r.status_code == 400, f"got {r.status_code}")

    # 4. verify-registration with the emailed code -> registers + logs in
    r = client.post("/api/auth/verify-registration", json={"email": TEST_EMAIL, "code": code, "password": TEST_PASSWORD})
    body = r.get_json()
    check("verify-registration returns 200", r.status_code == 200, f"got {r.status_code}")
    check("verify-registration returns status=registered", body.get("status") == "registered", str(body))
    check("register logs user in (session)", client.get("/").status_code == 200)

    # 5. check-email after registration -> needs_password
    r = client.post("/api/auth/check-email", json={"email": TEST_EMAIL})
    check("check-email -> needs_password", r.get_json().get("status") == "needs_password", str(r.get_json()))

    # 6. login with correct password
    r = client.post("/api/auth/login", json={"email": TEST_EMAIL, "password": TEST_PASSWORD})
    body = r.get_json()
    check("login returns 200", r.status_code == 200, f"got {r.status_code}")
    check("login returns user email", body.get("user", {}).get("email") == TEST_EMAIL, str(body))
    check("login returns location_ids list", isinstance(body.get("location_ids"), list), str(body))

    # 7. login with wrong password -> 401
    r = client.post("/api/auth/login", json={"email": TEST_EMAIL, "password": "wrongpass"})
    check("login rejects wrong password (401)", r.status_code == 401, f"got {r.status_code}")

    # 8. register again -> 400 (already registered)
    r = client.post("/api/auth/register", json={"email": TEST_EMAIL})
    check("register rejects duplicate (400)", r.status_code == 400, f"got {r.status_code}")

    # 9. check-email for unknown user -> 403
    r = client.post("/api/auth/check-email", json={"email": "nobody@example.com"})
    check("check-email rejects unknown (403)", r.status_code == 403, f"got {r.status_code}")

    print(f"\n{passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    seed_test_user()
    ok = run_tests()
    sys.exit(0 if ok else 1)
