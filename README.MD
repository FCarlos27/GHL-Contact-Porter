# GHL to Google Sheets: Automated Contact Porter

A Python/Flask web app that synchronizes **GoHighLevel (GHL)** appointment data with **Google Sheets**, backed by **Supabase** for state and authentication. The app handles GHL OAuth installation, syncs users, then lets a logged-in sales team push confirmed/showed appointments into a shared Google Sheet — grouped by date to avoid duplicates.

> Less manual data entry — next-day appointment lists for the sales team are built automatically.

## Key Features

- **GHL OAuth Installation** — Install the app on a single location or company/agency level. The callback exchanges the code, stores tokens, and syncs all GHL users into the database.
- **User Sync (`/users/search`)** — On install, every GHL user is imported. Agency owners are flagged and granted access to all locations; others get their assigned locations.
- **Authentication** — Login + registration with **email-verified one-time codes** (Resend). A user cannot claim an account by guessing an email, because registration requires ownership of the inbox.
- **Smart Note Parsing** — Extracts customer name, phone, and booking info directly from GHL appointment notes, so only the Calendar Events endpoint is needed.
- **Duplicate-Safe Sheet Insert** — Inserts contacts grouped by appointment date, skipping phone numbers already in the sheet.
- **Timezone-Aware** — Handles day and month synchronization across business hours.
- **Self-Service Sheet Linking** — First time using a location, the app prompts for a Google Sheets link, extracts the spreadsheet ID, and saves it for that location.

## Tech Stack

- **Backend:** Python 3.13, Flask (blueprint-based)
- **Database:** Supabase (PostgreSQL)
- **Email:** Resend API
- **APIs:** GoHighLevel (GHL) OAuth 2.0, Google Sheets API v4
- **Frontend:** HTML5, CSS3 (server-rendered Jinja templates)

## Project Structure

```
app.py                  Flask entry point (registers blueprints)
routes/                 Route handlers, split by concern (auth, main, oauth, contacts, common)
services/               Integration & business logic (ghl_api, oauth, supabase, sheets_api,
                        ghl_user_sync, email, appts_format)
utils/helpers.py        Shared helpers (date/phone formatting, verification codes, sheet-ID parsing)
migrations/             SQL migrations to run in the Supabase SQL editor
templates/              Jinja templates
scripts/                Utilities, e.g. seed_auth_test.py (auth smoke test)
```

## Prerequisites

- Python 3.13+
- A **GoHighLevel** account (Developer / Agency plan for company-level installs)
- A **Supabase** project
- A **Google Cloud** project with the Sheets & Drive APIs enabled
- A **Resend** account (for verification emails)

## Installation

### 1. Clone & set up the virtual environment

```bash
git clone https://github.com/FCarlos27/GHL-Contact-Porter
cd GHL-Contact-Porter
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure `.env`

Create a `.env` file in the project root:

```env
# Flask
FLASK_SECRET_KEY=change-me-to-a-long-random-string

# GoHighLevel OAuth
CLIENT_ID=your-ghl-app-client-id
CLIENT_SECRET=your-ghl-app-client-secret
REDIRECT_URI=https://your-domain.com/oauth/callback
TOKEN_URL=https://services.leadconnectorhq.com/oauth/token

# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-service-role-key

# Resend
RESEND_API_KEY=re_your-resend-key
EMAIL_FROM="GHL Dashboard <you@your-domain.com>"

# Google Sheets service account (base64 of the JSON key)
GOOGLE_CREDENTIALS_JSON_B64=...
```

> **`GOOGLE_CREDENTIALS_JSON_B64`** is the Google service-account JSON encoded as base64 (see *Google Sheets Setup* below). For example:
> ```bash
> python3 -c "import base64,json; open('GOOGLE_CREDENTIALS_JSON_B64.txt','w').write(base64.b64encode(open('credentials.json','rb').read()).decode())"
> ```

### 3. Create the database tables

In the **Supabase SQL editor**, run the migrations in order:

1. `migrations/001_create_users_tables.sql` — creates `users` and `user_locations`
2. `migrations/002_create_email_verifications.sql` — creates `email_verifications`

Also create the core `locations` table if it doesn't exist:

```sql
CREATE TABLE IF NOT EXISTS locations (
    location_id TEXT PRIMARY KEY,
    name TEXT,
    access_token TEXT,
    refresh_token TEXT,
    calendar_id TEXT,
    sheet_id TEXT,
    companyId TEXT,
    userId TEXT,
    last_refresh TIMESTAMPTZ
);
```

### 4. GoHighLevel app setup

- Create a **Marketplace / Private app** in GHL.
- Request scopes. Minimum for this app:
  - `calendars.readonly`, `calendars/events.readonly`
  - `users.readonly` (to sync users on install)
  - `locations.readonly` (company-level installs)
  - `oauth.write`, `oauth.readonly`
- Set the redirect URI to `your-domain.com/oauth/callback`.
- Run the app and visit `/oauth/callback` (or the marketplace install link) to install it.

### 5. Google Sheets setup

- In **Google Cloud Console**, enable the **Google Sheets API** and **Google Drive API**.
- Create a **Service Account** and download its JSON key.
- **Crucial:** share your spreadsheet with the service account's `client_email` from that JSON, granting **Editor** access.
- Base64-encode that JSON and put it in `GOOGLE_CREDENTIALS_JSON_B64`.
- Starter guide: https://www.youtube.com/watch?v=zCEJurLGFRk

### 6. Run the app

```bash
python3 app.py
```

The app listens on `http://0.0.0.0:5000`. For production, run behind a reverse proxy (e.g. nginx/caddy) with HTTPS, and use a tunnel like `cloudflared` if you just need a public URL for testing the OAuth callback.

## First-time workflow

1. **Install** — authorize the GHL app. The callback stores tokens and syncs your GHL users.
2. **(Optional) Sync users manually** — if users are added later, call `sync_ghl_users(payload)` with the `/users/search` payload, or re-run the install callback.
3. **Register** — go to `/register`, enter your GHL provisioned email, enter the emailed one-time code, and set a password.
4. **Log in** — `/login`.
5. **Select a location** — `/` shows the locations you have access to.
6. **Link a Google Sheet** — if a location has no sheet yet, the app redirects you to paste a Sheets link (its ID is stored automatically).
7. **Push contacts** — from `/menu`, choose *update sheet by appointment date* or *update sheet with all month appointments*.

## Install types: single‑location vs. company/agency

How the `/oauth/callback` behaves depends on which install your GHL app is configured for. The callback determines the install type from the token response's `locationId`:

### Single-location install (a `locationId` is present)

The app was installed on a specific sub-account. On install, the callback:

1. Exchanges the code for `accessToken` / `refreshToken` / `companyId` / `userId`.
2. Saves the tokens for that one `location_id`.
3. Fetches and stores the location's name.
4. Calls `/users/search` for **that location** and imports its users into `users`.

Result message: `App installed successfully for location: <id> (<n> users synced)`.

### Company / agency install (no `locationId`)

The app was installed at the agency/company level, so no single location is returned by the token exchange. The callback:

1. Exchanges the code for tokens (company-level access).
2. Calls `GET /locations/search` to list **every** accessible location and saves tokens + names for each one into the `locations` table.
3. Calls `/users/search` at the **company level** and imports all users.

Result message: `App installed successfully for <n> locations. (<m> users synced)`.

### How access is assigned during user sync

When users are imported, `sync_ghl_users` decides each user's location access:

- If `isAgencyOwner` is `true` (or a user has no `roles.locationIds`), the user is treated as an **agency owner** and gets access to **all locations** in the `locations` table.
- Otherwise, the user gets exactly the locations listed in `roles.locationIds`.

These mappings live in the `user_locations` junction table and drive which locations each logged-in user may select on `/`.

> **Tip:** because agency owners are granted access from the `locations` table at sync time, run a sync *after* a company-level install so all freshly saved locations are granted.

## Things to Keep in Mind

- **Emails must be pre-provisioned.** Only users synced from GHL can register. If a user isn't in the `users` table, `/register` returns a 403.
- **Registering an email requires inbox access.** The one-time code is sent to the address, so an outsider who guesses an email *cannot* claim the account.
- **Resend sender verification.** The default `onboarding@resend.dev` only works from your account until you verify your sending domain. Set `EMAIL_FROM` to a verified sender.
- **Service role key** (`SUPABASE_KEY`): treat it as a secret — it bypasses Row Level Security.
- **Sheet ownership.** The app writes to a sheet only if it was shared with the service-account email with **Editor** access; otherwise inserts fail with a permission error.
- **Note parsing depends on your notes format.** Extraction assumes the customer **name** and **phone** appear in the appointment description (e.g. a `NEW APPOINTMENT` block). Different GHL note templates may need the parser tuned in `services/appts_format.py`.
- **`users.readonly` scope is required** during installation, otherwise the user sync (`/users/search`) will fail and disrupt the callback.
- **Agency vs location installs.** On a company/agency install every accessible location is saved and synced; on a single-location install, only that location (see the *Install types* section above).
- **KPI block (columns K–P)** is snapshotted and restored around sheet inserts, so formulas there are preserved.

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you'd like to change.

## License

[MIT](LICENSE)