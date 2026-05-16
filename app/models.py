import json as _json
from datetime import datetime, date, timedelta
from flask_login import UserMixin
from app import db


class User(UserMixin, db.Model):
    __tablename__ = 'user'
    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(80),  unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        import bcrypt
        self.password_hash = bcrypt.hashpw(
            password.encode('utf-8'), bcrypt.gensalt(rounds=12)
        ).decode('utf-8')

    def check_password(self, password):
        import bcrypt
        try:
            return bcrypt.checkpw(password.encode('utf-8'),
                                  self.password_hash.encode('utf-8'))
        except Exception:
            return False


class Transaction(db.Model):
    __tablename__ = 'transaction'
    id           = db.Column(db.Integer, primary_key=True)
    type         = db.Column(db.String(10), nullable=False)
    amount       = db.Column(db.Float, nullable=False)
    description  = db.Column(db.String(500), default='')
    emoji        = db.Column(db.String(20),  default='')
    image_path   = db.Column(db.String(255), default='')
    category_id  = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=True)
    category     = db.relationship('Category', backref=db.backref('transactions', lazy=True))
    date         = db.Column(db.Date, nullable=False, default=date.today)
    budget_month = db.Column(db.String(7),   nullable=True)   # 'YYYY-MM' override for budget
    tags         = db.Column(db.String(500), default='')      # comma-separated, e.g. "urlaub,arbeit"
    note         = db.Column(db.Text, default='')
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)

    def effective_budget_month(self):
        """Return YYYY-MM string used for budget calculations."""
        if self.budget_month:
            return self.budget_month
        return self.date.strftime('%Y-%m')

    def _clean_desc(self):
        """Strip leading dates and amounts that CSV parsers sometimes leave in descriptions."""
        import re
        d = self.description or ''
        # Remove leading date patterns like 29.04.2025 or 2025-04-29
        d = re.sub(r'^[\d]{2}[./\-][\d]{2}[./\-][\d]{2,4}\s*[-–]?\s*', '', d)
        d = re.sub(r'^[\d]{4}-[\d]{2}-[\d]{2}\s*[-–]?\s*', '', d)
        # Remove leading amount patterns like 1.234,56 or 1234.56
        d = re.sub(r'^[+\-]?\s*[\d.,]+\s*(EUR|€)?\s*[-–]?\s*', '', d)
        return d.strip() or self.description or 'Buchung'

    def to_dict(self):
        return {
            'id': self.id, 'type': self.type, 'amount': self.amount,
            'description': self.description, 'emoji': self.emoji,
            'image_path': self.image_path, 'category_id': self.category_id,
            'category_name':  self.category.name  if self.category else 'Ohne Kategorie',
            'category_emoji': self.category.emoji if self.category else '📁',
            'category_color': self.category.color if self.category else '#666',
            'date': self.date.strftime('%Y-%m-%d'),
            'date_display': self.date.strftime('%d.%m.%Y'),
            'budget_month': self.budget_month or '',
            'tags': [t.strip() for t in (self.tags or '').split(',') if t.strip()],
            'note': self.note,
            'display_desc': self._clean_desc(),
        }


class Category(db.Model):
    __tablename__ = 'category'
    id           = db.Column(db.Integer, primary_key=True)
    name         = db.Column(db.String(100), nullable=False)
    emoji        = db.Column(db.String(20),  default='📁')
    color        = db.Column(db.String(20),  default='#666666')
    type         = db.Column(db.String(10),  default='expense')
    budget_limit = db.Column(db.Float, default=0)
    income_type  = db.Column(db.String(20),  default='regular')  # regular | unplanned

    def to_dict(self):
        return {
            'id': self.id, 'name': self.name, 'emoji': self.emoji,
            'color': self.color, 'type': self.type,
            'budget_limit': self.budget_limit, 'income_type': self.income_type,
        }


class AppSettings(db.Model):
    __tablename__ = 'app_settings'
    id    = db.Column(db.Integer, primary_key=True)
    key   = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.String(500), default='')

    @staticmethod
    def get(key, default=''):
        s = AppSettings.query.filter_by(key=key).first()
        return s.value if s else default

    @staticmethod
    def set(key, value):
        s = AppSettings.query.filter_by(key=key).first()
        if s:
            s.value = str(value)
        else:
            db.session.add(AppSettings(key=key, value=str(value)))
        db.session.commit()


class RecurringTransaction(db.Model):
    __tablename__ = 'recurring_transaction'
    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(200), nullable=False)
    type        = db.Column(db.String(10),  nullable=False)
    amount      = db.Column(db.Float, nullable=False)
    emoji       = db.Column(db.String(20),  default='🔄')
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=True)
    category    = db.relationship('Category', backref='recurring_txs')
    frequency   = db.Column(db.String(20),  nullable=False, default='monthly')
    start_date  = db.Column(db.Date, nullable=False, default=date.today)
    next_run    = db.Column(db.Date, nullable=True)
    end_date    = db.Column(db.Date, nullable=True)
    active      = db.Column(db.Boolean, default=True)
    note        = db.Column(db.Text, default='')

    FREQ_LABELS = {
        'daily': 'Täglich', 'weekly': 'Wöchentlich', 'biweekly': '2-wöchentlich',
        'monthly': 'Monatlich', 'quarterly': 'Vierteljährlich', 'yearly': 'Jährlich',
    }

    def compute_next(self, from_date=None):
        from dateutil.relativedelta import relativedelta
        base = from_date or (self.next_run or self.start_date)
        m = {
            'daily':     lambda d: d + timedelta(days=1),
            'weekly':    lambda d: d + timedelta(weeks=1),
            'biweekly':  lambda d: d + timedelta(weeks=2),
            'monthly':   lambda d: d + relativedelta(months=1),
            'quarterly': lambda d: d + relativedelta(months=3),
            'yearly':    lambda d: d + relativedelta(years=1),
        }
        return m.get(self.frequency, m['monthly'])(base)

    def to_dict(self):
        return {
            'id': self.id, 'name': self.name, 'type': self.type,
            'amount': self.amount, 'emoji': self.emoji,
            'category_id': self.category_id,
            'category_name': self.category.name if self.category else None,
            'frequency': self.frequency,
            'frequency_label': self.FREQ_LABELS.get(self.frequency, self.frequency),
            'start_date': self.start_date.strftime('%Y-%m-%d'),
            'next_run':   self.next_run.strftime('%Y-%m-%d') if self.next_run else None,
            'end_date':   self.end_date.strftime('%Y-%m-%d') if self.end_date else None,
            'active': self.active, 'note': self.note,
        }


class Document(db.Model):
    __tablename__ = 'document'
    id             = db.Column(db.Integer, primary_key=True)
    filename       = db.Column(db.String(255), nullable=False)
    original_name  = db.Column(db.String(255), nullable=False)
    doc_type       = db.Column(db.String(50),  default='bank_statement')
    upload_date    = db.Column(db.DateTime, default=datetime.utcnow)
    status         = db.Column(db.String(20),  default='pending')
    raw_text       = db.Column(db.Text, default='')
    extracted_json = db.Column(db.Text, default='[]')
    page_count     = db.Column(db.Integer, default=1)
    notes          = db.Column(db.Text, default='')

    DOC_TYPES = {'bank_statement': '🏦 Kontoauszug', 'invoice': '🧾 Rechnung',
                 'receipt': '🛒 Kassenbon', 'other': '📄 Sonstiges'}
    STATUSES  = {'pending': 'Ausstehend', 'scanned': 'Gescannt',
                 'imported': 'Importiert', 'archived': 'Archiviert'}

    def get_extracted(self):
        try:
            return _json.loads(self.extracted_json or '[]')
        except Exception:
            return []

    def to_dict(self):
        return {
            'id': self.id, 'filename': self.filename,
            'original_name': self.original_name, 'doc_type': self.doc_type,
            'doc_type_label': self.DOC_TYPES.get(self.doc_type, self.doc_type),
            'upload_date': self.upload_date.strftime('%d.%m.%Y %H:%M'),
            'status': self.status, 'status_label': self.STATUSES.get(self.status, self.status),
            'page_count': self.page_count, 'notes': self.notes,
            'tx_count': len(self.get_extracted()),
        }


class SavingsGoal(db.Model):
    __tablename__ = 'savings_goal'
    id             = db.Column(db.Integer, primary_key=True)
    name           = db.Column(db.String(200), nullable=False)
    emoji          = db.Column(db.String(20),  default='🎯')
    color          = db.Column(db.String(20),  default='#22d3a0')
    target_amount  = db.Column(db.Float, nullable=False)
    current_amount = db.Column(db.Float, default=0)
    deadline       = db.Column(db.Date, nullable=True)
    notes          = db.Column(db.Text, default='')
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)

    def pct(self):
        return round(min(self.current_amount / self.target_amount * 100, 100), 1) if self.target_amount else 0

    def to_dict(self):
        from datetime import date as _date
        days_left = None
        if self.deadline:
            days_left = (self.deadline - _date.today()).days
        return {
            'id': self.id, 'name': self.name, 'emoji': self.emoji, 'color': self.color,
            'target_amount': self.target_amount, 'current_amount': self.current_amount,
            'deadline': self.deadline.strftime('%Y-%m-%d') if self.deadline else None,
            'days_left': days_left, 'notes': self.notes, 'pct': self.pct(),
            'remaining': round(max(self.target_amount - self.current_amount, 0), 2),
        }


class QuickEntry(db.Model):
    __tablename__ = 'quick_entry'
    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(100), nullable=False)
    emoji       = db.Column(db.String(20),  default='⚡')
    amount      = db.Column(db.Float, nullable=False)
    type        = db.Column(db.String(10),  default='expense')
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=True)
    category    = db.relationship('Category')
    note        = db.Column(db.String(200), default='')

    def to_dict(self):
        return {
            'id': self.id, 'name': self.name, 'emoji': self.emoji,
            'amount': self.amount, 'type': self.type,
            'category_id': self.category_id,
            'category_name': self.category.name if self.category else None,
            'note': self.note,
        }


# Flask-Login user loader
from app import login_manager

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
