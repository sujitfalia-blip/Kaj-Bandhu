from flask import Flask, render_template, request, redirect, session
import sqlite3, os
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "sfworks123"

UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


# ================= DB =================

def get_db():
    return sqlite3.connect("database.db")


def init_db():
    conn = get_db()
    c = conn.cursor()

    # WORKERS
    c.execute("""
    CREATE TABLE IF NOT EXISTS workers(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        skill TEXT,
        location TEXT,
        phone TEXT,
        description TEXT,
        image TEXT
    )
    """)

    # USERS
    c.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT
    )
    """)

    # BOOKINGS
    c.execute("""
    CREATE TABLE IF NOT EXISTS bookings(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user TEXT,
        worker TEXT,
        phone TEXT,
        service TEXT,
        area TEXT,
        status TEXT DEFAULT 'Pending'
    )
    """)

    conn.commit()
    conn.close()


init_db()


# ================= AUTH =================

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"]
        password = generate_password_hash(request.form["password"])
        role = request.form["role"]

        conn = get_db()
        try:
            conn.execute("INSERT INTO users(username,password,role) VALUES (?,?,?)",
                         (username, password, role))
            conn.commit()
        except:
            return "User already exists"
        finally:
            conn.close()

        return redirect("/login")

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE username=?",
                            (username,)).fetchone()
        conn.close()

        if user and check_password_hash(user[2], password):
            session["user"] = username
            session["role"] = user[3]
            return redirect("/")

        return "Invalid login"

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# ================= HOME =================

@app.route("/", methods=["GET", "POST"])
def home():
    if "user" not in session:
        return redirect("/login")

    conn = get_db()
    c = conn.cursor()

    # ADD WORKER (admin only)
    if request.method == "POST" and session.get("role") == "admin":
        name = request.form["name"]
        skill = request.form["skill"]
        location = request.form["location"]
        phone = request.form["phone"]
        desc = request.form["description"]

        file = request.files.get("image")
        filename = ""

        if file and file.filename != "":
            filename = file.filename
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

        c.execute("""INSERT INTO workers(name,skill,location,phone,description,image)
                     VALUES (?,?,?,?,?,?)""",
                  (name, skill, location, phone, desc, filename))
        conn.commit()

    # SEARCH
    skill = request.args.get("skill", "")
    area = request.args.get("area", "")

    query = "SELECT * FROM workers WHERE 1=1"
    params = []

    if skill:
        query += " AND skill LIKE ?"
        params.append(f"%{skill}%")
    if area:
        query += " AND location LIKE ?"
        params.append(f"%{area}%")

    workers = c.execute(query, params).fetchall()

    logo = "logo.png" if os.path.exists("static/uploads/logo.png") else None

    conn.close()

    return render_template("index.html",
                           workers=workers,
                           logo=logo,
                           role=session.get("role"))


# ================= WORKER =================

@app.route("/delete/<int:id>")
def delete(id):
    if session.get("role") != "admin":
        return "Access Denied"

    conn = get_db()
    conn.execute("DELETE FROM workers WHERE id=?", (id,))
    conn.commit()
    conn.close()

    return redirect("/")


@app.route("/edit/<int:id>", methods=["GET", "POST"])
def edit(id):
    if session.get("role") != "admin":
        return "Access Denied"

    conn = get_db()
    c = conn.cursor()

    if request.method == "POST":
        name = request.form["name"]
        skill = request.form["skill"]
        location = request.form["location"]
        phone = request.form["phone"]
        desc = request.form["description"]

        file = request.files.get("image")

        if file and file.filename != "":
            filename = file.filename
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

            c.execute("""UPDATE workers 
                         SET name=?,skill=?,location=?,phone=?,description=?,image=? 
                         WHERE id=?""",
                      (name, skill, location, phone, desc, filename, id))
        else:
            c.execute("""UPDATE workers 
                         SET name=?,skill=?,location=?,phone=?,description=? 
                         WHERE id=?""",
                      (name, skill, location, phone, desc, id))

        conn.commit()
        conn.close()
        return redirect("/")

    worker = c.execute("SELECT * FROM workers WHERE id=?", (id,)).fetchone()
    conn.close()

    return render_template("edit.html", worker=worker)


# ================= LOGO =================

@app.route("/upload_logo", methods=["POST"])
def upload_logo():
    if session.get("role") != "admin":
        return "Access Denied"

    file = request.files.get("logo")
    if file:
        file.save(os.path.join(app.config["UPLOAD_FOLDER"], "logo.png"))

    return redirect("/")


# ================= BOOKING =================

@app.route("/book", methods=["POST"])
def book():
    if "user" not in session:
        return redirect("/login")

    user = session["user"]
    worker = request.form["worker"]
    phone = request.form["phone"]
    service = request.form["service"]
    area = request.form["area"]

    conn = get_db()
    conn.execute("""
    INSERT INTO bookings(user,worker,phone,service,area)
    VALUES (?,?,?,?,?)
    """, (user, worker, phone, service, area))

    conn.commit()
    conn.close()

    return redirect("/")


# ================= CHAT =================

@app.route("/chat")
def chat():
    name = request.args.get("w")
    phone = request.args.get("p")
    return render_template("chat.html", name=name, phone=phone)


# ================= ADMIN =================

@app.route("/admin")
def admin():
    if session.get("role") != "admin":
        return "Access Denied"

    conn = get_db()
    bookings = conn.execute("SELECT * FROM bookings").fetchall()
    conn.close()

    return render_template("admin.html", bookings=bookings)


@app.route("/approve/<int:id>")
def approve(id):
    if session.get("role") != "admin":
        return "Access Denied"

    conn = get_db()
    conn.execute("UPDATE bookings SET status='Approved' WHERE id=?", (id,))
    conn.commit()
    conn.close()

    return redirect("/admin")


@app.route("/reject/<int:id>")
def reject(id):
    if session.get("role") != "admin":
        return "Access Denied"

    conn = get_db()
    conn.execute("UPDATE bookings SET status='Rejected' WHERE id=?", (id,))
    conn.commit()
    conn.close()

    return redirect("/admin")


# ================= RUN =================

if __name__ == "__main__":
    app.run(debug=True)
    