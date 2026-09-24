"""Agent accounts. One table, kept deliberately small.

`active` is the whole point of this app existing: Xiaohui can flip one
agent's access off without touching anyone else's account, from the admin
page, with no server shell access needed. Login itself checks this flag
(see auth.py) -- a disabled account fails to log in even with the right
password, not just "hidden from a list somewhere."
"""
from datetime import datetime, timezone

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()


class Agent(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    office = db.Column(db.String(255), nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, nullable=False, default=False)
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def set_password(self, raw):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw):
        return check_password_hash(self.password_hash, raw)

    # Flask-Login calls this to decide whether a session is still valid.
    # A disabled agent's existing browser session stops working on their
    # very next request, not just at their next login.
    @property
    def is_active(self):
        return self.active


class Report(db.Model):
    """One row per generation run, so the dashboard can show an agent their
    own recent reports without re-uploading. Files themselves live on disk
    under instance/reports/<id>/ -- see app.py's REPORTS_DIR."""
    id = db.Column(db.Integer, primary_key=True)
    agent_id = db.Column(db.Integer, db.ForeignKey('agent.id'), nullable=False)
    subdivision = db.Column(db.String(255), nullable=False)
    city = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    files = db.Column(db.Text, nullable=False)  # newline-separated relative filenames
