import os
import sqlite3
from functools import wraps

from flask import (
    Flask, request, redirect, session, url_for,
    render_template_string, flash
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# -------------------- APP SETTINGS --------------------

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key-before-online-publishing")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "andbuild.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
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

    # Add profile fields to an existing users table without deleting user data.
    existing = {
        row["name"]
        for row in con.execute("PRAGMA table_info(users)").fetchall()
    }
    additions = {
        "role": "TEXT DEFAULT 'Buyer'",
        "city": "TEXT DEFAULT ''",
        "company": "TEXT DEFAULT ''",
        "bio": "TEXT DEFAULT ''",
        "photo": "TEXT DEFAULT ''",
        "status": "TEXT DEFAULT 'Active'",
    }
    for column, definition in additions.items():
        if column not in existing:
            con.execute(f"ALTER TABLE users ADD COLUMN {column} {definition}")

    con.commit()
    con.close()


init_db()


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
    background: #f4f6f3; color: #202733;
}
header {
    background: #123b32; color: white;
    padding: 18px 14px; text-align: center;
    border-bottom: 4px solid #e7b83d;
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
main { max-width: 1150px; margin: 22px auto; padding: 0 14px; }
.card, .formbox {
    background: white; padding: 18px; margin-bottom: 15px;
    border-radius: 12px; box-shadow: 0 2px 8px #00000012;
}
.hero { background: linear-gradient(120deg, #123b32, #176747); color: white;
    padding: 30px 22px; border-radius: 14px; margin-bottom: 24px; }
.hero h2 { font-size: clamp(25px, 5vw, 38px); margin: 0 0 10px; }
.hero p { font-size: 17px; line-height: 1.6; max-width: 720px; }
.hero .tagline { color: #f5d36f; font-weight: bold; }
.search-row { display: flex; gap: 8px; margin-top: 18px; }
.search-row input { flex: 1; margin: 0; background: white; }
.search-row button { background: #e7b83d; color: #18352c; font-weight: bold; }
.section-title { margin: 28px 0 14px; color: #173f33; }
.category-card { text-align: center; min-height: 112px; display: flex;
    flex-direction: column; align-items: center; justify-content: center; }
.category-card a { text-decoration: none; color: #173f33; }
.category-icon { font-size: 30px; margin-bottom: 8px; }
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
label { font-weight: bold; }
.small { color: #65717d; font-size: 14px; }
.price { color: #147a53; font-weight: bold; font-size: 18px; }
.notice { background: #fff4d6; padding: 10px; border-radius: 6px; }
footer { text-align: center; color: #65717d; padding: 25px; }
@media (max-width: 560px) {
    .search-row { flex-direction: column; }
    .search-row button { width: 100%; }
    nav { gap: 10px; }
    nav a { font-size: 14px; }
}
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


# -------------------- HOME AND SEARCH --------------------

@app.route("/")
def home():
    con = database()
    listings = con.execute(
        "SELECT * FROM listings ORDER BY id DESC LIMIT 8"
    ).fetchall()
    con.close()

    category_icons = {
        "Construction Materials": "🧱",
        "Machinery for Sale": "🚜",
        "Machinery for Rent": "🏗️",
        "Professionals": "👷",
        "Construction Companies": "🏢",
        "Construction Jobs": "💼",
        "Tenders and Projects": "📋",
    }
    category_html = ""
    for category_name in CATEGORIES:
        icon = category_icons.get(category_name, "🏗️")
        category_html += f'<div class="card category-card"><a href="/category/{category_name}"><div class="category-icon">{icon}</div><strong>{category_name}</strong></a></div>'

    listing_html = ""
    for item in listings:
        listing_html += f"""
        <div class="card">
            <h3><a href="/listing/{item['id']}">{item['title']}</a></h3>
            <p>{item['category']} · {item['location'] or 'Location not specified'}</p>
            <p class="price">{item['price'] or 'Price on request'}</p>
        </div>
        """

    if not listing_html:
        listing_html = '<div class="card">No listings yet. Be the first to post! / ገና ማስታወቂያ አልተጨመረም።</div>'

    content = f"""
    <section class="hero">
        <p class="tagline">የግንባታ ዓለም በአንድ ቦታ! · The World of Construction, All in One Place!</p>
        <h2>Welcome to AND BUILD ETHIOPIA</h2>
        <p>Find construction materials, machinery, professionals, companies,
        jobs, tenders and projects — all in one place.</p>
        <form class="search-row" action="/search" method="GET">
            <input name="q" placeholder="Search materials, machinery, jobs... / ፈልግ" required>
            <button type="submit">Search / ፈልግ</button>
        </form>
    </section>
    <h2 class="section-title" id="categories">Explore Construction Services / የግንባታ ዘርፎችን ይመልከቱ</h2>
    <div class="grid">{category_html}</div>
    <h2 class="section-title">Latest Listings / አዳዲስ ማስታወቂያዎች</h2>
    <div class="grid">{listing_html}</div>
    <p><a class="button" href="/add">Post a Listing / ማስታወቂያ ጨምር</a></p>
    """
    return page(content, "Home")

@app.route("/search")
def search():
    q = request.args.get("q", "").strip()
    con = database()
    items = con.execute("""
        SELECT * FROM listings
        WHERE title LIKE ? OR category LIKE ?
        OR description LIKE ? OR location LIKE ?
        ORDER BY id DESC
    """, (f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%")).fetchall()
    con.close()

    content = f"<h2>Search Results / የፍለጋ ውጤት: {q}</h2>"
    if not items:
        content += '<div class="card">No results found.</div>'
    for item in items:
        content += f"""
        <div class="card">
            <h3><a href="/listing/{item['id']}">{item['title']}</a></h3>
            <p>{item['category']} · {item['location'] or ''}</p>
            <p class="price">{item['price'] or 'Price on request'}</p>
        </div>
        """
    return page(content, "Search")


@app.route("/category/<path:category>")
def category(category):
    con = database()
    items = con.execute(
        "SELECT * FROM listings WHERE category=? ORDER BY id DESC",
        (category,)
    ).fetchall()
    con.close()

    content = f"<h2>{category}</h2>"
    if not items:
        content += '<div class="card">No listings in this category yet.</div>'
    for item in items:
        content += f"""
        <div class="card">
            <h3><a href="/listing/{item['id']}">{item['title']}</a></h3>
            <p>{item['location'] or ''}</p>
            <p class="price">{item['price'] or 'Price on request'}</p>
        </div>
        """
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
        con.close()

        valid = False
        if user:
            try:
                valid = check_password_hash(user["password"], password)
            except (ValueError, TypeError):
                valid = False
            # Compatibility with accounts created by an older local version.
            if not valid and user["password"] == password:
                valid = True

        if valid:
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
        name = request.form.get("name", "").strip()
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

            filename = secure_filename(uploaded.filename)
            filename = f"{user['id']}_{filename}"
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
            <input type="checkbox" name="role" value="{role_name}" {checked}>
            {role_name}
        </label>
        """

    photo_html = ""
    if user["photo"]:
        photo_html = (
            f'<img class="profile-photo" '
            f'src="/static/uploads/{user["photo"]}" alt="Profile photo">'
        )

    content = f"""
    <div class="formbox">
        <h2>My Profile / የእኔ ፕሮፋይል</h2>
        {photo_html}
        <p><b>Account status:</b> {user['status'] or 'Active'}</p>
        <form method="POST" enctype="multipart/form-data">
            <label>Full Name / ሙሉ ስም</label>
            <input name="name" value="{user['name'] or ''}" required>
            <label>Email / ኢሜይል</label>
            <input value="{user['email']}" disabled>
            <label>Phone / ስልክ</label>
            <input name="phone" value="{user['phone'] or ''}">
            <label>Profile Photo / የፕሮፋይል ፎቶ</label>
            <input type="file" name="photo" accept=".jpg,.jpeg,.png,.webp">
            <h3>Account Type / የመለያ አይነት</h3>
            <p class="small">You can select more than one.</p>
            {role_checks}
            <label>City / ከተማ</label>
            <input name="city" value="{user['city'] or ''}">
            <label>Company / ድርጅት</label>
            <input name="company" value="{user['company'] or ''}">
            <label>About Me / ስለ እኔ</label>
            <textarea name="bio">{user['bio'] or ''}</textarea>
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
            (title, category, description, price, location, phone, owner)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            title, category_name, description, price, location,
            phone, session.get("user", "")
        ))
        con.commit()
        con.close()
        flash("Your listing has been published.")
        return redirect(url_for("home"))

    options = "".join(
        f'<option value="{c}">{c}</option>' for c in CATEGORIES
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
        return page("<div class='card'>Listing not found.</div>", "Not Found")

    phone = item["phone"] or ""
    contact = ""
    if phone:
        digits = "".join(ch for ch in phone if ch.isdigit())
        contact = f"""
        <p><a class="button" href="https://wa.me/{digits}" target="_blank">
        Contact on WhatsApp</a></p>
        <p>Phone: {phone}</p>
        """

    content = f"""
    <div class="card">
        <h2>{item['title']}</h2>
        <p><b>Category:</b> {item['category']}</p>
        <p><b>Description:</b> {item['description'] or 'No description'}</p>
        <p class="price">{item['price'] or 'Price on request'}</p>
        <p><b>Location:</b> {item['location'] or 'Not specified'}</p>
        <p><b>Posted by:</b> {item['owner'] or 'Member'}</p>
        {contact}
    </div>
    """
    return page(content, item["title"])


# -------------------- RUN THE WEBSITE --------------------

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
