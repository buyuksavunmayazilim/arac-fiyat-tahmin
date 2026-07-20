from flask import Blueprint, render_template, session
import uuid

views_bp = Blueprint("views", __name__)


def ensure_session():
    if "session_id" not in session:
        session["session_id"] = str(uuid.uuid4())


@views_bp.route("/")
def index():
    ensure_session()
    return render_template("index.html")


@views_bp.route("/result")
def result():
    return render_template("result.html")


@views_bp.route("/history")
def history():
    ensure_session()
    return render_template("history.html")


@views_bp.route("/analytics")
def analytics():
    return render_template("analytics.html")


@views_bp.route("/compare")
def compare():
    return render_template("compare.html")


@views_bp.route("/config")
def config():
    return render_template("config.html")


@views_bp.route("/bfl")
def bfl():
    return render_template("bfl.html")
