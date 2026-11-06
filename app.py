import os, secrets
from datetime import datetime
from difflib import SequenceMatcher
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, abort
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "replace-this-secret-before-deployment")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(os.path.abspath(os.path.dirname(__file__)), "verida.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = os.path.join(app.root_path, "static", "uploads")
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
db = SQLAlchemy(app)
ALLOWED = {"png", "jpg", "jpeg", "webp"}

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default="student", nullable=False)

class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    kind = db.Column(db.String(10), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=False)
    location = db.Column(db.String(120), nullable=False)
    item_date = db.Column(db.String(30), nullable=False)
    image = db.Column(db.String(255))
    status = db.Column(db.String(20), default="open", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    reporter = db.relationship("User", backref="items")

class Claim(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey("item.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default="pending")
    item = db.relationship("Item", backref="claims")
    claimant = db.relationship("User")

def user_now():
    return db.session.get(User, session["user_id"]) if session.get("user_id") else None

@app.context_processor
def inject_user():
    return {"current_user": user_now()}

def login_required(fn):
    @wraps(fn)
    def wrapped(*a, **kw):
        if not user_now():
            flash("Please log in first.", "warning")
            return redirect(url_for("login"))
        return fn(*a, **kw)
    return wrapped

def admin_required(fn):
    @wraps(fn)
    def wrapped(*a, **kw):
        u = user_now()
        if not u or u.role != "admin":
            abort(403)
        return fn(*a, **kw)
    return wrapped

def similarity(a, b):
    # Demo text similarity only; this does not perform AI image recognition.
    x = f"{a.name} {a.category} {a.description}".lower()
    y = f"{b.name} {b.category} {b.description}".lower()
    return SequenceMatcher(None, x, y).ratio()

@app.route("/")
def home():
    items = Item.query.filter_by(status="open").order_by(Item.created_at.desc()).limit(6).all()
    return render_template("home.html", items=items)

@app.route("/items")
def items():
    q, kind = request.args.get("q", "").strip(), request.args.get("kind", "")
    query = Item.query.filter_by(status="open")
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(Item.name.ilike(like), Item.category.ilike(like), Item.description.ilike(like), Item.location.ilike(like)))
    if kind in ("lost", "found"):
        query = query.filter_by(kind=kind)
    return render_template("items.html", items=query.order_by(Item.created_at.desc()).all(), q=q, kind=kind)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name, email, password = request.form.get("name", "").strip(), request.form.get("email", "").strip().lower(), request.form.get("password", "")
        if not name or not email or len(password) < 8:
            flash("Enter all details. Password must be at least 8 characters.", "danger")
        elif User.query.filter_by(email=email).first():
            flash("Email already registered.", "danger")
        else:
            u = User(name=name, email=email, password_hash=generate_password_hash(password))
            db.session.add(u); db.session.commit()
            session["user_id"] = u.id
            return redirect(url_for("dashboard"))
    return render_template("auth.html", mode="register")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = User.query.filter_by(email=request.form.get("email", "").strip().lower()).first()
        if u and check_password_hash(u.password_hash, request.form.get("password", "")):
            session.clear(); session["user_id"] = u.id
            return redirect(url_for("admin") if u.role == "admin" else url_for("dashboard"))
        flash("Incorrect email or password.", "danger")
    return render_template("auth.html", mode="login")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

@app.route("/report/<kind>", methods=["GET", "POST"])
@login_required
def report(kind):
    if kind not in ("lost", "found"): abort(404)
    if request.method == "POST":
        fields = [request.form.get(k, "").strip() for k in ("name", "category", "description", "location", "item_date")]
        if not all(fields):
            flash("Please fill every required field.", "danger")
        else:
            photo = request.files.get("image")
            filename = None
            if photo and photo.filename:
                ext = photo.filename.rsplit(".", 1)[-1].lower()
                if "." not in photo.filename or ext not in ALLOWED:
                    flash("Use PNG, JPG, JPEG or WEBP images.", "danger")
                    return render_template("report.html", kind=kind)
                filename = secrets.token_hex(8) + "_" + secure_filename(photo.filename)
                photo.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
            item = Item(user_id=user_now().id, kind=kind, name=fields[0], category=fields[1], description=fields[2], location=fields[3], item_date=fields[4], image=filename)
            db.session.add(item); db.session.commit()
            flash("Your report has been submitted.", "success")
            return redirect(url_for("detail", item_id=item.id))
    return render_template("report.html", kind=kind)

@app.route("/item/<int:item_id>")
def detail(item_id):
    item = db.session.get(Item, item_id) or abort(404)
    opposite = "found" if item.kind == "lost" else "lost"
    others = Item.query.filter_by(kind=opposite, status="open").all()
    matches = sorted([(similarity(item, x), x) for x in others], reverse=True, key=lambda v:v[0])[:3]
    return render_template("detail.html", item=item, matches=[(int(s*100), x) for s,x in matches if s > .12])

@app.route("/claim/<int:item_id>", methods=["POST"])
@login_required
def claim(item_id):
    item = db.session.get(Item, item_id) or abort(404)
    msg = request.form.get("message", "").strip()
    if item.user_id == user_now().id or not msg:
        flash("Add verification details. You cannot claim your own report.", "warning")
    else:
        db.session.add(Claim(item_id=item.id, user_id=user_now().id, message=msg)); db.session.commit()
        flash("Claim request sent.", "success")
    return redirect(url_for("detail", item_id=item.id))

@app.route("/dashboard")
@login_required
def dashboard():
    u = user_now()
    own = Item.query.filter_by(user_id=u.id).order_by(Item.created_at.desc()).all()
    sent = Claim.query.filter_by(user_id=u.id).all()
    received = Claim.query.join(Item).filter(Item.user_id == u.id).all()
    return render_template("dashboard.html", own=own, sent=sent, received=received)

@app.route("/admin")
@admin_required
def admin():
    return render_template("admin.html", items=Item.query.order_by(Item.created_at.desc()).all(), claims=Claim.query.all(), users=User.query.all())

@app.route("/admin/item/<int:item_id>", methods=["POST"])
@admin_required
def admin_item(item_id):
    item = db.session.get(Item, item_id) or abort(404)
    status = request.form.get("status")
    if status not in ("open", "returned", "rejected"): abort(400)
    item.status = status; db.session.commit()
    return redirect(url_for("admin"))

@app.route("/admin/claim/<int:claim_id>", methods=["POST"])
@admin_required
def admin_claim(claim_id):
    c = db.session.get(Claim, claim_id) or abort(404)
    status = request.form.get("status")
    if status not in ("pending", "approved", "rejected"): abort(400)
    c.status = status
    if status == "approved": c.item.status = "returned"
    db.session.commit()
    return redirect(url_for("admin"))

@app.cli.command("init-db")
def init_db():
    db.create_all()
    email = os.environ.get("VERIDA_ADMIN_EMAIL", "admin@verida.local")
    password = os.environ.get("VERIDA_ADMIN_PASSWORD", "ChangeMe123!")
    if not User.query.filter_by(email=email).first():
        db.session.add(User(name="VERIDA Admin", email=email, password_hash=generate_password_hash(password), role="admin"))
        db.session.commit()
    print("Database initialized. Admin:", email, "| Set a private password before real use.")


with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)

