import os, csv, io, json, re
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
from flask import (Blueprint, render_template, request, jsonify,
                   current_app, send_file)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from sqlalchemy import func
from app import db
from app.models import Transaction, Category, AppSettings, RecurringTransaction, Document, SavingsGoal, QuickEntry, User
# ── German month names ────────────────────────────────────────────────
_DE_MONTHS = {
    1:'Januar', 2:'Februar', 3:'März', 4:'April', 5:'Mai', 6:'Juni',
    7:'Juli', 8:'August', 9:'September', 10:'Oktober', 11:'November', 12:'Dezember'
}
_DE_MONTHS_SHORT = {
    1:'Jan', 2:'Feb', 3:'Mär', 4:'Apr', 5:'Mai', 6:'Jun',
    7:'Jul', 8:'Aug', 9:'Sep', 10:'Okt', 11:'Nov', 12:'Dez'
}
def de_month(d):
    """Returns 'Mai 2026' style German month+year."""
    return f"{_DE_MONTHS[d.month]} {d.year}"
def de_month_short(d):
    """Returns 'Mai 26' style short German."""
    return f"{_DE_MONTHS_SHORT[d.month]} {str(d.year)[2:]}"



main = Blueprint('main', __name__)

ALLOWED_IMG = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
ALLOWED_DOC = {'csv', 'pdf', 'png', 'jpg', 'jpeg'}


def _ext(filename):
    return filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''


def get_settings():
    return {s.key: s.value for s in AppSettings.query.all()}


def fmt_amount(amount, cfg):
    cur = cfg.get('currency', '€')
    pos = cfg.get('currency_position', 'after')
    v = f"{amount:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    return f"{cur}{v}" if pos == 'before' else f"{v} {cur}"


# ─────────────────── RECURRING HELPER ───────────────────
@login_required
def process_due_recurring():
    today = date.today()
    due = RecurringTransaction.query.filter(
        RecurringTransaction.active == True,
        RecurringTransaction.next_run <= today,
    ).all()
    created = 0
    for r in due:
        if r.end_date and today > r.end_date:
            r.active = False
            continue
        t = Transaction(
            type=r.type, amount=r.amount,
            description=r.name, emoji=r.emoji,
            category_id=r.category_id, date=r.next_run,
            note=f'Wiederkehrend ({r.FREQ_LABELS.get(r.frequency, "")})',
        )
        db.session.add(t)
        r.next_run = r.compute_next(r.next_run)
        created += 1
    if created or due:
        db.session.commit()
    return created


# ─────────────────── PAGE ROUTES ───────────────────

@main.route('/')
@login_required
def dashboard():
    cfg = get_settings()
    today = date.today()
    som = today.replace(day=1)
    budget_ym = today.strftime('%Y-%m')

    auto = process_due_recurring()

    def month_sum(tx_type):
        """Sum transactions for current month, respecting budget_month override."""
        return db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.type == tx_type,
            db.or_(
                Transaction.budget_month == budget_ym,
                db.and_(
                    db.or_(Transaction.budget_month == None, Transaction.budget_month == ''),
                    Transaction.date >= som, Transaction.date <= today
                )
            )
        ).scalar() or 0

    income_m  = month_sum('income')
    expense_m = month_sum('expense')
    balance   = income_m - expense_m   # this month's balance
    savings_rate = round((income_m - expense_m) / income_m * 100, 1) if income_m > 0 else 0
    recent = Transaction.query.order_by(Transaction.date.desc(), Transaction.created_at.desc()).limit(8).all()

    warn_th = float(cfg.get('warning_threshold', 75))
    dang_th = float(cfg.get('danger_threshold', 90))
    warnings = []
    for cat in Category.query.filter(Category.budget_limit > 0).all():
        spent = db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.category_id == cat.id, Transaction.type == 'expense',
            db.or_(
                Transaction.budget_month == budget_ym,
                db.and_(
                    db.or_(Transaction.budget_month == None, Transaction.budget_month == ''),
                    Transaction.date >= som, Transaction.date <= today
                )
            )
        ).scalar() or 0
        pct = spent / cat.budget_limit * 100 if cat.budget_limit else 0
        if pct >= warn_th:
            status = 'over' if spent > cat.budget_limit else ('danger' if pct >= dang_th else 'warning')
            warnings.append(dict(category=cat.name, emoji=cat.emoji, color=cat.color,
                                 spent=spent, limit=cat.budget_limit, pct=round(pct,1), status=status))
    warnings.sort(key=lambda x: x['pct'], reverse=True)

    return render_template('dashboard.html', cfg=cfg, income=income_m, expenses=expense_m,
        balance=balance, savings_rate=savings_rate, recent=recent, warnings=warnings,
        month_name=de_month(today), auto_created=auto)


@main.route('/transactions')
@login_required
def transactions():
    cats = Category.query.order_by(Category.name).all()
    return render_template('transactions.html', cfg=get_settings(), categories=cats)


@main.route('/analytics')
@login_required
def analytics():
    return render_template('analytics.html', cfg=get_settings())


@main.route('/budget')
@login_required
def budget():
    cfg = get_settings()
    today = date.today()
    som = today.replace(day=1)
    budget_ym = today.strftime('%Y-%m')   # current month as YYYY-MM
    warn_th = float(cfg.get('warning_threshold', 75))
    dang_th = float(cfg.get('danger_threshold', 90))

    budget_data = []
    for cat in Category.query.filter(Category.budget_limit > 0, Category.type.in_(['expense','both'])).all():
        # Count expenses where effective budget month = current month
        # Either budget_month matches OR (budget_month is null AND date is in current month)
        spent = db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.category_id == cat.id,
            Transaction.type == 'expense',
            db.or_(
                Transaction.budget_month == budget_ym,
                db.and_(
                    db.or_(Transaction.budget_month == None, Transaction.budget_month == ''),
                    Transaction.date >= som, Transaction.date <= today
                )
            )
        ).scalar() or 0

        pct = min(spent / cat.budget_limit * 100, 150) if cat.budget_limit else 0
        # Status: over = spent > limit (into minus), danger = >=dang_th, warning = >=warn_th
        if spent > cat.budget_limit:
            status = 'over'
        elif pct >= dang_th:
            status = 'danger'
        elif pct >= 100:
            status = 'full'   # exactly at limit → yellow
        elif pct >= warn_th:
            status = 'warning'
        else:
            status = 'ok'

        budget_data.append(dict(category=cat.to_dict(), spent=round(spent,2),
                                pct=round(pct,1), remaining=round(cat.budget_limit-spent,2),
                                status=status))
    budget_data.sort(key=lambda x: x['pct'], reverse=True)

    cats_exp     = [c.to_dict() for c in Category.query.filter(Category.type.in_(['expense','both'])).order_by(Category.name).all()]
    total_budget = sum(b['category']['budget_limit'] for b in budget_data)
    total_spent  = sum(b['spent'] for b in budget_data)

    return render_template('budget.html', cfg=cfg, budget_data=budget_data,
        total_budget=total_budget, total_spent=total_spent,
        categories=cats_exp, month_name=de_month(today),
        budget_ym=budget_ym)


@main.route('/settings')
@login_required
def settings():
    cats      = Category.query.order_by(Category.name).all()
    recurring = RecurringTransaction.query.order_by(RecurringTransaction.name).all()
    return render_template('settings.html', cfg=get_settings(), categories=cats, recurring=recurring)


@main.route('/documents')
@login_required
def documents_page():
    docs = Document.query.order_by(Document.upload_date.desc()).all()
    cats = [c.to_dict() for c in Category.query.order_by(Category.name).all()]
    return render_template('documents.html', cfg=get_settings(), documents=docs, categories=cats)


# ─────────────────── TRANSACTIONS API ───────────────────

@main.route('/api/transactions', methods=['GET'])
@login_required
def api_transactions_get():
    page=request.args.get('page',1,type=int); per_page=request.args.get('per_page',50,type=int)
    tf=request.args.get('type',''); cf=request.args.get('category',0,type=int)
    df=request.args.get('date_from',''); dt=request.args.get('date_to',''); s=request.args.get('search','')
    tag=request.args.get('tag','')

    q = Transaction.query
    if tf in ('income','expense'): q=q.filter(Transaction.type==tf)
    if cf: q=q.filter(Transaction.category_id==cf)
    if df: q=q.filter(Transaction.date>=datetime.strptime(df,'%Y-%m-%d').date())
    if dt: q=q.filter(Transaction.date<=datetime.strptime(dt,'%Y-%m-%d').date())
    if s:  q=q.filter(Transaction.description.ilike(f'%{s}%'))
    if tag: q=q.filter(Transaction.tags.ilike(f'%{tag}%'))
    q=q.order_by(Transaction.date.desc(), Transaction.created_at.desc())
    total=q.count(); items=q.offset((page-1)*per_page).limit(per_page).all()
    return jsonify(dict(transactions=[t.to_dict() for t in items], total=total,
                        pages=(total+per_page-1)//per_page, page=page))


@main.route('/api/transactions', methods=['POST'])
@login_required
def api_transactions_post():
    d=request.get_json()
    try:
        t=Transaction(type=d['type'],amount=float(d['amount']),description=d.get('description',''),
            emoji=d.get('emoji',''),image_path=d.get('image_path',''),
            category_id=d.get('category_id') or None,
            date=datetime.strptime(d['date'],'%Y-%m-%d').date(),
            budget_month=d.get('budget_month') or None,
            tags=','.join(t.strip().lstrip('#') for t in d.get('tags',[]) if t.strip()),
            note=d.get('note',''))
        db.session.add(t); db.session.commit()
        return jsonify(dict(success=True, transaction=t.to_dict()))
    except Exception as e:
        db.session.rollback(); return jsonify(dict(success=False, error=str(e))), 400


@main.route('/api/transactions/<int:tid>', methods=['GET'])
@login_required
def api_transaction_get(tid):
    return jsonify(Transaction.query.get_or_404(tid).to_dict())


@main.route('/api/transactions/<int:tid>', methods=['PUT'])
@login_required
def api_transaction_put(tid):
    t=Transaction.query.get_or_404(tid); d=request.get_json()
    try:
        t.type=d.get('type',t.type); t.amount=float(d.get('amount',t.amount))
        t.description=d.get('description',t.description); t.emoji=d.get('emoji',t.emoji)
        t.image_path=d.get('image_path',t.image_path); t.category_id=d.get('category_id') or None
        t.note=d.get('note',t.note); t.budget_month=d.get('budget_month') or None
        if 'tags' in d:
            t.tags=','.join(x.strip().lstrip('#') for x in d['tags'] if x.strip())
        if 'date' in d: t.date=datetime.strptime(d['date'],'%Y-%m-%d').date()
        db.session.commit(); return jsonify(dict(success=True, transaction=t.to_dict()))
    except Exception as e:
        db.session.rollback(); return jsonify(dict(success=False, error=str(e))), 400


@main.route('/api/transactions/<int:tid>', methods=['DELETE'])
@login_required
def api_transaction_delete(tid):
    t=Transaction.query.get_or_404(tid); db.session.delete(t); db.session.commit()
    return jsonify(dict(success=True))


@main.route('/api/upload', methods=['POST'])
@login_required
def api_upload():
    if 'file' not in request.files: return jsonify(dict(success=False,error='Keine Datei')),400
    f=request.files['file']
    if not f.filename or _ext(f.filename) not in ALLOWED_IMG:
        return jsonify(dict(success=False,error='Nicht erlaubter Dateityp')),400
    fname=datetime.now().strftime('%Y%m%d_%H%M%S_')+secure_filename(f.filename)
    f.save(os.path.join(current_app.config['UPLOAD_FOLDER'],fname))
    return jsonify(dict(success=True, path=f'/static/uploads/{fname}'))


# ─────────────────── CATEGORIES API ───────────────────

@main.route('/api/categories', methods=['GET'])
@login_required
def api_categories_get():
    tf=request.args.get('type','')
    q=Category.query
    if tf: q=q.filter(db.or_(Category.type==tf, Category.type=='both'))
    return jsonify([c.to_dict() for c in q.order_by(Category.name).all()])


@main.route('/api/categories', methods=['POST'])
@login_required
def api_categories_post():
    d=request.get_json()
    try:
        c=Category(name=d['name'],emoji=d.get('emoji','📁'),color=d.get('color','#666666'),
            type=d.get('type','expense'),budget_limit=float(d.get('budget_limit',0)),
            income_type=d.get('income_type','regular'))
        db.session.add(c); db.session.commit()
        return jsonify(dict(success=True, category=c.to_dict()))
    except Exception as e:
        db.session.rollback(); return jsonify(dict(success=False,error=str(e))),400


@main.route('/api/admin/dedup-categories', methods=['POST'])
@login_required
def api_dedup_categories():
    """Remove duplicate categories, keeping the one with the lowest ID per name."""
    seen = {}
    removed = 0
    for cat in Category.query.order_by(Category.id).all():
        if cat.name in seen:
            # Re-assign transactions to the keeper
            Transaction.query.filter_by(category_id=cat.id).update({'category_id': seen[cat.name]})
            db.session.delete(cat)
            removed += 1
        else:
            seen[cat.name] = cat.id
    db.session.commit()
    return jsonify(dict(success=True, removed=removed))


@main.route('/api/categories/<int:cid>', methods=['PUT'])
@login_required
def api_category_put(cid):
    c=Category.query.get_or_404(cid); d=request.get_json()
    try:
        c.name=d.get('name',c.name); c.emoji=d.get('emoji',c.emoji); c.color=d.get('color',c.color)
        c.type=d.get('type',c.type); c.budget_limit=float(d.get('budget_limit',c.budget_limit))
        c.income_type=d.get('income_type',c.income_type)
        db.session.commit(); return jsonify(dict(success=True, category=c.to_dict()))
    except Exception as e:
        db.session.rollback(); return jsonify(dict(success=False,error=str(e))),400


@main.route('/api/categories/<int:cid>', methods=['DELETE'])
@login_required
def api_category_delete(cid):
    c=Category.query.get_or_404(cid)
    Transaction.query.filter_by(category_id=cid).update({'category_id':None})
    db.session.delete(c); db.session.commit()
    return jsonify(dict(success=True))


# ─────────────────── SETTINGS API ───────────────────

@main.route('/api/settings', methods=['GET'])
@login_required
def api_settings_get():
    return jsonify(get_settings())


@main.route('/api/settings', methods=['POST'])
@login_required
def api_settings_post():
    from flask import session as flask_session
    d = request.get_json() or {}
    try:
        # Handle username change
        if 'username' in d:
            new_name = str(d.pop('username')).strip()
            if len(new_name) < 3:
                return jsonify(dict(success=False, error='Benutzername muss mindestens 3 Zeichen haben.')), 400
            if new_name != current_user.username:
                existing = User.query.filter_by(username=new_name).first()
                if existing:
                    return jsonify(dict(success=False, error='Benutzername bereits vergeben.')), 400
                current_user.username = new_name
                db.session.commit()

        # Handle password change
        if 'password' in d:
            new_pw = str(d.pop('password'))
            if len(new_pw) < 8:
                return jsonify(dict(success=False, error='Passwort muss mindestens 8 Zeichen haben.')), 400
            current_user.set_password(new_pw)
            db.session.commit()

        # Handle session_timeout (days; 0 = browser session)
        if 'session_timeout' in d:
            days = int(d['session_timeout'])
            AppSettings.set('session_timeout', str(days))
            # Apply immediately to current session
            from datetime import timedelta as _td
            if days > 0:
                flask_session.permanent = True
                from flask import current_app
                current_app.permanent_session_lifetime = _td(days=days)
            else:
                flask_session.permanent = False
            d.pop('session_timeout')

        # Save remaining general settings
        ALLOWED = {'currency','currency_position','monthly_savings_goal',
                   'warning_threshold','danger_threshold','theme'}
        for k, v in d.items():
            if k in ALLOWED:
                AppSettings.set(k, str(v))

        return jsonify(dict(success=True, username=current_user.username))
    except Exception as e:
        return jsonify(dict(success=False, error=str(e))), 400


@main.route('/api/security', methods=['GET'])
@login_required
def api_security_get():
    cfg = get_settings()
    return jsonify(dict(
        username=current_user.username,
        session_timeout=int(cfg.get('session_timeout', 30)),
    ))


# ─────────────────── ANALYTICS API ───────────────────

@main.route('/api/analytics')
@login_required
def api_analytics():
    period = request.args.get('period', 'year')
    today  = date.today()

    # ── Date range ──
    if period == '7days':
        start  = today - timedelta(days=6)
        mode   = 'daily'
    elif period == 'month':
        start  = today.replace(day=1)   # current month from 1st
        mode   = 'daily'
    elif period == '1month':
        start  = today - timedelta(days=29)
        mode   = 'daily'
    elif period == '3months':
        start  = (today - relativedelta(months=2)).replace(day=1)
        mode   = 'monthly'
    elif period == 'year':
        start  = today.replace(month=1, day=1)
        mode   = 'monthly'
    else:
        first  = Transaction.query.order_by(Transaction.date).first()
        start  = first.date.replace(day=1) if first else today.replace(day=1)
        mode   = 'monthly'

    # ── Build time-series ──
    series = []
    if mode == 'daily':
        for i in range((today - start).days + 1):
            d = start + timedelta(days=i)
            inc = db.session.query(func.sum(Transaction.amount)).filter(
                Transaction.type=='income',  Transaction.date==d).scalar() or 0
            exp = db.session.query(func.sum(Transaction.amount)).filter(
                Transaction.type=='expense', Transaction.date==d).scalar() or 0
            series.append(dict(label=d.strftime('%d.%m'), income=round(inc,2),
                               expenses=round(exp,2), balance=round(inc-exp,2)))
    else:
        diff   = relativedelta(today, start)
        months = diff.years * 12 + diff.months + 1
        for i in range(months):
            ms = (start + relativedelta(months=i)).replace(day=1)
            me = (ms + relativedelta(months=1)) - timedelta(days=1)
            inc = db.session.query(func.sum(Transaction.amount)).filter(
                Transaction.type=='income',  Transaction.date>=ms, Transaction.date<=me).scalar() or 0
            exp = db.session.query(func.sum(Transaction.amount)).filter(
                Transaction.type=='expense', Transaction.date>=ms, Transaction.date<=me).scalar() or 0
            series.append(dict(label=de_month_short(ms), income=round(inc,2),
                               expenses=round(exp,2), balance=round(inc-exp,2)))

    # ── Category breakdown ──
    rows = db.session.query(Category.name, Category.emoji, Category.color,
        func.sum(Transaction.amount).label('total')).join(
        Transaction, Transaction.category_id==Category.id).filter(
        Transaction.type=='expense', Transaction.date>=start, Transaction.date<=today
    ).group_by(Category.id).order_by(func.sum(Transaction.amount).desc()).all()
    tot_exp = sum(r.total for r in rows)
    cat_data = [dict(name=r.name, emoji=r.emoji, color=r.color, amount=round(r.total,2),
                     percentage=round(r.total/tot_exp*100,1) if tot_exp else 0) for r in rows]

    # ── Income category breakdown ──
    inc_rows = db.session.query(Category.name, Category.emoji, Category.color,
        func.sum(Transaction.amount).label('total')).join(
        Transaction, Transaction.category_id==Category.id).filter(
        Transaction.type=='income', Transaction.date>=start, Transaction.date<=today
    ).group_by(Category.id).order_by(func.sum(Transaction.amount).desc()).all()
    tot_inc_cat = sum(r.total for r in inc_rows)
    inc_cat_data = [dict(name=r.name, emoji=r.emoji, color=r.color, amount=round(r.total,2),
                         percentage=round(r.total/tot_inc_cat*100,1) if tot_inc_cat else 0) for r in inc_rows]

    # ── Daily spending (for 7-day sparklines) ──
    ti = sum(m['income'] for m in series)
    te = sum(m['expenses'] for m in series)

    return jsonify(dict(
        series=series,
        monthly_data=series,  # backwards compat
        category_data=cat_data,
        income_category_data=inc_cat_data,
        mode=mode,
        summary=dict(total_income=round(ti,2), total_expenses=round(te,2),
                     balance=round(ti-te,2),
                     savings_rate=round((ti-te)/ti*100,1) if ti else 0)
    ))


@main.route('/api/budget-status')
@login_required
def api_budget_status():
    cfg=get_settings(); today=date.today(); som=today.replace(day=1)
    warn_th=float(cfg.get('warning_threshold',75)); dang_th=float(cfg.get('danger_threshold',90))
    result=[]
    for cat in Category.query.filter(Category.budget_limit>0).all():
        spent=db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.category_id==cat.id,Transaction.type=='expense',
            Transaction.date>=som,Transaction.date<=today).scalar() or 0
        pct=spent/cat.budget_limit*100 if cat.budget_limit else 0
        status='over' if pct>=100 else ('danger' if pct>=dang_th else ('warning' if pct>=warn_th else 'ok'))
        result.append(dict(id=cat.id,name=cat.name,emoji=cat.emoji,color=cat.color,
            spent=round(spent,2),limit=cat.budget_limit,pct=round(pct,1),
            remaining=max(round(cat.budget_limit-spent,2),0),status=status))
    result.sort(key=lambda x:x['pct'],reverse=True)
    return jsonify(result)


@main.route('/api/export')
@login_required
def api_export():
    fmt=request.args.get('format','csv')
    txs=Transaction.query.order_by(Transaction.date.desc()).all()
    if fmt=='json': return jsonify([t.to_dict() for t in txs])
    out=io.StringIO(); w=csv.writer(out,delimiter=';')
    w.writerow(['ID','Datum','Typ','Betrag','Beschreibung','Kategorie','Emoji','Notiz'])
    for t in txs:
        w.writerow([t.id,t.date.strftime('%d.%m.%Y'),'Einnahme' if t.type=='income' else 'Ausgabe',
            f"{t.amount:.2f}",t.description,t.category.name if t.category else '',t.emoji,t.note])
    out.seek(0)
    return send_file(io.BytesIO(out.getvalue().encode('utf-8-sig')),mimetype='text/csv',
        as_attachment=True,download_name=f'finanzen_{datetime.now().strftime("%Y%m%d")}.csv')


# ─────────────────── RECURRING API ───────────────────

@main.route('/api/recurring', methods=['GET'])
@login_required
def api_recurring_get():
    items=RecurringTransaction.query.order_by(RecurringTransaction.name).all()
    return jsonify([r.to_dict() for r in items])


@main.route('/api/recurring', methods=['POST'])
@login_required
def api_recurring_post():
    d=request.get_json()
    try:
        start=datetime.strptime(d['start_date'],'%Y-%m-%d').date()
        r=RecurringTransaction(name=d['name'],type=d['type'],amount=float(d['amount']),
            emoji=d.get('emoji','🔄'),category_id=d.get('category_id') or None,
            frequency=d.get('frequency','monthly'),start_date=start,
            end_date=datetime.strptime(d['end_date'],'%Y-%m-%d').date() if d.get('end_date') else None,
            active=d.get('active',True),note=d.get('note',''))
        r.next_run=r.compute_next(start)
        db.session.add(r); db.session.commit()
        return jsonify(dict(success=True,recurring=r.to_dict()))
    except Exception as e:
        db.session.rollback(); return jsonify(dict(success=False,error=str(e))),400


@main.route('/api/recurring/<int:rid>', methods=['PUT'])
@login_required
def api_recurring_put(rid):
    r=RecurringTransaction.query.get_or_404(rid); d=request.get_json()
    try:
        r.name=d.get('name',r.name); r.type=d.get('type',r.type)
        r.amount=float(d.get('amount',r.amount)); r.emoji=d.get('emoji',r.emoji)
        r.category_id=d.get('category_id') or None; r.frequency=d.get('frequency',r.frequency)
        r.active=d.get('active',r.active); r.note=d.get('note',r.note)
        if d.get('start_date'): r.start_date=datetime.strptime(d['start_date'],'%Y-%m-%d').date()
        r.end_date=datetime.strptime(d['end_date'],'%Y-%m-%d').date() if d.get('end_date') else None
        db.session.commit(); return jsonify(dict(success=True,recurring=r.to_dict()))
    except Exception as e:
        db.session.rollback(); return jsonify(dict(success=False,error=str(e))),400


@main.route('/api/recurring/<int:rid>', methods=['DELETE'])
@login_required
def api_recurring_delete(rid):
    r=RecurringTransaction.query.get_or_404(rid)
    db.session.delete(r); db.session.commit()
    return jsonify(dict(success=True))


# ─────────────────── DOCUMENTS API ───────────────────

@main.route('/api/documents/upload', methods=['POST'])
@login_required
def api_documents_upload():
    if 'file' not in request.files: return jsonify(dict(success=False,error='Keine Datei')),400
    f=request.files['file']
    if not f.filename or _ext(f.filename) not in ALLOWED_DOC:
        return jsonify(dict(success=False,error=f'Dateiformat nicht unterstützt: .{_ext(f.filename or "")} (erlaubt: CSV, PDF, PNG, JPG)')),400
    fname=datetime.now().strftime('%Y%m%d_%H%M%S_')+secure_filename(f.filename)
    filepath=os.path.join(current_app.config['DOCS_FOLDER'],fname)
    f.save(filepath)
    doc=Document(filename=fname,original_name=f.filename,
                 doc_type=request.form.get('doc_type','bank_statement'),status='pending')
    db.session.add(doc); db.session.commit()
    try:
        result=_scan_document(filepath)
    except Exception as scan_err:
        import traceback as _tb
        tb_str = _tb.format_exc()
        current_app.logger.error(f'[SCAN ERROR] {scan_err}\n{tb_str}')
        doc.status='error'; db.session.commit()
        # Return full error in dev, short in prod
        err_detail = str(scan_err)
        return jsonify(dict(success=False, 
                           error=f'Scan-Fehler: {err_detail}',
                           debug=tb_str.split("\n")[-3:-1],
                           transactions=[], document=doc.to_dict()))
    doc.raw_text=result.get('raw_text','')
    doc.extracted_json=json.dumps(result.get('transactions',[]),ensure_ascii=False)
    doc.page_count=result.get('pages',1); doc.status='scanned'
    db.session.commit()
    return jsonify(dict(success=True, document=doc.to_dict(),
                        transactions=result.get('transactions',[]),
                        info=result.get('info', '')))


@main.route('/api/documents/<int:did>/extracted')
@login_required
def api_documents_extracted(did):
    doc=Document.query.get_or_404(did)
    d = doc.to_dict()
    d['raw_text'] = doc.raw_text or ''
    return jsonify(dict(document=d, transactions=doc.get_extracted()))


@main.route('/api/documents/<int:did>/import', methods=['POST'])
@login_required
def api_documents_import(did):
    doc=Document.query.get_or_404(did); d=request.get_json()

    # For invoices/receipts: make the file web-accessible so it can attach to transaction
    attached_path = ''
    is_attachable = doc.doc_type in ('invoice', 'receipt')
    if is_attachable:
        src = os.path.join(current_app.config['DOCS_FOLDER'], doc.filename)
        if os.path.exists(src):
            dest_dir = current_app.config['UPLOAD_FOLDER']
            dest     = os.path.join(dest_dir, doc.filename)
            if not os.path.exists(dest):
                import shutil
                shutil.copy2(src, dest)
            attached_path = f'/static/uploads/{doc.filename}'

    imported=0
    for tx in d.get('transactions',[]):
        if not tx.get('include',True): continue
        try:
            t=Transaction(type=tx.get('type','expense'),amount=float(tx.get('amount',0)),
                description=tx.get('description',''),emoji=tx.get('emoji',''),
                category_id=tx.get('category_id') or None,
                date=datetime.strptime(tx['date'],'%Y-%m-%d').date(),
                image_path=attached_path,
                note=f"Import: {doc.original_name}")
            db.session.add(t); imported+=1
        except: continue
    doc.status='imported'; db.session.commit()
    return jsonify(dict(success=True,imported=imported))


@main.route('/api/documents/<int:did>', methods=['DELETE'])
@login_required
def api_documents_delete(did):
    doc=Document.query.get_or_404(did)
    try:
        fp=os.path.join(current_app.config['DOCS_FOLDER'],doc.filename)
        if os.path.exists(fp): os.remove(fp)
    except: pass
    db.session.delete(doc); db.session.commit()
    return jsonify(dict(success=True))


@main.route('/api/documents/<int:did>/file')
@login_required
def api_documents_file(did):
    doc=Document.query.get_or_404(did)
    fp=os.path.join(current_app.config['DOCS_FOLDER'],doc.filename)
    if not os.path.exists(fp): return jsonify(dict(error='Datei nicht gefunden')),404
    return send_file(fp,as_attachment=False)


# ─────────────────── PDF/OCR HELPERS ───────────────────

def _scan_document(filepath):
    """Dispatch to the right parser based on file extension."""
    ext = filepath.rsplit('.', 1)[-1].lower()
    if ext == 'csv':
        return _scan_csv(filepath)
    # PDF / image – basic attempt, user can always fall back to CSV export
    raw_text = ''; pages = 1
    try:
        if ext == 'pdf':
            try:
                import pdfplumber
                with pdfplumber.open(filepath) as pdf:
                    pages = len(pdf.pages)
                    for page in pdf.pages:
                        t = page.extract_text()
                        if t: raw_text += t + '\n'
            except ImportError:
                raw_text = '[pdfplumber nicht installiert]'
        else:
            try:
                import pytesseract
                from PIL import Image, ImageFilter, ImageEnhance
                img = Image.open(filepath)
                # Convert to RGB first if needed (handles RGBA, CMYK, etc.)
                if img.mode not in ('L', 'RGB'):
                    img = img.convert('RGB')
                # Grayscale + contrast boost + sharpen for better OCR
                gray = img.convert('L')
                gray = ImageEnhance.Contrast(gray).enhance(2.2)
                gray = ImageEnhance.Sharpness(gray).enhance(2.0)
                w, h = gray.size
                if w < 1400:  # upscale small images
                    scale = 1400 / w
                    gray = gray.resize((int(w*scale), int(h*scale)), Image.LANCZOS)
                ocr_cfg = '--psm 6 --oem 3 -c preserve_interword_spaces=1'
                raw_text = pytesseract.image_to_string(gray, lang='deu+eng', config=ocr_cfg)
                if len(raw_text.strip()) < 20:
                    # fallback: try original without preprocessing
                    raw_text = pytesseract.image_to_string(img, lang='deu+eng')
            except ImportError:
                raw_text = '[pytesseract nicht installiert – pip install pytesseract]'
            except Exception as e:
                raw_text = f'[OCR-Fehler: {e}]'
    except Exception as e:
        raw_text = f'[Lesefehler: {e}]'

    # For images: try to extract receipt/invoice transactions from OCR text
    extracted = _extract_receipt_transactions(raw_text) if ext in ('png','jpg','jpeg') else []
    return dict(raw_text=raw_text, transactions=extracted, pages=pages,
                info=f'Bild-OCR: {len(extracted)} Position(en) erkannt. Bitte prüfen und anpassen.')


# ── Receipt OCR helper ────────────────────────────────────────────────────────
def _extract_receipt_transactions(text):
    """
    Extract amounts from receipt/invoice OCR text.
    Design goal: never return empty-handed if there are ANY numbers in the text.
    """
    if not text or text.startswith('['):
        return []

    import re

    lines      = [l.strip() for l in text.split('\n') if l.strip()]
    today_str  = date.today().strftime('%Y-%m-%d')

    # ── Find receipt date ──
    date_re = re.compile(r'(\d{1,2})[./\-](\d{1,2})[./\-](\d{2,4})')
    receipt_date = today_str
    for line in lines:
        dm = date_re.search(line)
        if dm:
            d, m, y = dm.group(1).zfill(2), dm.group(2).zfill(2), dm.group(3)
            if len(y) == 2: y = '20' + y
            try:
                datetime.strptime(f'{y}-{m}-{d}', '%Y-%m-%d')
                # Sanity: year must be plausible
                if 2000 <= int(y) <= 2099:
                    receipt_date = f'{y}-{m}-{d}'
                    break
            except: pass

    # ── Robust amount parser ──
    def parse_amount(s):
        """
        Handle all common OCR amount formats:
        12,99 / 12.99 / 1.234,56 / 1,234.56 / 1299 / 12 99 / EUR 12,99 / 12,9
        Returns float or None.
        """
        s = re.sub(r'[€$£EUReuro\s]', '', s, flags=re.I)
        s = s.strip()
        if not s: return None

        # Count separators
        dots   = s.count('.')
        commas = s.count(',')

        try:
            if dots == 1 and commas == 1:
                # Could be 1.234,56 (German) or 1,234.56 (English)
                if s.index('.') < s.index(','):
                    # German: 1.234,56
                    s = s.replace('.', '').replace(',', '.')
                else:
                    # English: 1,234.56
                    s = s.replace(',', '')
            elif commas == 1 and dots == 0:
                # German decimal: 12,99 → 12.99  OR thousands: 1,234 → 1234
                parts = s.split(',')
                if len(parts[1]) <= 2:
                    s = s.replace(',', '.')   # decimal
                else:
                    s = s.replace(',', '')    # thousands
            elif dots == 1 and commas == 0:
                # English decimal 12.99 OR German thousands 1.234
                parts = s.split('.')
                if len(parts[1]) == 3 and len(parts[0]) <= 3:
                    s = s.replace('.', '')    # thousands: 1.234
                # else keep as-is: 12.99
            elif dots == 0 and commas == 0:
                pass  # plain integer e.g. "5"
            else:
                # Multiple separators – strip all and treat as integer
                s = re.sub(r'[.,]', '', s)

            val = float(s)
            return round(val, 2) if val > 0 else None
        except:
            return None

    # ── Broad amount regex – catches all plausible price patterns ──
    # Matches: 12,99 / 12.99 / 1.234,56 / 1.23 / 5 / 12 (standalone)
    AMT_PAT = re.compile(
        r'(?<!\d)'                           # no digit before
        r'(\d{1,4}(?:[.,]\d{3})*[.,]\d{2}'  # structured: 1.234,56 or 12,99
        r'|\d{1,4}[.,]\d{1,2}'              # short: 5,9 or 12.5
        r'|\d{1,5})'                         # plain integer: 5
        r'(?!\d)'                            # no digit after
    )

    TOTAL_KW  = {'gesamt', 'summe', 'total', 'endsumme', 'gesamtbetrag',
                 'rechnungsbetrag', 'zu zahlen', 'zahlbetrag', 'summe eur',
                 'gesamtsumme', 'rechnungs', 'zahlung', 'subtotal', 'amount due',
                 'zu bezahlen', 'endpreis', 'gesamtpreis'}
    SKIP_KW   = {'mwst', 'mehrwertsteuer', 'ust.', 'ust %',
                 'rabatt %', 'skonto', 'guthaben', 'pfand rückgabe'}

    candidates = []
    seen_vals  = set()

    for line in lines:
        ll = line.lower()

        # Hard skip: pure tax/discount percentage lines
        if any(kw in ll for kw in SKIP_KW) and '%' in line:
            continue

        is_total = any(kw in ll for kw in TOTAL_KW)

        matches = AMT_PAT.findall(line)
        if not matches:
            continue

        # Try all matches in line, prefer last one (usually the price column)
        val = None
        for raw in reversed(matches):
            v = parse_amount(raw)
            if v and 0.10 <= v <= 99999:
                val = v; break
        if val is None:
            continue

        # Skip tiny penny amounts unless they look like a total
        if val < 0.50 and not is_total:
            continue

        key = round(val, 2)
        if key in seen_vals:
            continue
        seen_vals.add(key)

        # Clean description: remove amount tokens, keep meaningful text
        desc = line
        for raw in matches:
            desc = desc.replace(raw, '')
        desc = re.sub(r'[€$£]', '', desc)
        desc = re.sub(r'\s{2,}', ' ', desc).strip(' -–:|')
        if not desc or len(desc) < 2:
            desc = 'Gesamtbetrag' if is_total else 'Position'

        candidates.append(dict(
            date=receipt_date,
            description=desc[:150],
            amount=val,
            type='expense',
            include=is_total,   # pre-check only totals
            category_id=None,
            emoji='🧾' if is_total else '🛒',
            _is_total=is_total,
        ))

    if not candidates:
        return []

    # ── Strategy: if we have totals, keep those + uncheck the rest ──
    totals = [c for c in candidates if c['_is_total']]
    items  = [c for c in candidates if not c['_is_total']]

    if totals:
        # Pick the single best total (highest amount among total-keyword lines)
        best = max(totals, key=lambda x: x['amount'])
        best['include'] = True
        best['description'] = best['description'] or 'Gesamtbetrag'
        # Return best total first, then all line items unchecked for reference
        result = [best] + sorted(items, key=lambda x: x['amount'], reverse=True)
    else:
        # No total keyword found – sort by amount desc, pre-check the largest
        candidates.sort(key=lambda x: x['amount'], reverse=True)
        candidates[0]['include'] = True
        result = candidates

    # Remove internal field
    for c in result:
        c.pop('_is_total', None)

    return result[:30]


def _clean_csv_desc(payee, purpose, extra=''):
    """
    Build a clean transaction description from payee + Verwendungszweck.
    Combines the best parts of both fields, strips bank metadata noise.
    """
    import re as _re

    NOISE = _re.compile(
        r'\b(end-to-end|mandatsref|glaeubiger.id|gläubiger.id|'
        r'sepa|lastschrift|überweisung|gutschrift|dauerauftrag|'
        r'referenz|ref\.|buchung|transaktion|kreditkarte|ec.karte|'
        r'debit|credit|payment|zahlung|transfer|mandat|iban|bic|swift|'
        r'hauptkonto|girokonto|geschäftskonto|presentment|'
        r'geldautomat|bargeldauszahlung|pos.beleg)\b',
        _re.I
    )
    DATE_RE   = _re.compile(r'\d{1,2}[./\-]\d{1,2}[./\-]\d{2,4}')
    ISO_DATE  = _re.compile(r'\d{4}-\d{2}-\d{2}')
    AMOUNT_RE = _re.compile(r'^[+-]?\d[\d.,]*$')
    IBAN_RE   = _re.compile(r'[A-Z]{2}\d{2}[A-Z0-9]{10,}')
    NUM_RE    = _re.compile(r'^\d+$')

    def clean_token(s):
        """Return cleaned string or '' if it looks like metadata."""
        s = s.strip().strip('"\'')
        if not s or len(s) < 2:
            return ''
        if DATE_RE.fullmatch(s) or ISO_DATE.fullmatch(s):
            return ''
        if AMOUNT_RE.match(s):
            return ''
        if IBAN_RE.search(s):
            return ''
        if NUM_RE.match(s):
            return ''
        cleaned = NOISE.sub('', s).strip(' -–|:/')
        return cleaned if len(cleaned) > 1 else ''

    def extract_best(raw):
        """Split on separators, keep meaningful tokens."""
        if not raw:
            return ''
        # Remove inline IBANs and amounts
        raw = IBAN_RE.sub('', raw)
        raw = _re.sub(r'\b\d{8,}\b', '', raw)  # long numbers
        # Split on common bank separators
        parts = _re.split(r'\s{2,}|\s*[–\-/|]\s*', raw)
        keepers = [clean_token(p) for p in parts]
        keepers = [k for k in keepers if k]
        return ' '.join(keepers[:4])

    p = extract_best(str(payee or ''))
    u = extract_best(str(purpose or ''))
    e = extract_best(str(extra or ''))

    # Strategy: use payee as primary name, purpose as context
    if p and u and u.lower() != p.lower():
        # If purpose starts with payee name, just use purpose
        if u.lower().startswith(p.lower()[:6]):
            result = u
        else:
            result = f"{p} – {u}"
    elif p:
        result = p
    elif u:
        result = u
    elif e:
        result = e
    else:
        return 'Buchung'

    # Final cleanup
    result = _re.sub(r'\s+', ' ', result).strip(' -–|')
    result = _re.sub(r'([\s-–])+', lambda m: m.group(0)[0], result)
    return result[:300] if result else 'Buchung'


# ── CSV parser ────────────────────────────────────────────────────────────────
def _scan_csv(filepath):
    """
    Parse German bank-statement CSVs.
    Supports: DKB (old+new), Sparkasse, ING, Commerzbank, Volksbank/VR,
              N26, Revolut, Comdirect, Postbank, generic SEPA.
    Auto-detects bank format, delimiter, encoding, sign convention.
    Combines Auftraggeber/Begünstigter + Verwendungszweck for best description.
    """
    # 1. Read & detect encoding
    with open(filepath, 'rb') as f:
        raw = f.read()
    text = None
    for enc in ('utf-8-sig', 'utf-8', 'latin-1', 'cp1252', 'iso-8859-15'):
        try:
            text = raw.decode(enc)
            break
        except Exception:
            pass
    if text is None:
        return dict(raw_text='[Encoding-Fehler]', transactions=[], pages=1,
                    info='Datei konnte nicht gelesen werden.')

    # 2. Detect delimiter
    delim = ';'
    sample = '\n'.join(text.splitlines()[:8])
    scores = {';': sample.count(';'), ',': sample.count(','), '\t': sample.count('\t')}
    delim = max(scores, key=scores.get)
    if scores[delim] < 2:
        delim = ';'

    rows = list(csv.reader(io.StringIO(text), delimiter=delim, quotechar='"'))
    if not rows:
        return dict(raw_text=text[:2000], transactions=[], pages=1, info='CSV ist leer.')

    # 3. Find header row (first row with ≥3 filled cells, skip account-info lines)
    header_idx = 0
    for i, row in enumerate(rows[:20]):
        filled = [c for c in row if c.strip()]
        if len(filled) >= 3:
            # Prefer rows that contain date/amount keywords
            joined = ' '.join(row).lower()
            if any(kw in joined for kw in ('datum','betrag','amount','buchung','date','umsatz','wert')):
                header_idx = i
                break
            if header_idx == 0:
                header_idx = i  # fallback: first non-empty row

    headers_raw = [h.strip().strip('"') for h in rows[header_idx]]
    headers = [h.lower() for h in headers_raw]
    data_rows = rows[header_idx + 1:]

    # 4. Detect bank format by header fingerprint
    h_set = set(headers)
    joined_h = ' '.join(headers)

    bank = 'generic'
    if 'glaeubiger id' in joined_h or 'gläubiger-id' in joined_h or 'mandatsreferenz' in joined_h:
        if 'verwendungszweck' in joined_h and 'beguenstigter' in joined_h:
            bank = 'dkb_old'
        else:
            bank = 'dkb_new'
    elif 'auftraggeber/begünstigter' in joined_h or 'auftraggeber / begünstigter' in joined_h:
        bank = 'sparkasse'
    elif 'auftraggeber/empfänger' in joined_h or 'auftraggeber/empfaenger' in joined_h:
        if 'betrag (eur)' in joined_h or 'betrag' in joined_h:
            bank = 'ing'
    elif any('buchungstext' in h for h in headers) and 'commerzbank' in text[:500].lower():
        bank = 'commerzbank'
    elif any('buchungstext' in h for h in headers):
        bank = 'commerzbank_generic'
    elif 'payee' in h_set and 'payment reference' in joined_h:
        bank = 'n26'
    elif 'beneficiary' in joined_h or 'payment details' in joined_h:
        bank = 'revolut'
    elif 'empfänger/zahlungspflichtiger' in joined_h or 'kontonummer/iban' in joined_h:
        bank = 'volksbank'
    elif 'comdirect' in text[:300].lower() or 'buchungstag' in joined_h and 'vorgang/verwendungszweck' in joined_h:
        bank = 'comdirect'
    elif 'postbank' in text[:300].lower():
        bank = 'postbank'

    # 5. Column mapping per bank
    def col(kws, exact=False):
        """Find first header index matching any keyword."""
        kws = [k.lower() for k in kws]
        for i, h in enumerate(headers):
            for kw in kws:
                if (exact and h == kw) or (not exact and kw in h):
                    return i
        return None

    # Default mappings
    col_date   = col(['buchungstag','buchungsdatum','datum','buchung','date','auftragsdatum','wertstellung'])
    col_payee  = col(['auftraggeber','begünstigter','beguenstigter','empfänger','zahlungsempfänger',
                      'payee','name','beneficiary'])
    col_zweck  = col(['verwendungszweck','betreff','beschreibung','buchungstext','memo',
                      'payment reference','transaction description','payment details',
                      'vorgang','reference','referenz'])
    col_amount = col(['betrag','umsatz','amount','wert','summe','buchungsbetrag','betrag (eur)'])
    col_credit = col(['haben','gutschrift','credit','eingang','einnahmen','credit amount'])
    col_debit  = col(['soll','belastung','abbuchung','debit','ausgaben','debit amount'])
    col_extra  = None  # optional 3rd description field

    # Bank-specific overrides
    if bank in ('dkb_old', 'dkb_new'):
        col_date   = col(['buchungstag','buchungsdatum'])
        col_payee = next((i for i, h in enumerate(headers) if 'zahlungsempfänger' in h), None) or col(['beguenstigter', 'begünstigter', 'auftraggeber'])
        col_zweck  = col(['verwendungszweck'])
        col_amount = col(['betrag','glaeubiger id']) if col(['betrag']) is not None else col(['betrag'])
        col_amount = col(['betrag'])

    elif bank == 'sparkasse':
        col_date   = col(['buchungstag','buchungsdatum','auftragsdatum'])
        col_payee  = col(['auftraggeber/begünstigter','auftraggeber / begünstigter','beguenstigter'])
        col_zweck  = col(['verwendungszweck'])
        col_amount = col(['betrag'])

    elif bank == 'ing':
        col_date   = col(['buchung','wertstellung'])
        col_payee  = col(['auftraggeber/empfänger','auftraggeber/empfaenger'])
        col_zweck  = col(['verwendungszweck'])
        col_amount = col(['betrag'])

    elif bank in ('commerzbank', 'commerzbank_generic'):
        col_date   = col(['buchungstag','datum','buchungsdatum'])
        col_payee  = col(['auftraggeber / begünstigter','auftraggeber','begünstigter','beguenstigter'])
        col_zweck  = col(['verwendungszweck','buchungstext'])
        col_amount = col(['betrag','umsatz'])

    elif bank == 'n26':
        col_date   = col(['date','booking date','buchungsdatum'])
        col_payee  = col(['payee','merchant name'])
        col_zweck  = col(['payment reference','account number','transaction type'])
        col_amount = col(['amount'])

    elif bank == 'revolut':
        col_date   = col(['completed date','started date','date'])
        col_payee  = col(['description','beneficiary'])
        col_zweck  = col(['payment details','reference'])
        col_amount = col(['amount'])

    elif bank == 'volksbank':
        col_date   = col(['buchungsdatum','buchungstag','datum'])
        col_payee  = col(['auftraggeber/empfänger','empfänger/zahlungspflichtiger'])
        col_zweck  = col(['verwendungszweck'])
        col_amount = col(['betrag'])

    elif bank == 'comdirect':
        col_date   = col(['buchungstag'])
        col_payee  = col(['vorgang/verwendungszweck'])   # comdirect merges both
        col_zweck  = col(['buchungstext','betreff'])
        col_amount = col(['umsatz in eur','betrag'])

    # Fallback for completely unknown formats
    if col_date is None:
        col_date = 0
    if col_amount is None and col_credit is None:
        # pick last column that looks numeric
        for i in range(len(headers)-1, -1, -1):
            if any(kw in headers[i] for kw in ('eur','€','betrag','amount','umsatz','summe','wert')):
                col_amount = i; break
        if col_amount is None:
            col_amount = len(headers) - 1
    if col_payee is None and col_zweck is None:
        # find widest string column
        skip = {col_date, col_amount, col_credit, col_debit}
        for i, h in enumerate(headers):
            if i not in skip:
                col_payee = i
                break

    def parse_date(s):
        s = (s or '').strip().split()[0]
        for fmt in ('%d.%m.%Y','%d.%m.%y','%Y-%m-%d','%d/%m/%Y','%m/%d/%Y','%Y/%m/%d'):
            try:
                return datetime.strptime(s, fmt).date()
            except ValueError:
                pass
        return None

    def parse_amount(s):
        s = (s or '').strip().replace('\xa0','').replace('\u202f','').replace(' ','')
        if not s or s in ('-','+',''):
            return None
        neg = s.startswith('-')
        s = s.lstrip('+-')
        # Strip currency symbols
        s = s.replace('EUR','').replace('€','').replace('$','').replace('£','').strip()
        if ',' in s and '.' in s:
            if s.rfind(',') > s.rfind('.'):   # German: 1.234,56
                s = s.replace('.','').replace(',','.')
            else:                              # English: 1,234.56
                s = s.replace(',','')
        elif ',' in s:
            parts = s.split(',')
            if len(parts) == 2 and 1 <= len(parts[1]) <= 2:
                s = s.replace(',','.')
            else:
                s = s.replace(',','')
        try:
            val = float(s)
            return -val if neg else val
        except ValueError:
            return None

    transactions = []
    seen = set()
    skipped = 0

    for row in data_rows:
        try:
            if not row or all(c.strip() == '' for c in row):
                continue
            # Skip summary/total rows
            first = row[0].strip().lower() if row else ''
            if first in ('summe','saldo','gesamt','total','kontostand','anfangssaldo','endsaldo',
                         'buchungen','umsätze','umsaetze'):
                continue

            def cell(idx):
                if idx is None or idx >= len(row): return ''
                v = row[idx]
                return v.strip().strip('"\u00a0').replace('\x00','')

            # Date
            d = parse_date(cell(col_date))
            if d is None:
                skipped += 1
                continue

            # Amount
            amount = None
            tx_type = 'expense'

            if col_credit is not None or col_debit is not None:
                cv = parse_amount(cell(col_credit)) if col_credit is not None else None
                dv = parse_amount(cell(col_debit))  if col_debit  is not None else None
                if cv and abs(cv) > 0.001:
                    amount = abs(cv); tx_type = 'income'
                elif dv and abs(dv) > 0.001:
                    amount = abs(dv); tx_type = 'expense'
            else:
                rv = parse_amount(cell(col_amount))
                if rv is None:
                    skipped += 1
                    continue
                amount  = abs(rv)
                tx_type = 'income' if rv > 0 else 'expense'

            if amount is None or amount < 0.001 or amount > 9_999_999:
                skipped += 1
                continue

            # Description: combine payee + Verwendungszweck
            payee  = cell(col_payee)
            zweck  = cell(col_zweck)
            extra  = cell(col_extra) if col_extra is not None else ''
            try:
                description = _clean_csv_desc(payee, zweck, extra) or 'Buchung'
            except Exception:
                description = (payee or zweck or 'Buchung')[:200]

            # Dedup
            key = (str(d), round(amount, 2), tx_type, description[:30])
            if key in seen:
                continue
            seen.add(key)

            transactions.append(dict(
                date=d.strftime('%Y-%m-%d'),
                description=description,
                amount=round(amount, 2),
                type=tx_type,
                include=True,
                category_id=None,
                emoji='',
            ))
        except Exception:
            skipped += 1
            continue

    bank_label = {
        'dkb_old': 'DKB (alt)', 'dkb_new': 'DKB (neu)',
        'sparkasse': 'Sparkasse', 'ing': 'ING',
        'commerzbank': 'Commerzbank', 'commerzbank_generic': 'Commerzbank-Format',
        'n26': 'N26', 'revolut': 'Revolut',
        'volksbank': 'Volksbank/VR-Bank',
        'comdirect': 'Comdirect', 'postbank': 'Postbank',
        'generic': 'Unbekannte Bank',
    }.get(bank, bank)

    date_h   = headers_raw[col_date]   if col_date   is not None else '?'
    payee_h  = headers_raw[col_payee]  if col_payee  is not None else '-'
    zweck_h  = headers_raw[col_zweck]  if col_zweck  is not None else '-'
    amount_h = headers_raw[col_amount] if col_amount is not None else '?'

    info = (f'Bank: {bank_label} | '
            f'Datum: „{date_h}" | Auftraggeber: „{payee_h}" | '
            f'Zweck: „{zweck_h}" | Betrag: „{amount_h}" | '
            f'{len(transactions)} Transaktionen gefunden'
            + (f' ({skipped} Zeilen übersprungen)' if skipped else ''))

    return dict(
        raw_text=text[:3000],
        transactions=transactions[:500],
        pages=1,
        info=info,
    )



@main.route('/api/documents/test-scan', methods=['POST'])
@login_required
def api_test_scan():
    """Debug endpoint: shows exactly what the CSV parser sees."""
    import traceback as _tb
    if 'file' not in request.files:
        return jsonify({'error': 'No file'}), 400
    f = request.files['file']
    import tempfile, os
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='_' + secure_filename(f.filename or 'test.csv'))
    try:
        f.save(tmp.name)
        result = _scan_csv(tmp.name)
        return jsonify({
            'success': True,
            'info': result.get('info', ''),
            'transaction_count': len(result.get('transactions', [])),
            'first_3': result.get('transactions', [])[:3],
            'raw_preview': result.get('raw_text', '')[:500],
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e), 'traceback': _tb.format_exc()})
    finally:
        try: os.unlink(tmp.name)
        except: pass


# ─────────────────── SAVINGS GOALS ───────────────────

@main.route('/savings')
@login_required
def savings_page():
    goals = SavingsGoal.query.order_by(SavingsGoal.created_at.desc()).all()
    return render_template('savings.html', cfg=get_settings(), goals=goals, today=date.today())

@main.route('/api/savings', methods=['GET'])
@login_required
def api_savings_get():
    return jsonify([g.to_dict() for g in SavingsGoal.query.order_by(SavingsGoal.created_at.desc()).all()])

@main.route('/api/savings', methods=['POST'])
@login_required
def api_savings_post():
    d = request.get_json()
    try:
        g = SavingsGoal(
            name=d['name'], emoji=d.get('emoji','🎯'), color=d.get('color','#22d3a0'),
            target_amount=float(d['target_amount']),
            current_amount=float(d.get('current_amount', 0)),
            deadline=datetime.strptime(d['deadline'],'%Y-%m-%d').date() if d.get('deadline') else None,
            notes=d.get('notes',''))
        db.session.add(g); db.session.commit()
        return jsonify(dict(success=True, goal=g.to_dict()))
    except Exception as e:
        db.session.rollback(); return jsonify(dict(success=False, error=str(e))), 400

@main.route('/api/savings/<int:gid>', methods=['PUT'])
@login_required
def api_savings_put(gid):
    g = SavingsGoal.query.get_or_404(gid); d = request.get_json()
    try:
        g.name=d.get('name',g.name); g.emoji=d.get('emoji',g.emoji); g.color=d.get('color',g.color)
        g.target_amount=float(d.get('target_amount',g.target_amount))
        g.current_amount=float(d.get('current_amount',g.current_amount))
        g.notes=d.get('notes',g.notes)
        g.deadline=datetime.strptime(d['deadline'],'%Y-%m-%d').date() if d.get('deadline') else None
        db.session.commit(); return jsonify(dict(success=True, goal=g.to_dict()))
    except Exception as e:
        db.session.rollback(); return jsonify(dict(success=False, error=str(e))), 400

@main.route('/api/savings/<int:gid>/deposit', methods=['POST'])
@login_required
def api_savings_deposit(gid):
    g = SavingsGoal.query.get_or_404(gid); d = request.get_json()
    try:
        amount = float(d['amount'])
        g.current_amount = round(g.current_amount + amount, 2)
        db.session.commit(); return jsonify(dict(success=True, goal=g.to_dict()))
    except Exception as e:
        db.session.rollback(); return jsonify(dict(success=False, error=str(e))), 400

@main.route('/api/savings/<int:gid>', methods=['DELETE'])
@login_required
def api_savings_delete(gid):
    g = SavingsGoal.query.get_or_404(gid)
    db.session.delete(g); db.session.commit()
    return jsonify(dict(success=True))


# ─────────────────── MONTHLY REPORT ───────────────────

@main.route('/report')
@login_required
def report_page():
    # Get available months from transactions
    months_raw = db.session.query(
        func.strftime('%Y-%m', Transaction.date).label('ym')
    ).distinct().order_by(func.strftime('%Y-%m', Transaction.date).desc()).all()
    months = [m.ym for m in months_raw]
    return render_template('report.html', cfg=get_settings(), months=months, today=date.today())

@main.route('/api/report')
@login_required
def api_report():
    ym = request.args.get('month', date.today().strftime('%Y-%m'))
    try:
        y, m = int(ym[:4]), int(ym[5:7])
        som = date(y, m, 1)
        eom = (som + relativedelta(months=1)) - timedelta(days=1)
    except:
        return jsonify(dict(error='Ungültiger Monat')), 400

    txs = Transaction.query.filter(
        Transaction.date >= som, Transaction.date <= eom
    ).order_by(Transaction.date, Transaction.created_at).all()

    income   = sum(t.amount for t in txs if t.type == 'income')
    expenses = sum(t.amount for t in txs if t.type == 'expense')

    # Category breakdown
    cat_totals = {}
    for t in txs:
        if t.type == 'expense':
            key = t.category.name if t.category else 'Ohne Kategorie'
            cat_totals[key] = cat_totals.get(key, 0) + t.amount

    return jsonify(dict(
        month=ym, month_label=de_month(som),
        transactions=[t.to_dict() for t in txs],
        summary=dict(income=round(income,2), expenses=round(expenses,2),
                     balance=round(income-expenses,2), count=len(txs)),
        category_breakdown=sorted(
            [dict(name=k, amount=round(v,2)) for k,v in cat_totals.items()],
            key=lambda x: x['amount'], reverse=True)
    ))

@main.route('/api/report/csv')
@login_required
def api_report_csv():
    ym = request.args.get('month', date.today().strftime('%Y-%m'))
    try:
        y, m = int(ym[:4]), int(ym[5:7])
        som = date(y, m, 1); eom = (som + relativedelta(months=1)) - timedelta(days=1)
    except:
        return 'Ungültiger Monat', 400
    txs = Transaction.query.filter(
        Transaction.date >= som, Transaction.date <= eom
    ).order_by(Transaction.date).all()
    out = io.StringIO(); w = csv.writer(out, delimiter=';')
    w.writerow(['Datum','Typ','Betrag','Beschreibung','Kategorie','Tags','Notiz'])
    for t in txs:
        w.writerow([t.date.strftime('%d.%m.%Y'),
                    'Einnahme' if t.type=='income' else 'Ausgabe',
                    f'{t.amount:.2f}', t.description,
                    t.category.name if t.category else '',
                    t.tags or '', t.note or ''])
    out.seek(0)
    fname = f'Monatsbericht_{ym}.csv'
    return send_file(io.BytesIO(out.getvalue().encode('utf-8-sig')),
                     mimetype='text/csv', as_attachment=True, download_name=fname)


# ─────────────────── QUICK ENTRIES ───────────────────

@main.route('/api/quickentries', methods=['GET'])
@login_required
def api_qe_get():
    return jsonify([q.to_dict() for q in QuickEntry.query.order_by(QuickEntry.name).all()])

@main.route('/api/quickentries', methods=['POST'])
@login_required
def api_qe_post():
    d = request.get_json()
    try:
        q = QuickEntry(name=d['name'], emoji=d.get('emoji','⚡'),
                       amount=float(d['amount']), type=d.get('type','expense'),
                       category_id=d.get('category_id') or None, note=d.get('note',''))
        db.session.add(q); db.session.commit()
        return jsonify(dict(success=True, entry=q.to_dict()))
    except Exception as e:
        db.session.rollback(); return jsonify(dict(success=False, error=str(e))), 400

@main.route('/api/quickentries/<int:qid>', methods=['PUT'])
@login_required
def api_qe_put(qid):
    q = QuickEntry.query.get_or_404(qid); d = request.get_json()
    try:
        q.name=d.get('name',q.name); q.emoji=d.get('emoji',q.emoji)
        q.amount=float(d.get('amount',q.amount)); q.type=d.get('type',q.type)
        q.category_id=d.get('category_id') or None; q.note=d.get('note',q.note)
        db.session.commit(); return jsonify(dict(success=True, entry=q.to_dict()))
    except Exception as e:
        db.session.rollback(); return jsonify(dict(success=False, error=str(e))), 400

@main.route('/api/quickentries/<int:qid>', methods=['DELETE'])
@login_required
def api_qe_delete(qid):
    q = QuickEntry.query.get_or_404(qid)
    db.session.delete(q); db.session.commit()
    return jsonify(dict(success=True))

@main.route('/api/tags')
@login_required
def api_tags():
    """Return all unique tags used across transactions."""
    rows = db.session.query(Transaction.tags).filter(Transaction.tags != '').all()
    tags = set()
    for (t,) in rows:
        for tag in (t or '').split(','):
            tag = tag.strip()
            if tag: tags.add(tag)
    return jsonify(sorted(tags))
