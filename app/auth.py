import time
from collections import defaultdict
from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, session)
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models import User

auth = Blueprint('auth', __name__)

# ── Brute-force protection ────────────────────────────────────────────────────
# In-memory store: {ip: [timestamp, ...]}  — resets on container restart (fine for home use)
_attempts: dict = defaultdict(list)
MAX_ATTEMPTS = 10       # max failed attempts
WINDOW_SEC   = 600      # within this many seconds (10 min)
LOCKOUT_SEC  = 900      # lockout duration (15 min)


def _is_locked(ip: str) -> tuple[bool, int]:
    """Returns (locked, seconds_remaining)."""
    now = time.time()
    # Remove old attempts outside the window
    _attempts[ip] = [t for t in _attempts[ip] if now - t < WINDOW_SEC]
    if len(_attempts[ip]) >= MAX_ATTEMPTS:
        oldest = _attempts[ip][0]
        remaining = int(LOCKOUT_SEC - (now - oldest))
        if remaining > 0:
            return True, remaining
        # Lockout expired — clear
        _attempts[ip] = []
    return False, 0


def _record_failure(ip: str):
    _attempts[ip].append(time.time())


def _clear_attempts(ip: str):
    _attempts.pop(ip, None)


# ── Routes ────────────────────────────────────────────────────────────────────

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    error = None
    locked = False
    lockout_mins = 0

    ip = request.remote_addr or '0.0.0.0'
    is_locked, remaining = _is_locked(ip)

    if request.method == 'POST':
        if is_locked:
            locked = True
            lockout_mins = max(1, remaining // 60)
        else:
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '')
            remember = request.form.get('remember') == 'on'

            user = User.query.filter_by(username=username).first()

            if user and user.check_password(password):
                _clear_attempts(ip)
                # Apply session timeout from settings
                from app.models import AppSettings
                timeout_days = int(AppSettings.query.filter_by(key='session_timeout').first().value if AppSettings.query.filter_by(key='session_timeout').first() else 30)
                if timeout_days > 0:
                    from datetime import timedelta
                    session.permanent = True
                    from flask import current_app
                    current_app.permanent_session_lifetime = timedelta(days=timeout_days)
                else:
                    session.permanent = False
                login_user(user, remember=remember)
                # Redirect to originally requested page or dashboard
                next_page = request.args.get('next', '')
                if next_page and next_page.startswith('/') and not next_page.startswith('//'):
                    return redirect(next_page)
                return redirect(url_for('main.dashboard'))
            else:
                _record_failure(ip)
                is_locked, remaining = _is_locked(ip)
                if is_locked:
                    locked = True
                    lockout_mins = max(1, remaining // 60)
                else:
                    attempts_left = MAX_ATTEMPTS - len(_attempts[ip])
                    error = f'Falscher Benutzername oder Passwort. Noch {attempts_left} Versuch(e).'

    return render_template('login.html', error=error, locked=locked, lockout_mins=lockout_mins)


@auth.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))


@auth.route('/change-password', methods=['POST'])
@login_required
def change_password():
    current_pw  = request.form.get('current_password', '')
    new_pw      = request.form.get('new_password', '')
    confirm_pw  = request.form.get('confirm_password', '')

    if not current_user.check_password(current_pw):
        flash('Aktuelles Passwort falsch.', 'error')
    elif len(new_pw) < 8:
        flash('Neues Passwort muss mindestens 8 Zeichen haben.', 'error')
    elif new_pw != confirm_pw:
        flash('Passwörter stimmen nicht überein.', 'error')
    else:
        current_user.set_password(new_pw)
        db.session.commit()
        flash('Passwort erfolgreich geändert.', 'success')

    return redirect(url_for('main.settings'))
