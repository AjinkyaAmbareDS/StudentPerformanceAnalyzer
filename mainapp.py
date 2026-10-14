import os, sqlite3
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from werkzeug.security import generate_password_hash, check_password_hash
from ml_model import predict_risk, train_model

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "studentiq.db")
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("STUDENTIQ_SECRET_KEY", "change-this-secret-before-deployment")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con

def init_db():
    con = db()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS users(
      id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
      email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
      role TEXT NOT NULL CHECK(role IN ('student','teacher')),
      class_name TEXT NOT NULL DEFAULT 'FE - H',
      identifier TEXT NOT NULL DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS marks(
      id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER NOT NULL,
      subject TEXT NOT NULL, score REAL NOT NULL, maximum REAL NOT NULL DEFAULT 100,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS attendance(
      id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER NOT NULL UNIQUE,
      present INTEGER NOT NULL DEFAULT 0, total INTEGER NOT NULL DEFAULT 0,
      FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE
    );
    """)
    # Upgrade an existing local database created by an earlier version.
    user_columns = [row["name"] for row in con.execute("PRAGMA table_info(users)").fetchall()]
    if "identifier" not in user_columns:
        con.execute("ALTER TABLE users ADD COLUMN identifier TEXT NOT NULL DEFAULT ''")
    if con.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        people = [
          ("Aarav Sharma","student@vsecc.com","student123","student"),
          ("Priya Patil","priya@vsecc.com","student123","student"),
          ("Rohan Deshmukh","rohan@vsecc.com","student123","student"),
          ("Ananya Kulkarni","ananya@vsecc.com","student123","student"),
          ("Teacher Demo","teacher@vsecc.com","teacher123","teacher"),
        ]
        for name,email,password,role in people:
            con.execute("INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,?)",
                        (name,email,generate_password_hash(password),role))
        demo = {
          "Aarav Sharma":({"Mathematics":82,"Physics":74,"Programming":91,"Chemistry":68,"Electrical":79},42,48),
          "Priya Patil":({"Mathematics":92,"Physics":88,"Programming":95,"Chemistry":84,"Electrical":90},46,48),
          "Rohan Deshmukh":({"Mathematics":48,"Physics":55,"Programming":62,"Chemistry":51,"Electrical":46},31,48),
          "Ananya Kulkarni":({"Mathematics":71,"Physics":66,"Programming":78,"Chemistry":73,"Electrical":69},38,48),
        }
        for name,(subjects,present,total) in demo.items():
            sid=con.execute("SELECT id FROM users WHERE name=?",(name,)).fetchone()["id"]
            con.executemany("INSERT INTO marks(student_id,subject,score,maximum) VALUES(?,?,?,100)",
                            [(sid,sub,score) for sub,score in subjects.items()])
            con.execute("INSERT INTO attendance(student_id,present,total) VALUES(?,?,?)",(sid,present,total))
        con.commit()
    con.close()
    train_model()

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))

        # Recover gracefully if a session refers to a user no longer in the database.
        user = current_user()
        if user is None:
            session.clear()
            flash("Your session expired or the account was not found. Please log in again.", "error")
            return redirect(url_for("login"))

        return fn(*args, **kwargs)
    return wrapper

def current_user():
    if not session.get("user_id"): return None
    con=db()
    user=con.execute("SELECT id,name,email,role,class_name FROM users WHERE id=?",(session["user_id"],)).fetchone()
    con.close()
    return user

def student_stats(student_id):
    con = db()

    # Database se student ke saare assessment marks lena
    raw_marks = con.execute(
        """
        SELECT subject, score, maximum, created_at
        FROM marks
        WHERE student_id = ?
        ORDER BY subject, created_at
        """,
        (student_id,)
    ).fetchall()

    # Student ki attendance lena
    attendance = con.execute(
        "SELECT present, total FROM attendance WHERE student_id = ?",
        (student_id,)
    ).fetchone()

    con.close()

    # Same subject ke marks ko group karna
    grouped = {}

    for mark in raw_marks:
        subject = mark["subject"].strip()

        if not subject:
            subject = "Unspecified subject"

        maximum = float(mark["maximum"] or 0)

        if maximum <= 0:
            continue

        percentage = float(mark["score"]) / maximum * 100

        if subject not in grouped:
            grouped[subject] = []

        grouped[subject].append(percentage)

    # Har subject ka average calculate karna
    marks = []

    for subject in sorted(grouped, key=str.casefold):
        scores = grouped[subject]

        average = round(sum(scores) / len(scores), 1)

        marks.append({
            "subject": subject,
            "score": average,
            "maximum": 100.0,
            "percentage": average,
            "assessment_count": len(scores)
        })

    # Overall average: har subject ko equal weight
    percentages = [m["percentage"] for m in marks]

    avg = (
        round(sum(percentages) / len(percentages), 1)
        if percentages else 0
    )

    # Attendance percentage calculate karna
    present = attendance["present"] if attendance else 0
    total = attendance["total"] if attendance else 0

    att = round(present / total * 100, 1) if total else 0

    # Machine-learning risk prediction
    prediction = predict_risk(avg, att, len(raw_marks))

    # 60% se kam average wale subjects
    weak = [
        m["subject"]
        for m in marks
        if m["percentage"] < 60
    ]

    return {
        "marks": marks,
        "avg": avg,
        "att": att,
        "present": present,
        "total": total,
        "risk": prediction["risk"],
        "probability": prediction["probability"],
        "model_note": prediction["model_note"],
        "weak": weak,
        "assessment_count": len(raw_marks)
    }

def index():
    return redirect(url_for("dashboard") if session.get("user_id") else url_for("login"))

@app.route("/login",methods=["GET","POST"])
def login():
    if request.method=="POST":
        email=request.form.get("email","").strip().lower()
        password=request.form.get("password","")
        con=db()
        u=con.execute("SELECT * FROM users WHERE lower(email)=?",(email,)).fetchone()
        con.close()
        if u and check_password_hash(u["password_hash"],password):
            session.clear()
            session["user_id"]=u["id"]
            session["role"]=u["role"]
            return redirect(url_for("dashboard"))
        flash("Email or password is incorrect.","error")
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        role = request.form.get("role", "").strip().lower()
        identifier = request.form.get("identifier", "").strip()
        class_name = request.form.get("class_name", "FE - H").strip() or "FE - H"

        error = None
        if len(name) < 2 or len(name) > 80:
            error = "Please enter your full name."
        elif "@" not in email or len(email) > 160:
            error = "Please enter a valid email address."
        elif len(password) < 8:
            error = "Password must be at least 8 characters long."
        elif password != confirm:
            error = "Passwords do not match."
        elif role not in ("student", "teacher"):
            error = "Please choose Student or Teacher."
        elif not identifier or len(identifier) > 40:
            error = "Please enter your roll number or teacher/staff ID."

        if error:
            return render_template("register.html", error=error, form=request.form)

        con = db()
        try:
            con.execute(
                "INSERT INTO users(name,email,password_hash,role,class_name,identifier) VALUES(?,?,?,?,?,?)",
                (name, email, generate_password_hash(password), role, class_name, identifier)
            )
            con.commit()
            new_user = con.execute("SELECT id,role FROM users WHERE lower(email)=?", (email,)).fetchone()
        except sqlite3.IntegrityError:
            con.close()
            return render_template("register.html", error="An account with this email already exists. Please log in.", form=request.form)
        con.close()
        session.clear()
        session["user_id"] = new_user["id"]
        session["role"] = new_user["role"]
        flash("Account created successfully. Welcome to StudentIQ!", "success")
        return redirect(url_for("dashboard"))
    return render_template("register.html", error=None, form={})

@app.route("/add-student", methods=["POST"])
@login_required
def add_student():
    # Only a logged-in teacher can create student accounts.
    if session.get("role") != "teacher":
        abort(403)

    name = request.form.get("name", "").strip()
    identifier = request.form.get("identifier", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    class_name = request.form.get("class_name", "FE - H").strip() or "FE - H"

    if not name or len(name) > 80 or not identifier or len(identifier) > 40:
        flash("Enter a valid student name and roll number.", "error")
        return redirect(url_for("dashboard"))
    if not email or "@" not in email or len(email) > 160:
        flash("Enter a valid student email.", "error")
        return redirect(url_for("dashboard"))
    if len(password) < 8:
        flash("Password must be at least 8 characters.", "error")
        return redirect(url_for("dashboard"))

    con = db()
    try:
        # Prevent duplicate student roll numbers within the same class.
        duplicate = con.execute(
            "SELECT id FROM users WHERE role='student' AND lower(identifier)=lower(?) AND lower(class_name)=lower(?)",
            (identifier, class_name)
        ).fetchone()
        if duplicate:
            flash("That roll number already exists in this class.", "error")
            return redirect(url_for("dashboard"))

        con.execute(
            """INSERT INTO users(name,email,password_hash,role,class_name,identifier)
               VALUES(?,?,?,'student',?,?)""",
            (name, email, generate_password_hash(password), class_name, identifier)
        )
        con.commit()
        flash("Student account created successfully. Share the login details securely.", "success")
    except sqlite3.IntegrityError:
        con.rollback()
        flash("An account with this email already exists.", "error")
    finally:
        con.close()

    return redirect(url_for("dashboard"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/dashboard")
@login_required
def dashboard():
    u=current_user()
    if u is None:
        session.clear()
        flash("Please log in again to continue.", "error")
        return redirect(url_for("login"))
    if u["role"]=="teacher":
        con=db()
        students=con.execute("SELECT id,name,email,class_name FROM users WHERE role='student' ORDER BY name").fetchall()
        con.close()
        rows=[{"student":s,"stats":student_stats(s["id"])} for s in students]
        class_avg=round(sum(x["stats"]["avg"] for x in rows)/len(rows),1) if rows else 0
        class_att=round(sum(x["stats"]["att"] for x in rows)/len(rows),1) if rows else 0
        high=sum(x["stats"]["risk"]=="High" for x in rows)
        return render_template("teacher.html",user=u,rows=rows,class_avg=class_avg,class_att=class_att,high=high)
    stats=student_stats(u["id"])
    return render_template("student.html",user=u,stats=stats)

@app.route("/student/<int:sid>")
@login_required
def student_report(sid):
    if session.get("role")!="teacher": abort(403)
    con=db()
    s=con.execute("SELECT id,name,email,class_name FROM users WHERE id=? AND role='student'",(sid,)).fetchone()
    con.close()
    if not s: abort(404)
    return render_template("report.html",user=current_user(),student=s,stats=student_stats(sid),own=False)

@app.route("/report")
@login_required
def my_report():
    u=current_user()
    if u["role"]!="student": return redirect(url_for("dashboard"))
    return render_template("report.html",user=u,student=u,stats=student_stats(u["id"]),own=True)

@app.route("/add-mark",methods=["POST"])
@login_required
def add_mark():
    if session.get("role")!="teacher": abort(403)
    try:
        sid=int(request.form["student_id"])
        subject=request.form["subject"].strip()
        score=float(request.form["score"])
        maximum=float(request.form.get("maximum",100))
        if not subject or len(subject)>80 or maximum<=0 or score<0 or score>maximum:
            raise ValueError
        con=db()
        valid=con.execute("SELECT id FROM users WHERE id=? AND role='student'",(sid,)).fetchone()
        if not valid: raise ValueError
        # Add a new assessment row; the dashboard averages all recorded assessments per subject.
        con.execute("INSERT INTO marks(student_id,subject,score,maximum) VALUES(?,?,?,?)",(sid,subject,score,maximum))
        con.commit(); con.close()
        flash("Assessment result saved to the database.","success")
    except (ValueError,KeyError):
        flash("Please enter valid student, subject and marks.","error")
    return redirect(url_for("dashboard"))

@app.route("/attendance",methods=["POST"])
@login_required
def update_attendance():
    if session.get("role")!="teacher": abort(403)
    try:
        sid=int(request.form["student_id"]); present=int(request.form["present"]); total=int(request.form["total"])
        if total<1 or present<0 or present>total: raise ValueError
        con=db()
        con.execute("""INSERT INTO attendance(student_id,present,total) VALUES(?,?,?)
          ON CONFLICT(student_id) DO UPDATE SET present=excluded.present,total=excluded.total""",(sid,present,total))
        con.commit(); con.close()
        flash("Attendance saved to the database.","success")
    except (ValueError,KeyError):
        flash("Enter valid attendance numbers (present cannot exceed total).","error")
    return redirect(url_for("dashboard"))

@app.errorhandler(403)
def forbidden(e): return render_template("error.html",code=403,message="You don't have permission to open this page.",user=current_user()),403
@app.errorhandler(404)
def missing(e): return render_template("error.html",code=404,message="That page or student record was not found.",user=current_user()),404

if __name__=="__main__":
    init_db()
    app.run(host="127.0.0.1",port=5000,debug=False)
    
