import os
import re
import uuid
import secrets
import sqlite3
from functools import wraps

from flask import (
    Flask, request, redirect, session, url_for,
    render_template_string, flash, abort
)
from markupsafe import escape
from werkzeug.security import generate_password_hash, check_password_hash

# -------------------- APP SETTINGS --------------------

app = Flask(__name__)

# In production set SECRET_KEY as an environment variable (e.g. on Railway).
# If it is missing, a random key is used (users must log in again after restart).
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)

app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
# Set COOKIE_SECURE=1 when the site runs on https.
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("COOKIE_SECURE") == "1"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# On Railway, point DATABASE_PATH / UPLOAD_DIR to a mounted volume so data is not lost.
DATABASE = os.environ.get("DATABASE_PATH", os.path.join(BASE_DIR, "andbuild.db"))
UPLOAD_FOLDER = os.environ.get("UPLOAD_DIR", os.path.join(BASE_DIR, "static", "uploads"))
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 3 * 1024 * 1024

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}

CATEGORIES = [
    "Construction Materials",
    "Machinery for Sale",
    "Machinery for Rent",
    "Professionals",
    "Construction Companies",
    "Construction Jobs",
    "Tenders and Projects",
]

ROLES = [
    "Buyer",
    "Seller",
    "Professional",
    "Machinery Owner",
    "Construction Company",
    "Contractor",
    "Job Seeker",
]


# -------------------- DATABASE --------------------

def database():
    con = sqlite3.connect(DATABASE)
    con.row_factory = sqlite3.Row
    return con


def add_missing_columns(con, table, additions):
    existing = {
        row["name"] for row in con.execute(f"PRAGMA table_info({table})").fetchall()
    }
    for column, definition in additions.items():
        if column not in existing:
            con.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_db():
    con = database()

    con.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            phone TEXT
        )
    """)

    con.execute("""
        CREATE TABLE IF NOT EXISTS listings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            price TEXT,
            location TEXT,
            phone TEXT,
            owner TEXT
        )
    """)

    # Add new columns to existing tables without deleting data.
    add_missing_columns(con, "users", {
        "role": "TEXT DEFAULT 'Buyer'",
        "city": "TEXT DEFAULT ''",
        "company": "TEXT DEFAULT ''",
        "bio": "TEXT DEFAULT ''",
        "photo": "TEXT DEFAULT ''",
        "status": "TEXT DEFAULT 'Active'",
    })
    add_missing_columns(con, "listings", {
        "owner_id": "INTEGER",
    })

    con.commit()
    con.close()


init_db()


# -------------------- SECURITY HELPERS --------------------

def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    return session["csrf"]


@app.before_request
def check_csrf():
    if request.method == "POST":
        sent = request.form.get("csrf_token", "")
        saved = session.get("csrf", "")
        if not sent or not saved or not secrets.compare_digest(sent, saved):
            abort(400)


@app.errorhandler(413)
def file_too_large(error):
    flash("Image is too large (max 3 MB). / ፎቶው በጣም ትልቅ ነው (ከ3MB አይበልጥ)።")
    return redirect(url_for("profile") if "user_id" in session else url_for("home"))


# -------------------- COMMON PAGE DESIGN --------------------

PAGE = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ title }} - AND BUILD ETHIOPIA</title>
<style>
* { box-sizing: border-box; }
body {
    margin: 0; font-family: Arial, sans-serif;
    background: #f3f5f7; color: #202733;
}
header {
    background: #123b32; color: white;
    padding: 18px 14px; text-align: center;
}
header h1 { margin: 0; font-size: 25px; }
header p { margin: 7px 0 0; }
nav {
    background: #0b2923; padding: 12px;
    display: flex; justify-content: center;
    flex-wrap: wrap; gap: 14px;
}
nav a { color: white; text-decoration: none; font-weight: bold; }
nav a:hover { text-decoration: underline; }
main { max-width: 950px; margin: 22px auto; padding: 0 12px; }
.card, .formbox {
    background: white; padding: 18px; margin-bottom: 15px;
    border-radius: 10px; box-shadow: 0 2px 8px #00000012;
}
.grid {
    display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
    gap: 12px;
}
input, textarea, select {
    display: block; width: 100%; padding: 11px;
    margin: 7px 0 14px; border: 1px solid #cbd2d9;
    border-radius: 6px; font-size: 16px; background: white;
}
textarea { min-height: 100px; }
button, .button {
    display: inline-block; background: #147a53; color: white;
    border: 0; border-radius: 6px; padding: 11px 16px;
    font-size: 16px; text-decoration: none; cursor: pointer;
}
button:hover, .button:hover { background: #0d6040; }
.danger { background: #b3261e; }
.danger:hover { background: #8c1d18; }
label { font-weight: bold; }
.small { color: #65717d; font-size: 14px; }
.price { color: #147a53; font-weight: bold; font-size: 18px; }
.notice { background: #fff4d6; padding: 10px; border-radius: 6px; margin-bottom: 10px; }
footer { text-align: center; color: #65717d; padding: 25px; }
.profile-photo {
    width: 120px; height: 120px; border-radius: 50%;
    object-fit: cover; display: block; margin-bottom: 15px;
}
.role-option { font-weight: normal; display: block; margin: 8px 0; }
.role-option input { display: inline-block; width: auto; margin: 0 8px 0 0; }
</style>
</head>
<body>
<header>
    <h1>AND BUILD ETHIOPIA</h1>
    <p>አንድ ቢልድ ኢትዮጵያ</p>
    <p>የግንባታ ዓለም በአንድ ቦታ! | The World of Construction, All in One Place!</p>
</header>
<nav>
    <a href="/">Home / መነሻ</a>
    <a href="/#categories">Categories / ዘርፎች</a>
    {% if session.get("user_id") %}
        <a href="/add">Post Listing / ማስታወቂያ ጨምር</a>
        <a href="/profile">My Profile / ፕሮፋይሌ</a>
        <a href="/logout">Logout / ውጣ</a>
    {% else %}
        <a href="/register">Register / መመዝገቢያ</a>
        <a href="/login">Login / ግባ</a>
    {% endif %}
</nav>
<main>
    {% with messages = get_flashed_messages() %}
      {% if messages %}
        {% for message in messages %}
          <div class="notice">{{ message }}</div>
        {% endfor %}
      {% endif %}
    {% endwith %}
    {{ content|safe }}
</main>
<footer>AND BUILD ETHIOPIA · አንድ ቢልድ ኢትዮጵያ</footer>
</body>
</html>
"""


def page(content, title="Home"):
    # Add the CSRF hidden field to every POST form automatically.
    field = f'<input type="hidden" name="csrf_token" value="{csrf_token()}">'
    content = re.sub(
        r'(<form[^>]*method="POST"[^>]*>)',
        lambda m: m.group(1) + field,
        content,
    )
    return render_template_string(PAGE, content=content, title=title)


def logged_in_required(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first. / እባክዎ መጀመሪያ ይግቡ።")
            return redirect(url_for("login"))
        return function(*args, **kwargs)
    return wrapper


def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


def listing_card(item, show_category=True):
    """One listing card. All user text is escaped (prevents XSS)."""
    where = escape(item["location"] or "")
    if show_category:
        line = f"{escape(item['category'])} · {where or 'Location not specified'}"
    else:
        line = f"{where}"
    return f"""
    <div class="card">
        <h3><a href="/listing/{item['id']}">{escape(item['title'])}</a></h3>
        <p>{line}</p>
        <p class="price">{escape(item['price'] or 'Price on request')}</p>
    </div>
    """


def whatsapp_number(phone):
    """Convert 09xxxxxxxx / +2519xxxxxxxx to 2519xxxxxxxx for wa.me links."""
    digits = "".join(ch for ch in phone if ch.isdigit())
    if digits.startswith("00"):
        digits = digits[2:]
    elif digits.startswith("0"):
        digits = "251" + digits[1:]
    return digits


# -------------------- HOME AND SEARCH --------------------

@app.route("/")
def home():
    con = database()
    listings = con.execute(
        "SELECT * FROM listings ORDER BY id DESC LIMIT 12"
    ).fetchall()
    con.close()

    category_html = ""
    for cat in CATEGORIES:
        category_html += (
            f'<div class="card"><a href="{url_for("category_page", category=cat)}">'
            f'<h3>{escape(cat)}</h3></a></div>'
        )

    listing_html = "".join(listing_card(item) for item in listings)
    if not listing_html:
        listing_html = '<div class="card">No listings yet. Be the first to post!</div>'

    content = f"""
    <div class="card">
        <h2>Welcome to AND BUILD ETHIOPIA!</h2>
        <p>Find construction materials, machinery, professionals, companies,
        jobs, tenders and projects in one place.</p>
        <form action="/search" method="GET">
            <input name="q" placeholder="Search materials, machinery, jobs..." required>
            <button type="submit">Search / ፈልግ</button>
        </form>
    </div>
    <h2 id="categories">Categories / የግንባታ ዘርፎች</h2>
    <div class="grid">{category_html}</div>
    <h2>Latest Listings / አዳዲስ ማስታወቂያዎች</h2>
    {listing_html}
    """
    return page(content, "Home")


@app.route("/search")
def search():
    q = request.args.get("q", "").strip()
    like = f"%{q}%"
    con = database()
    items = con.execute("""
        SELECT * FROM listings
        WHERE title LIKE ? OR category LIKE ?
        OR description LIKE ? OR location LIKE ?
        ORDER BY id DESC
        LIMIT 100
    """, (like, like, like, like)).fetchall()
    con.close()

    content = f"<h2>Search Results / የፍለጋ ውጤት: {escape(q)}</h2>"
    if not items:
        content += '<div class="card">No results found.</div>'
    content += "".join(listing_card(item) for item in items)
    return page(content, "Search")


@app.route("/category/<path:category>")
def category_page(category):
    if category not in CATEGORIES:
        abort(404)

    con = database()
    items = con.execute(
        "SELECT * FROM listings WHERE category=? ORDER BY id DESC",
        (category,)
    ).fetchall()
    con.close()

    content = f"<h2>{escape(category)}</h2>"
    if not items:
        content += '<div class="card">No listings in this category yet.</div>'
    content += "".join(listing_card(item, show_category=False) for item in items)
    return page(content, category)


# -------------------- REGISTRATION AND LOGIN --------------------

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")

        if not name or not email or not password:
            flash("Please fill in all required fields.")
            return redirect(url_for("register"))

        if len(password) < 6:
            flash("Password must be at least 6 characters. / የይለፍ ቃል ቢያንስ 6 ቁምፊ ይሁን።")
            return redirect(url_for("register"))

        con = database()
        try:
            con.execute("""
                INSERT INTO users (name, email, password, phone)
                VALUES (?, ?, ?, ?)
            """, (name, email, generate_password_hash(password), phone))
            con.commit()
            user = con.execute(
                "SELECT id FROM users WHERE email=?", (email,)
            ).fetchone()
            session.clear()
            session["user_id"] = user["id"]
            session["user"] = name
            flash("Registration successful. Complete your profile.")
            return redirect(url_for("profile"))
        except sqlite3.IntegrityError:
            flash("This email is already registered.")
        finally:
            con.close()

    content = """
    <div class="formbox">
    <h2>Register / ይመዝገቡ</h2>
    <form method="POST">
        <label>Full Name / ሙሉ ስም</label>
        <input name="name" required>
        <label>Email / ኢሜይል</label>
        <input type="email" name="email" required>
        <label>Phone / ስልክ</label>
        <input name="phone">
        <label>Password / የይለፍ ቃል</label>
        <input type="password" name="password" required minlength="6">
        <button type="submit">Create Account / መዝግብ</button>
    </form>
    </div>
    """
    return page(content, "Register")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        con = database()
        user = con.execute(
            "SELECT * FROM users WHERE email=?", (email,)
        ).fetchone()

        valid = False
        if user:
            stored = user["password"]
            try:
                valid = check_password_hash(stored, password)
            except (ValueError, TypeError):
                valid = False

            # Old accounts with a plain-text password: allow login once,
            # then convert the password to a secure hash.
            if not valid and secrets.compare_digest(
                stored.encode("utf-8"), password.encode("utf-8")
            ):
                valid = True
                con.execute(
                    "UPDATE users SET password=? WHERE id=?",
                    (generate_password_hash(password), user["id"]),
                )
                con.commit()
        con.close()

        if valid:
            session.clear()
            session["user_id"] = user["id"]
            session["user"] = user["name"]
            return redirect(url_for("profile"))

        flash("Email or password is incorrect.")
        return redirect(url_for("login"))

    content = """
    <div class="formbox">
    <h2>Login / ግባ</h2>
    <form method="POST">
        <label>Email / ኢሜይል</label>
        <input type="email" name="email" required>
        <label>Password / የይለፍ ቃል</label>
        <input type="password" name="password" required>
        <button type="submit">Login / ግባ</button>
    </form>
    </div>
    """
    return page(content, "Login")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


# -------------------- USER PROFILE --------------------

@app.route("/profile", methods=["GET", "POST"])
@logged_in_required
def profile():
    con = database()
    user = con.execute(
        "SELECT * FROM users WHERE id=?", (session["user_id"],)
    ).fetchone()

    if user is None:
        con.close()
        session.clear()
        return redirect(url_for("login"))

    if request.method == "POST":
        name = request.form.get("name", "").strip() or user["name"]
        phone = request.form.get("phone", "").strip()
        city = request.form.get("city", "").strip()
        company = request.form.get("company", "").strip()
        bio = request.form.get("bio", "").strip()
        selected_roles = request.form.getlist("role")
        role = ",".join(r for r in selected_roles if r in ROLES)
        photo = user["photo"] or ""

        uploaded = request.files.get("photo")
        if uploaded and uploaded.filename:
            if not allowed_file(uploaded.filename):
                con.close()
                flash("Only JPG, JPEG, PNG or WEBP images are allowed.")
                return redirect(url_for("profile"))

            ext = uploaded.filename.rsplit(".", 1)[1].lower()
            filename = f"{user['id']}_{uuid.uuid4().hex[:10]}.{ext}"
            uploaded.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
            photo = filename

        con.execute("""
            UPDATE users
            SET name=?, phone=?, city=?, company=?, bio=?, role=?, photo=?
            WHERE id=?
        """, (name, phone, city, company, bio, role, photo, user["id"]))
        con.commit()
        con.close()
        session["user"] = name
        flash("Profile saved successfully.")
        return redirect(url_for("profile"))

    con.close()

    role_checks = ""
    saved_roles = (user["role"] or "").split(",")
    for role_name in ROLES:
        checked = "checked" if role_name in saved_roles else ""
        role_checks += f"""
        <label class="role-option">
            <input type="checkbox" name="role" value="{escape(role_name)}" {checked}>
            {escape(role_name)}
        </label>
        """

    photo_html = ""
    if user["photo"]:
        photo_html = (
            f'<img class="profile-photo" '
            f'src="/static/uploads/{escape(user["photo"])}" alt="Profile photo">'
        )

    content = f"""
    <div class="formbox">
        <h2>My Profile / የእኔ ፕሮፋይል</h2>
        {photo_html}
        <p><b>Account status:</b> {escape(user['status'] or 'Active')}</p>
        <form method="POST" enctype="multipart/form-data">
            <label>Full Name / ሙሉ ስም</label>
            <input name="name" value="{escape(user['name'] or '')}" required>
            <label>Email / ኢሜይል</label>
            <input value="{escape(user['email'])}" disabled>
            <label>Phone / ስልክ</label>
            <input name="phone" value="{escape(user['phone'] or '')}">
            <label>Profile Photo / የፕሮፋይል ፎቶ</label>
            <input type="file" name="photo" accept=".jpg,.jpeg,.png,.webp">
            <h3>Account Type / የመለያ አይነት</h3>
            <p class="small">You can select more than one.</p>
            {role_checks}
            <label>City / ከተማ</label>
            <input name="city" value="{escape(user['city'] or '')}">
            <label>Company / ድርጅት</label>
            <input name="company" value="{escape(user['company'] or '')}">
            <label>About Me / ስለ እኔ</label>
            <textarea name="bio">{escape(user['bio'] or '')}</textarea>
            <button type="submit">Save Profile / አስቀምጥ</button>
        </form>
    </div>
    """
    return page(content, "My Profile")


# -------------------- CREATE AND VIEW LISTINGS --------------------

@app.route("/add", methods=["GET", "POST"])
@logged_in_required
def add_listing():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        category_name = request.form.get("category", "")
        description = request.form.get("description", "").strip()
        price = request.form.get("price", "").strip()
        location = request.form.get("location", "").strip()
        phone = request.form.get("phone", "").strip()

        if not title or category_name not in CATEGORIES:
            flash("Please enter a title and select a valid category.")
            return redirect(url_for("add_listing"))

        con = database()
        con.execute("""
            INSERT INTO listings
            (title, category, description, price, location, phone, owner, owner_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            title, category_name, description, price, location,
            phone, session.get("user", ""), session["user_id"]
        ))
        con.commit()
        con.close()
        flash("Your listing has been published.")
        return redirect(url_for("home"))

    options = "".join(
        f'<option value="{escape(c)}">{escape(c)}</option>' for c in CATEGORIES
    )
    content = f"""
    <div class="formbox">
        <h2>Post a Listing / ማስታወቂያ ያስገቡ</h2>
        <form method="POST">
            <label>Title / ርዕስ</label>
            <input name="title" required>
            <label>Category / ዘርፍ</label>
            <select name="category" required>
                <option value="">Choose category</option>
                {options}
            </select>
            <label>Description / መግለጫ</label>
            <textarea name="description"></textarea>
            <label>Price / ዋጋ (ETB)</label>
            <input name="price" placeholder="e.g. 25000 ETB">
            <label>Location / አካባቢ</label>
            <input name="location">
            <label>Phone / ስልክ</label>
            <input name="phone">
            <button type="submit">Publish / አትም</button>
        </form>
    </div>
    """
    return page(content, "Add Listing")


@app.route("/listing/<int:listing_id>")
def view_listing(listing_id):
    con = database()
    item = con.execute(
        "SELECT * FROM listings WHERE id=?", (listing_id,)
    ).fetchone()
    con.close()

    if item is None:
        return page("<div class='card'>Listing not found.</div>", "Not Found"), 404

    phone = item["phone"] or ""
    contact = ""
    if phone:
        contact = f"""
        <p><a class="button" href="https://wa.me/{whatsapp_number(phone)}"
        target="_blank" rel="noopener">Contact on WhatsApp</a></p>
        <p>Phone: {escape(phone)}</p>
        """

    delete_html = ""
    if session.get("user_id") and session["user_id"] == item["owner_id"]:
        delete_html = f"""
        <form method="POST" action="/listing/{item['id']}/delete"
              onsubmit="return confirm('Delete this listing? / ይህን ማስታወቂያ ይሰረዝ?');">
            <button type="submit" class="danger">Delete / ሰርዝ</button>
        </form>
        """

    content = f"""
    <div class="card">
        <h2>{escape(item['title'])}</h2>
        <p><b>Category:</b> {escape(item['category'])}</p>
        <p><b>Description:</b> {escape(item['description'] or 'No description')}</p>
        <p class="price">{escape(item['price'] or 'Price on request')}</p>
        <p><b>Location:</b> {escape(item['location'] or 'Not specified')}</p>
        <p><b>Posted by:</b> {escape(item['owner'] or 'Member')}</p>
        {contact}
        {delete_html}
    </div>
    """
    return page(content, item["title"])


@app.route("/listing/<int:listing_id>/delete", methods=["POST"])
@logged_in_required
def delete_listing(listing_id):
    con = database()
    con.execute(
        "DELETE FROM listings WHERE id=? AND owner_id=?",
        (listing_id, session["user_id"]),
    )
    con.commit()
    con.close()
    flash("Listing deleted. / ማስታወቂያው ተሰርዟል።")
    return redirect(url_for("home"))


# -------------------- RUN THE WEBSITE --------------------
# For online hosting use:  gunicorn app:app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    host = "0.0.0.0" if os.environ.get("PORT") else "127.0.0.1"
    app.run(host=host, port=port, debug=os.environ.get("FLASK_DEBUG") == "1")
