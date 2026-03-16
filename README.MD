# GHL to Google Sheets: Automated Contact Porter

A performance-optimized Python/Flask utility that synchronizes GoHighLevel (GHL) appointment data with Google Sheets. This tool leverages custom string parsing and Supabase state management to streamline sales workflows.

## Impact & Why I Built It

In my current workflow, manual contact insertion and end-of-shift reporting were major bottlenecks. I developed this tool to automate the creation of next-day appointment lists for the sales team.
* **Efficiency Gain:** Reduced manual data entry time by **60% - 70%**.
* **Streamlined Operations:** Shift handovers are now automated, ensuring the sales team has accurate data immediately.

## Key Features

- **Smart Note Parsing:** High-speed data extraction by parsing contact details (Name/Phone) directly from GHL Appointment Notes.
- **API Optimization:** Reduces total API overhead by eliminating redundant calls to the GHL Contacts endpoint.
- **Distributed State:** Utilizes **Supabase (PostgreSQL)** for secure, cloud-hosted OAuth token and metadata storage, allowing the app to run seamlessly across different environments.
- **Time-Zone Integrity:** Built to handle synchronization for different business hours.

## Tech Stack

- **Backend:** Python 3.13.4, Flask
- **Database:** Supabase (PostgreSQL)
- **APIs:** GoHighLevel (GHL) OAuth 2.0, Google Sheets API v4
- **Frontend:** HTML5, CSS3 (Vanilla Stack)

## Considerations
By leveraging specific company appointment formatting, the program only needs to hit a single GHL endpoint (Calendar Events). 
* **Note:** This optimization assumes contact info exists in the appt description. A fallback version utilizing the GHL Contacts API is available upon request for different organizational structures.

## Setup & Installation

1. **Clone the Repo:**
   ```bash
   git clone [https://github.com/FCarlos27/GHL-Contact-Porter]
   cd ghl-sheets-porter

2. **Install Dependencies:**
    pip install -r requirements.txt

3. **Configure Environment:**
    Create a .env file in the root directory with CLIENT_ID, CLIENT_SECRET, REDIRECT_URI, TOKEN_URL, FLASK_SECRET_KEY

4. **Initialize Database:**
    Create a .env file in the root directory:
    CREATE TABLE locations (
    location_id TEXT PRIMARY KEY,
    name TEXT,
    access_token TEXT,
    refresh_token TEXT,
    calendar_id TEXT,
    sheet_id TEXT,
    last_refresh TIMESTAMPTZ
);

5. **GHL App Setup:**
    -Create a GHL Marketplace App with calendars.readonly scopes.
    -Set redirect URI to your-domain.com/oauth/callback.
    -Install the app on the desired sub-location.

6. **Google Sheets API Setup:**
    -Go to the Google Cloud Console.
    -Enable the Google Sheets API and Google Drive API.
    -Create a Service Account and download the JSON credentials file.
    -Crucial: Share your Google Sheet with the client_email found inside that JSON file (giving it "Editor" access).
    -Follow this guide if you haven't created a Service Account before: https://www.youtube.com/watch?v=zCEJurLGFRk
    
7. **Run the App:**
    python app.py

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

## License 

[MIT](LICENSE)
