# StudentIQ — Student Performance Analyzer (Full Stack)

## What is included
- **Backend:** Python Flask routes and server-side session handling.
- **Database:** SQLite database (`studentiq.db`) created automatically on first launch.
- **Authentication:** Passwords stored as Werkzeug password hashes, not plain text.
- **Account creation:** Signup lets a user choose Student or Teacher and enter a roll number / staff ID.
- **Student dashboard:** Subject marks, average, attendance, report and suggestions.
- **Teacher dashboard:** Class summary, risk indicators, add marks and update attendance.
- **Machine learning:** scikit-learn Random Forest classifier in `ml_model.py`.
- **Local demo data:** four sample students and one teacher, created on first launch.

## Run on Windows
1. Install Python 3.10+ from https://www.python.org/downloads/. During setup, enable **Add Python to PATH**.
2. Extract this ZIP to a normal folder.
3. Double-click `run_windows.bat`. First run installs the required Python packages and may take a few minutes.
4. Your browser opens at http://127.0.0.1:5000.
5. To stop, close the command prompt window. To start again, double-click `run_windows.bat`.

## Run in VS Code terminal
Open this folder in VS Code, then run:
```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# Install dependencies:
pip install -r requirements.txt
python app.py
```
Open http://127.0.0.1:5000.

## Account creation
Open the login page and select **Create an account**. Choose Student or Teacher, then enter the matching roll number or staff ID, email, class (students), and password. In this prototype teacher sign-up is open; require college approval/invite codes before public use.

## Demo accounts
- Student: `student@vsecc.com` / `student123`
- Teacher: `teacher@vsecc.com` / `teacher123`
- Additional student records: `priya@vsecc.com`, `rohan@vsecc.com`, `ananya@vsecc.com`, each with password `student123`.

## How the ML feature works
The Random Forest model uses average marks, attendance percentage, and number of recorded assessments to estimate Low / Medium / High risk. It is trained on **synthetic illustrative data**, not real student records. It is an academic prototype and should not be used for consequential decisions until validated on appropriate real-world data. The displayed probability is model confidence, not a guarantee.

## Important security / deployment notes
This is a local college-project starter, not production-ready. Before public deployment:
- Set a long random `STUDENTIQ_SECRET_KEY` environment variable.
- Add CSRF protection, rate limiting, password reset, HTTPS, secure cookies, and authorization tests.
- Add consent and access controls for educational records.
- Back up the SQLite database or move to managed PostgreSQL for multi-user hosted deployment.
- Validate the model with representative, consented data and monitor bias and errors.

SQLite stores data on the computer running the server. Other devices cannot share this local database unless the app is hosted and configured for shared access.


## Teacher: add a student
Log in as teacher, use the **Add New Student** form, and enter the student's name, roll number, email, class/division, and a temporary password (at least 8 characters). The student account is saved in SQLite. The student can then log in with those credentials. Teacher accounts are required; student users cannot submit this form.
