import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

db = SQLAlchemy()
login_manager = LoginManager()


def create_app():
    app = Flask(__name__)
    basedir = os.path.abspath(os.path.dirname(__file__))
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'change-this-in-production-please')
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, '..', 'data', 'finance.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['UPLOAD_FOLDER'] = os.path.join(basedir, 'static', 'uploads')
    app.config['DOCS_FOLDER']   = os.path.join(basedir, '..', 'data', 'documents')
    app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024
    app.config['REMEMBER_COOKIE_DURATION'] = 60 * 60 * 24 * 30   # 30 days
    app.config['SESSION_COOKIE_HTTPONLY']  = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

    os.makedirs(os.path.join(basedir, '..', 'data'), exist_ok=True)
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['DOCS_FOLDER'],   exist_ok=True)

    db.init_app(app)

    login_manager.init_app(app)
    login_manager.login_view      = 'auth.login'
    login_manager.login_message   = 'Bitte melde dich an.'

    from app.routes import main
    from app.auth   import auth
    app.register_blueprint(main)
    app.register_blueprint(auth)

    with app.app_context():
        db.create_all()
        _init_default_data()

    return app


def _init_default_data():
    from app.models import Category, AppSettings, User
    import time, os

    time.sleep(0.05)

    # Create default admin user if none exists
    if User.query.count() == 0:
        default_pw = os.environ.get('VAULT_PASSWORD', 'vault1234')
        u = User(username=os.environ.get('VAULT_USER', 'admin'))
        u.set_password(default_pw)
        db.session.add(u)
        print(f"[Vault] Erster Start: Benutzer '{u.username}' mit Passwort '{default_pw}' erstellt.")
        print(f"[Vault] Passwort bitte sofort in den Einstellungen ändern!")

    # Upsert categories by name (safe with multiple workers)
    defaults = [
        dict(name='Gehalt',              emoji='💼', color='#22d3a0', type='income',  income_type='regular',   budget_limit=0),
        dict(name='Freelance',            emoji='💻', color='#38bdf8', type='income',  income_type='regular',   budget_limit=0),
        dict(name='Investitionen',        emoji='📈', color='#34d399', type='income',  income_type='regular',   budget_limit=0),
        dict(name='Ebay / Verkauf',       emoji='🛍️', color='#a3e635', type='income',  income_type='unplanned', budget_limit=0),
        dict(name='Geschenk / Sonstiges', emoji='🎁', color='#fb923c', type='income',  income_type='unplanned', budget_limit=0),
        dict(name='Miete',                emoji='🏠', color='#f87171', type='expense', income_type='regular',   budget_limit=800),
        dict(name='Lebensmittel',         emoji='🛒', color='#fbbf24', type='expense', income_type='regular',   budget_limit=400),
        dict(name='Transport',            emoji='🚗', color='#60a5fa', type='expense', income_type='regular',   budget_limit=150),
        dict(name='Restaurant',           emoji='🍽️', color='#fb923c', type='expense', income_type='regular',   budget_limit=200),
        dict(name='Unterhaltung',         emoji='🎮', color='#c084fc', type='expense', income_type='regular',   budget_limit=100),
        dict(name='Gesundheit',           emoji='⚕️',  color='#2dd4bf', type='expense', income_type='regular',   budget_limit=100),
        dict(name='Kleidung',             emoji='👗', color='#f472b6', type='expense', income_type='regular',   budget_limit=150),
        dict(name='Abonnements',          emoji='📱', color='#f43f5e', type='expense', income_type='regular',   budget_limit=50),
        dict(name='Haushalt',             emoji='🏡', color='#94a3b8', type='expense', income_type='regular',   budget_limit=100),
        dict(name='Bildung',              emoji='📚', color='#818cf8', type='expense', income_type='regular',   budget_limit=100),
        dict(name='Kontostandanpassung',  emoji='⚖️',  color='#64748b', type='both',    income_type='regular',   budget_limit=0),
    ]
    for d in defaults:
        if not Category.query.filter_by(name=d['name']).first():
            db.session.add(Category(**d))

    # Settings (only if key doesn't exist)
    setting_defaults = [
        ('currency', '€'), ('currency_position', 'after'), ('theme', 'dark'),
        ('warning_threshold', '75'), ('danger_threshold', '90'), ('monthly_savings_goal', '0'),
    ]
    for key, value in setting_defaults:
        if not AppSettings.query.filter_by(key=key).first():
            db.session.add(AppSettings(key=key, value=value))

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()  # another worker beat us to it — that's fine
