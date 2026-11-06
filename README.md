# VERIDA Website – Local MVP

## Features
- Student signup/login with hashed passwords
- Report lost/found items and upload photos
- Search and browse open reports
- Simple text similarity suggestions
- Claim requests
- Student dashboard
- Admin dashboard for item and claim status

**Important:** Matching is basic text similarity, not trained AI or image recognition.

## Run on Windows
1. Install Python 3.10+ and VS Code.
2. Extract this ZIP and open the `VERIDA_website` folder in VS Code.
3. Open Terminal and run:

```bash
py -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

4. Initialize the database/admin:

```powershell
$env:VERIDA_ADMIN_EMAIL="admin@verida.local"
$env:VERIDA_ADMIN_PASSWORD="SetYourOwnPassword123!"
flask --app app init-db
```

5. Start the website:

```bash
python app.py
```

6. Open http://127.0.0.1:5000

Admin login uses the email/password set in step 4. If you skip it, the demo defaults are `admin@verida.local` / `ChangeMe123!`; change these immediately.

## Before public deployment
This is a student MVP, not production-ready. Add CSRF protection, email verification, rate limiting, HTTPS, secure file-content validation, private persistent file storage, backups, privacy notices, and a production database. Replace the Flask secret key and never publish demo credentials.
