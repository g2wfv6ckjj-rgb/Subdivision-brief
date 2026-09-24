"""Flask-Login wiring, plus the one extra guard this app needs: admin-only
routes. Everything else (login required, session cookies, "remember me")
comes from Flask-Login itself -- no custom session handling written here,
since that's exactly the kind of thing worth not hand-rolling.
"""
from functools import wraps

from flask import abort
from flask_login import LoginManager, current_user

from models import Agent

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to continue.'


@login_manager.user_loader
def load_user(user_id):
    return Agent.query.get(int(user_id))


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return view(*args, **kwargs)
    return wrapped
