import os
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
import anthropic
import jwt
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__, static_folder='static')
CORS(app)

# ─── CONFIG ───
database_url = os.environ.get('DATABASE_URL', 'sqlite:///revlife.db')
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'revlife-change-in-prod')
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'pool_pre_ping': True, 'pool_recycle': 300}

db = SQLAlchemy(app)
anthropic_client = anthropic.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'))

FMO_EMAIL = 'lifeteam@revolutionmo.com'
FMO_PASSWORD = 'fmo2026'
INVITE_CODE = 'IUL2026'

# ─── MODELS ───

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='agent')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Case(db.Model):
    __tablename__ = 'cases'
    id = db.Column(db.Integer, primary_key=True)
    client = db.Column(db.String(200))
    agent = db.Column(db.String(100))
    agent_email = db.Column(db.String(100))
    date = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    stage_updated_at = db.Column(db.DateTime, default=datetime.utcnow)
    carrier = db.Column(db.String(10))
    csv = db.Column(db.Float, default=0)
    db_amount = db.Column(db.Float, default=0)
    age = db.Column(db.Integer, default=0)
    annual_premium = db.Column(db.Float, default=0)
    opt2_premium = db.Column(db.Float, default=0)
    opt3_premium = db.Column(db.Float, default=0)
    stage = db.Column(db.Integer, default=1)
    notes = db.Column(db.Text, default='')
    lead_source = db.Column(db.String(100), default='')
    result = db.Column(db.String(50), default='')
    case_notes = db.Column(db.Text, default='')
    reason = db.Column(db.Text, default='')
    dis = db.Column(db.JSON, default=list)
    adv = db.Column(db.JSON, default=list)
    opt1 = db.Column(db.Text, default='')
    is_mec = db.Column(db.Boolean, default=False)
    opt_carriers = db.Column(db.JSON, default=dict)
    case_manager = db.Column(db.String(100), default='')
    rev_life_coach = db.Column(db.String(100), default='')
    annuity_marketer = db.Column(db.String(100), default='')
    target_premium = db.Column(db.Float, default=0)
    insured_name = db.Column(db.String(200), default='')
    policy_number = db.Column(db.String(100), default='')
    funding_source = db.Column(db.String(100), default='')
    app_expiration_date = db.Column(db.Date, nullable=True)
    reopen_date = db.Column(db.Date, nullable=True)
    postpone_reason = db.Column(db.Text, default='')
    created_by = db.Column(db.String(20))

    def to_dict(self):
        return {
            'id': self.id,
            'client': self.client,
            'agent': self.agent,
            'date': self.date,
            'createdAt': int(self.created_at.timestamp() * 1000) if self.created_at else 0,
            'stageUpdatedAt': int(self.stage_updated_at.timestamp() * 1000) if self.stage_updated_at else 0,
            'carrier': self.carrier,
            'csv': self.csv or 0,
            'dbAmount': self.db_amount or 0,
            'age': self.age or 0,
            'annualPremium': self.annual_premium or 0,
            'opt2Premium': self.opt2_premium or 0,
            'opt3Premium': self.opt3_premium or 0,
            'stage': self.stage if self.stage is not None else 1,
            'notes': self.notes or '',
            'leadSource': self.lead_source or '',
            'result': self.result or '',
            'caseNotes': self.case_notes or '',
            'reason': self.reason or '',
            'dis': self.dis or [],
            'adv': self.adv or [],
            'opt1': self.opt1 or '',
            'isMEC': self.is_mec or False,
            'optCarriers': self.opt_carriers or {},
            'createdBy': self.created_by,
            'caseManager': self.case_manager or '',
            'revLifeCoach': self.rev_life_coach or '',
            'annuityMarketer': self.annuity_marketer or '',
            'targetPremium': self.target_premium or 0,
            'insuredName': self.insured_name or '',
            'policyNumber': self.policy_number or '',
            'fundingSource': self.funding_source or '',
            'appExpirationDate': self.app_expiration_date.isoformat() if self.app_expiration_date else '',
            'reopenDate': self.reopen_date.isoformat() if self.reopen_date else '',
            'postponeReason': self.postpone_reason or '',
        }


# ─── AUTH HELPERS ───

def make_token(user_id, email, name, role):
    return jwt.encode(
        {'id': user_id, 'email': email, 'name': name, 'role': role},
        app.config['SECRET_KEY'],
        algorithm='HS256'
    )


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if not token:
            return jsonify({'error': 'Unauthorized'}), 401
        try:
            request.user = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401
        return f(*args, **kwargs)
    return decorated


# ─── ROUTES ───

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')


@app.route('/api/me', methods=['GET'])
@require_auth
def me():
    u = request.user
    return jsonify({'name': u['name'], 'role': u['role'], 'email': u['email']})


@app.route('/api/db-status', methods=['GET'])
def db_status():
    db_url = app.config['SQLALCHEMY_DATABASE_URI']
    db_type = 'postgresql' if 'postgresql' in db_url else 'sqlite'
    return jsonify({'type': db_type, 'persistent': db_type == 'postgresql',
                    'warning': None if db_type == 'postgresql' else 'Using SQLite — cases will be lost on redeploy. Set DATABASE_URL in Railway env vars.'})


@app.route('/api/login', methods=['POST'])
def login():
    data = request.json or {}
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if email == FMO_EMAIL and password == FMO_PASSWORD:
        token = make_token(0, FMO_EMAIL, 'FMO Team', 'fmo')
        return jsonify({'token': token, 'name': 'FMO Team', 'role': 'fmo'})

    user = User.query.filter_by(email=email).first()
    if user and check_password_hash(user.password_hash, password):
        token = make_token(user.id, user.email, user.name, user.role)
        return jsonify({'token': token, 'name': user.name, 'role': user.role})

    return jsonify({'error': 'Invalid email or password'}), 401


@app.route('/api/register', methods=['POST'])
def register():
    data = request.json or {}
    code = data.get('code', '').strip()
    name = data.get('name', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if code != INVITE_CODE:
        return jsonify({'error': 'Invalid invite code.'}), 400
    if not name or not email or not password:
        return jsonify({'error': 'Please fill in all fields.'}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'An account with this email already exists.'}), 400

    user = User(
        name=name,
        email=email,
        password_hash=generate_password_hash(password),
        role='agent'
    )
    db.session.add(user)
    db.session.commit()

    token = make_token(user.id, user.email, user.name, user.role)
    return jsonify({'token': token, 'name': user.name, 'role': user.role})


@app.route('/api/cases', methods=['GET'])
@require_auth
def get_cases():
    user = request.user
    if user['role'] == 'fmo':
        cases = Case.query.order_by(Case.created_at.desc()).all()
    else:
        cases = Case.query.filter_by(agent_email=user['email']).order_by(Case.created_at.desc()).all()
    return jsonify([c.to_dict() for c in cases])


@app.route('/api/cases', methods=['POST'])
@require_auth
def create_case():
    data = request.json or {}
    user = request.user
    case = Case(
        client=data.get('client', 'Unknown Client'),
        agent=data.get('agent', user['name']),
        agent_email=user['email'],
        date=data.get('date', ''),
        carrier=data.get('carrier', 'AZ'),
        csv=data.get('csv', 0),
        db_amount=data.get('dbAmount', 0),
        age=data.get('age', 0),
        annual_premium=data.get('annualPremium', 0),
        opt2_premium=data.get('opt2Premium', 0),
        opt3_premium=data.get('opt3Premium', 0),
        stage=data.get('stage', 1),
        dis=data.get('dis', []),
        adv=data.get('adv', []),
        opt1=data.get('opt1', ''),
        is_mec=data.get('isMEC', False),
        opt_carriers=data.get('optCarriers', {}),
        case_manager=data.get('caseManager', ''),
        rev_life_coach=data.get('revLifeCoach', ''),
        annuity_marketer=data.get('annuityMarketer', ''),
        target_premium=data.get('targetPremium', 0),
        insured_name=data.get('insuredName', data.get('client', '')),
        policy_number=data.get('policyNumber', ''),
        funding_source=data.get('fundingSource', ''),
        created_by=user['role']
    )
    db.session.add(case)
    db.session.commit()
    return jsonify(case.to_dict()), 201


@app.route('/api/cases/<int:case_id>', methods=['PUT'])
@require_auth
def update_case(case_id):
    user = request.user
    case = db.session.get(Case, case_id)
    if not case:
        return jsonify({'error': 'Not found'}), 404
    if user['role'] != 'fmo' and case.agent_email != user['email']:
        return jsonify({'error': 'Forbidden'}), 403

    data = request.json or {}
    if 'stage' in data:
        case.stage = int(data['stage'])
        case.stage_updated_at = datetime.utcnow()
    if 'notes' in data:
        case.notes = data['notes']
    if 'reason' in data:
        case.reason = data['reason']
    if 'leadSource' in data:
        case.lead_source = data['leadSource']
    if 'result' in data:
        case.result = data['result']
    if 'caseNotes' in data:
        case.case_notes = data['caseNotes']
    if 'caseManager' in data:
        case.case_manager = data['caseManager']
    if 'revLifeCoach' in data:
        case.rev_life_coach = data['revLifeCoach']
    if 'annuityMarketer' in data:
        case.annuity_marketer = data['annuityMarketer']
    if 'targetPremium' in data:
        case.target_premium = float(data['targetPremium'])
    if 'insuredName' in data:
        case.insured_name = data['insuredName']
    if 'policyNumber' in data:
        case.policy_number = data['policyNumber']
    if 'fundingSource' in data:
        case.funding_source = data['fundingSource']
    if 'postponeReason' in data:
        case.postpone_reason = data['postponeReason']

    db.session.commit()
    return jsonify(case.to_dict())


@app.route('/api/cases/<int:case_id>', methods=['DELETE'])
@require_auth
def delete_case(case_id):
    user = request.user
    case = db.session.get(Case, case_id)
    if not case:
        return jsonify({'error': 'Not found'}), 404
    if user['role'] != 'fmo' and case.agent_email != user['email']:
        return jsonify({'error': 'Forbidden'}), 403
    db.session.delete(case)
    db.session.commit()
    return jsonify({'ok': True})


@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        data = request.json
        response = anthropic_client.messages.create(
            model='claude-sonnet-4-20250514',
            max_tokens=1000,
            messages=data['messages']
        )
        return jsonify({'content': [{'text': response.content[0].text}]})
    except Exception as e:
        return jsonify({'error': {'message': str(e)}}), 500


# ─── INIT ───

import sys
if 'postgresql' not in os.environ.get('DATABASE_URL', ''):
    print('WARNING: DATABASE_URL not set or not PostgreSQL — using SQLite. Cases WILL be lost on redeploy!', file=sys.stderr)

with app.app_context():
    db.create_all()
    # Add new columns if they don't exist (safe to run on every startup)
    from sqlalchemy import text
    new_cols = [
        ('db_amount', 'FLOAT DEFAULT 0'),
        ('age', 'INTEGER DEFAULT 0'),
        ('annual_premium', 'FLOAT DEFAULT 0'),
        ('opt2_premium', 'FLOAT DEFAULT 0'),
        ('opt3_premium', 'FLOAT DEFAULT 0'),
        ('is_mec', 'BOOLEAN DEFAULT FALSE'),
        ('opt_carriers', "JSONB DEFAULT '{}'"),
        ('case_manager', "VARCHAR(100) DEFAULT ''"),
        ('rev_life_coach', "VARCHAR(100) DEFAULT ''"),
        ('annuity_marketer', "VARCHAR(100) DEFAULT ''"),
        ('target_premium', 'FLOAT DEFAULT 0'),
        ('insured_name', "VARCHAR(200) DEFAULT ''"),
        ('policy_number', "VARCHAR(100) DEFAULT ''"),
        ('funding_source', "VARCHAR(100) DEFAULT ''"),
        ('app_expiration_date', 'DATE'),
        ('reopen_date', 'DATE'),
        ('postpone_reason', "TEXT DEFAULT ''"),
    ]
    with db.engine.connect() as conn:
        for col, coltype in new_cols:
            conn.execute(text(f'ALTER TABLE cases ADD COLUMN IF NOT EXISTS {col} {coltype}'))
            conn.commit()
        # Migrations tracking
        try:
            conn.execute(text('CREATE TABLE IF NOT EXISTS migrations (name VARCHAR(100) PRIMARY KEY, applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)'))
            conn.commit()
        except Exception:
            conn.rollback()
        try:
            applied = {r[0] for r in conn.execute(text('SELECT name FROM migrations')).fetchall()}
            if 'remove_sent_for_analysis_stage' not in applied:
                conn.execute(text('UPDATE cases SET stage = stage - 1 WHERE stage >= 2'))
                conn.execute(text("INSERT INTO migrations (name) VALUES ('remove_sent_for_analysis_stage')"))
                conn.commit()
            if 'fix_katie_gr_name' not in applied:
                conn.execute(text("UPDATE cases SET agent = 'Katie Grafrath' WHERE agent = 'Katie Gr'"))
                conn.execute(text("INSERT INTO migrations (name) VALUES ('fix_katie_gr_name')"))
                conn.commit()
        except Exception:
            conn.rollback()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port)
