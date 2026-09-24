"""Subdivision Brief web app.

Agents log in, upload their own MLS export, and get back the Master Brief,
Appendix, carousel and postcard -- the same pipeline that ran inside a Claude
conversation all last session, now running as an ordinary web request. No
Anthropic API call happens anywhere in this file or anything it imports from
skill/: this whole app's marginal cost per report is server compute, not
Claude usage. See skill/CHANGELOG.md and skill/SKILL.md for what that
pipeline actually does and every bug already found and fixed in it -- this
app is deliberately a thin wrapper, not a reimplementation.

Per-agent accounts (models.Agent) exist so Xiaohui can disable one agent's
access from /admin without touching anyone else's -- that was the explicit
reason for choosing this over one shared site-wide password.
"""
import os
import secrets
import shutil
import sys
import tempfile
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import (Flask, abort, flash, redirect, render_template, request,
                    send_from_directory, url_for)
from flask_login import current_user, login_required, login_user, logout_user

from auth import admin_required, login_manager
from models import Agent, Report, db

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR / 'skill'))  # so `import master` etc. resolve

INSTANCE_DIR = BASE_DIR / 'instance'
REPORTS_DIR = INSTANCE_DIR / 'reports'
INSTANCE_DIR.mkdir(exist_ok=True)
REPORTS_DIR.mkdir(exist_ok=True)

ALLOWED_EXT = {'.csv'}
MAX_UPLOAD_MB = 25
RETENTION_DAYS = int(os.environ.get('RETENTION_DAYS', 30))


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
        'DATABASE_URL', f"sqlite:///{INSTANCE_DIR / 'app.db'}")
    app.config['MAX_CONTENT_LENGTH'] = MAX_UPLOAD_MB * 1024 * 1024

    db.init_app(app)
    login_manager.init_app(app)

    with app.app_context():
        db.create_all()
        _bootstrap_admin()

    register_routes(app)
    return app


def _bootstrap_admin():
    """Creates the first admin account from environment variables if no
    admin exists yet. Runs on every boot; a no-op once an admin is present.
    This is how the very first login gets created without needing shell
    access on the host -- set ADMIN_EMAIL/ADMIN_PASSWORD/ADMIN_NAME once in
    Render's environment settings, deploy, then those variables can be
    removed (the account persists in the database from then on)."""
    if Agent.query.filter_by(is_admin=True).first():
        return
    email = os.environ.get('ADMIN_EMAIL')
    pw = os.environ.get('ADMIN_PASSWORD')
    if not email or not pw:
        print('[bootstrap] No admin exists and ADMIN_EMAIL/ADMIN_PASSWORD are '
              'not set -- no one can log in yet. Set both in the environment '
              'and redeploy.')
        return
    admin = Agent(email=email.strip().lower(),
                 name=os.environ.get('ADMIN_NAME', 'Admin'),
                 is_admin=True, active=True)
    admin.set_password(pw)
    db.session.add(admin)
    db.session.commit()
    print(f'[bootstrap] Created admin account for {email}.')


def _purge_expired_reports():
    """Deletes any report (files and database row) older than RETENTION_DAYS.

    Runs once per request via before_request below -- cheap at this app's
    expected scale (a handful of agents, occasional generation), so no
    separate scheduled job or cron service is needed. That also means no
    second paid Render service just to expire old files.

    A report past the window is gone entirely, not just hidden from the
    dashboard list: the files are deleted from instance/reports/<id>/ and
    the Report row is deleted, so a bookmarked /reports/<id> link for an
    expired report 404s rather than quietly still working.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)
    expired = Report.query.filter(Report.created_at < cutoff).all()
    for r in expired:
        shutil.rmtree(REPORTS_DIR / str(r.id), ignore_errors=True)
        db.session.delete(r)
    if expired:
        db.session.commit()
        print(f'[retention] purged {len(expired)} report(s) older than '
             f'{RETENTION_DAYS} days.')


def register_routes(app):

    @app.before_request
    def _enforce_retention():
        _purge_expired_reports()

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        if request.method == 'POST':
            email = request.form.get('email', '').strip().lower()
            pw = request.form.get('password', '')
            agent = Agent.query.filter_by(email=email).first()
            # Same message whether the email doesn't exist, the password is
            # wrong, or the account is disabled -- a disabled agent gets no
            # signal from the login page that they've specifically been cut
            # off, which is Xiaohui's call to communicate or not, not this
            # page's.
            if agent and agent.active and agent.check_password(pw):
                login_user(agent)
                return redirect(url_for('dashboard'))
            flash('Incorrect email or password.', 'error')
        return render_template('login.html')

    @app.route('/logout', methods=['POST'])
    @login_required
    def logout():
        logout_user()
        return redirect(url_for('login'))

    @app.route('/')
    @login_required
    def dashboard():
        reports = (Report.query.filter_by(agent_id=current_user.id)
                  .order_by(Report.created_at.desc()).limit(15).all())
        return render_template('dashboard.html', reports=reports)

    @app.route('/generate', methods=['POST'])
    @login_required
    def generate():
        f = request.files.get('csv_file')
        sub = request.form.get('subdivision', '').strip()
        city = request.form.get('city', '').strip()
        want_carousel = request.form.get('carousel') == 'on'
        want_postcard = request.form.get('postcard') == 'on'

        if not f or not f.filename:
            flash('Choose an MLS export CSV first.', 'error')
            return redirect(url_for('dashboard'))
        if Path(f.filename).suffix.lower() not in ALLOWED_EXT:
            flash('That file needs to be a .csv MLS export.', 'error')
            return redirect(url_for('dashboard'))
        if not sub or not city:
            flash('Subdivision name and city are both required.', 'error')
            return redirect(url_for('dashboard'))

        report = Report(agent_id=current_user.id, subdivision=sub, city=city, files='')
        db.session.add(report)
        db.session.commit()
        outdir = REPORTS_DIR / str(report.id)
        outdir.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(prefix='upload-') as tmp:
            csv_path = Path(tmp) / f.filename
            f.save(csv_path)

            try:
                import co_data
                import core
                import master
                paths, m, scores = master.build(
                    str(csv_path), sub, city, outdir=str(outdir), carousel=want_carousel)

                if want_postcard:
                    import postcard
                    d = core.load(str(csv_path))
                    area = co_data.from_export(d).as_dict()
                    paths += postcard.render(m, sub, city, str(outdir),
                                             scores=scores, area=area, place=city)
            except core.BriefError as exc:
                # Deliberate stops (stale mortgage rate, unrecognized county,
                # etc.) -- these are the pipeline correctly refusing, not a
                # crash. Surfaced as-is; see skill/SKILL.md rule 6 for what
                # the rate-staleness check specifically means and how to
                # clear it (an admin needs to update skill/core.py's FIN
                # dict and redeploy -- this cannot self-heal from a request).
                shutil.rmtree(outdir, ignore_errors=True)
                db.session.delete(report)
                db.session.commit()
                flash(f'Could not build this report: {exc}', 'error')
                return redirect(url_for('dashboard'))
            except Exception:
                shutil.rmtree(outdir, ignore_errors=True)
                db.session.delete(report)
                db.session.commit()
                traceback.print_exc()
                flash('Something went wrong generating this report. '
                     'Double-check the CSV is a subdivision activity export, '
                     'or try again in a moment.', 'error')
                return redirect(url_for('dashboard'))

        report.files = '\n'.join(Path(p).name for p in paths)
        db.session.commit()
        return redirect(url_for('report_detail', report_id=report.id))

    @app.route('/reports/<int:report_id>')
    @login_required
    def report_detail(report_id):
        report = Report.query.get_or_404(report_id)
        if report.agent_id != current_user.id and not current_user.is_admin:
            abort(403)
        files = [f for f in report.files.split('\n') if f]
        return render_template('report_detail.html', report=report, files=files)

    @app.route('/download/<int:report_id>/<path:filename>')
    @login_required
    def download(report_id, filename):
        report = Report.query.get_or_404(report_id)
        if report.agent_id != current_user.id and not current_user.is_admin:
            abort(403)
        return send_from_directory(REPORTS_DIR / str(report_id), filename, as_attachment=True)

    # --------------------------------------------------------------- admin

    @app.route('/admin')
    @admin_required
    def admin_home():
        agents = Agent.query.order_by(Agent.created_at.desc()).all()
        return render_template('admin.html', agents=agents)

    @app.route('/admin/agents', methods=['POST'])
    @admin_required
    def admin_create_agent():
        email = request.form.get('email', '').strip().lower()
        name = request.form.get('name', '').strip()
        office = request.form.get('office', '').strip()
        if not email or not name:
            flash('Name and email are both required.', 'error')
            return redirect(url_for('admin_home'))
        if Agent.query.filter_by(email=email).first():
            flash(f'{email} already has an account.', 'error')
            return redirect(url_for('admin_home'))
        temp_pw = secrets.token_urlsafe(9)
        agent = Agent(email=email, name=name, office=office or None, active=True)
        agent.set_password(temp_pw)
        db.session.add(agent)
        db.session.commit()
        flash(f'Created {name} ({email}). One-time password: {temp_pw} '
             f'-- share this now, it will not be shown again.', 'success')
        return redirect(url_for('admin_home'))

    @app.route('/admin/agents/<int:agent_id>/toggle', methods=['POST'])
    @admin_required
    def admin_toggle_agent(agent_id):
        agent = Agent.query.get_or_404(agent_id)
        if agent.id == current_user.id:
            flash("You can't disable your own admin account.", 'error')
            return redirect(url_for('admin_home'))
        agent.active = not agent.active
        db.session.commit()
        flash(f'{agent.name} is now {"active" if agent.active else "disabled"}.', 'success')
        return redirect(url_for('admin_home'))

    @app.route('/admin/agents/<int:agent_id>/reset', methods=['POST'])
    @admin_required
    def admin_reset_agent(agent_id):
        agent = Agent.query.get_or_404(agent_id)
        temp_pw = secrets.token_urlsafe(9)
        agent.set_password(temp_pw)
        db.session.commit()
        flash(f'New one-time password for {agent.name}: {temp_pw} '
             f'-- share this now, it will not be shown again.', 'success')
        return redirect(url_for('admin_home'))

    @app.errorhandler(403)
    def forbidden(_e):
        return render_template('error.html', code=403,
                              message="You don't have access to that."), 403

    @app.errorhandler(404)
    def not_found(_e):
        return render_template('error.html', code=404,
                              message="That page doesn't exist."), 404


app = create_app()

if __name__ == '__main__':
    app.run(debug=True, port=5000)
