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
    stage = db.Column(db.Integer, default=1)
    notes = db.Column(db.Text, default='')
    lead_source = db.Column(db.String(100), default='')
    result = db.Column(db.String(50), default='')
    case_notes = db.Column(db.Text, default='')
    reason = db.Column(db.Text, default='')
    dis = db.Column(db.JSON, default=list)
    adv = db.Column(db.JSON, default=list)
    opt1 = db.Column(db.Text, default='')
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
            'stage': self.stage or 1,
            'notes': self.notes or '',
            'leadSource': self.lead_source or '',
            'result': self.result or '',
            'caseNotes': self.case_notes or '',
            'reason': self.reason or '',
            'dis': self.dis or [],
            'adv': self.adv or [],
            'opt1': self.opt1 or '',
            'createdBy': self.created_by,
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
        stage=1,
        dis=data.get('dis', []),
        adv=data.get('adv', []),
        opt1=data.get('opt1', ''),
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

    db.session.commit()
    return jsonify(case.to_dict())


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

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port)
