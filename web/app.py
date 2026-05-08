from flask import Flask, render_template, request, Response, stream_with_context, session, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from extract import extract_text
from llm import get_annotations
from renderer import render_full_document
from functools import wraps
import uuid
import secrets
import requests
import json
import time
import os
import re

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'fallback_key_here')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///llm.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

OLLAMA_URL = "http://localhost:11435/api/generate"
MODEL = "deepseek-r1:32b"
ALLOWED_DOMAIN = "@stolaf.edu"

# ============================================================
# Database Models
# ============================================================

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    first_seen = db.Column(db.DateTime, default=datetime.utcnow)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    conversations = db.relationship('Conversation', backref='user', lazy=True)

class Conversation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    started = db.Column(db.DateTime, default=datetime.utcnow)
    messages = db.relationship('Message', backref='conversation', lazy=True)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversation.id'), nullable=False)
    role = db.Column(db.String(10), nullable=False)  # 'user' or 'assistant'
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    response_time = db.Column(db.Float, nullable=True)
    tokens_per_second = db.Column(db.Float, nullable=True)

class ErrorLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_email = db.Column(db.String(120), nullable=True)
    error = db.Column(db.Text, nullable=False)

class Review(db.Model):
    id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    created = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref='reviews')

class ReadingReview(db.Model):
    id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    created = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref='reading_reviews')

class ApiKey(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(128), unique=True, nullable=False)
    label = db.Column(db.String(120), nullable=False, default='')
    active = db.Column(db.Boolean, default=True, nullable=False)
    created = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()

# ============================================================
# Helper Functions
# ============================================================

def is_valid_email(email):
    return email.endswith(ALLOWED_DOMAIN) and len(email) > len(ALLOWED_DOMAIN)

def get_or_create_user(email):
    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(email=email)
        db.session.add(user)
        db.session.commit()
    else:
        user.last_seen = datetime.utcnow()
        db.session.commit()
    return user

def get_or_create_conversation(user):
    conversation = Conversation.query.filter_by(user_id=user.id).order_by(Conversation.started.desc()).first()
    if not conversation:
        conversation = Conversation(user_id=user.id)
        db.session.add(conversation)
        db.session.commit()
    return conversation

def get_conversation_history(conversation):
    messages = Message.query.filter_by(conversation_id=conversation.id).order_by(Message.timestamp.asc()).all()
    history = []
    for msg in messages:
        history.append({
            'role': msg.role,
            'content': msg.content
        })
    return history

def log_error(error, email=None):
    err = ErrorLog(error=str(error), user_email=email)
    db.session.add(err)
    db.session.commit()

def is_ollama_running():
    try:
        requests.get('http://localhost:11435', timeout=2)
        return True
    except requests.exceptions.ConnectionError:
        return False

# ============================================================
# Routes
# ============================================================

@app.route('/')
def index():
    if 'email' not in session:
        return redirect(url_for('login'))
    return render_template('index.html', email=session['email'])

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    next_url = request.args.get('next', '')
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        next_url = request.form.get('next_url', '')
        if not is_valid_email(email):
            error = 'Please enter a valid @stolaf.edu email address'
        else:
            get_or_create_user(email)
            session['email'] = email
            if next_url and next_url.startswith('/'):
                return redirect(next_url)
            return redirect(url_for('index'))
    return render_template('login.html', error=error, next_url=next_url)

@app.route('/logout')
def logout():
    session.pop('email', None)
    return redirect(url_for('login'))

@app.route('/status')
def status():
    return {'running': is_ollama_running()}

@app.route('/history')
def history():
    if 'email' not in session:
        return jsonify([])
    user = User.query.filter_by(email=session['email']).first()
    if not user:
        return jsonify([])
    conversation = get_or_create_conversation(user)
    messages = get_conversation_history(conversation)
    return jsonify(messages)

@app.route('/clear', methods=['POST'])
def clear():
    if 'email' not in session:
        return jsonify({'success': False})
    user = User.query.filter_by(email=session['email']).first()
    if user:
        conversation = Conversation(user_id=user.id)
        db.session.add(conversation)
        db.session.commit()
    return jsonify({'success': True})

@app.route('/query', methods=['POST'])
def query():
    if 'email' not in session:
        return Response('Unauthorized', status=401)

    if not is_ollama_running():
        return Response('Ollama is not running', status=503)

    data = request.get_json()
    prompt = data.get('prompt', '')
    email = session['email']

    user = get_or_create_user(email)
    conversation = get_or_create_conversation(user)

    # Save user message
    user_message = Message(
        conversation_id=conversation.id,
        role='user',
        content=prompt
    )
    db.session.add(user_message)
    db.session.commit()

    # Build conversation history for context
    history = get_conversation_history(conversation)
    
    # Format history into a single prompt with context
    context = ""
    for msg in history[:-1]:  # exclude the message we just added
        role_label = "User" if msg['role'] == 'user' else "Assistant"
        context += f"{role_label}: {msg['content']}\n\n"
    
    full_prompt = context + f"User: {prompt}\n\nAssistant:"

    def generate():
        start_time = time.time()
        first_token_time = None
        full_response = ""
        token_count = 0

        try:
            response = requests.post(OLLAMA_URL,
                json={"model": MODEL, "prompt": full_prompt},
                stream=True,
                timeout=300
            )

            for line in response.iter_lines():
                if line:
                    token = json.loads(line).get('response', '')
                    if token and first_token_time is None:
                        first_token_time = time.time()
                    full_response += token
                    token_count += 1
                    yield token

        except Exception as e:
            log_error(e, email)
            yield f"\nError: {str(e)}"
            return

        # Calculate metrics
        end_time = time.time()
        total_time = end_time - start_time
        tokens_per_second = token_count / total_time if total_time > 0 else 0

        # Save assistant response
        assistant_message = Message(
            conversation_id=conversation.id,
            role='assistant',
            content=full_response,
            response_time=round(total_time, 2),
            tokens_per_second=round(tokens_per_second, 2)
        )
        db.session.add(assistant_message)
        db.session.commit()

    return Response(stream_with_context(generate()), mimetype='text/plain')

# ============================================================
# Writing Center Routes
# ============================================================

@app.route('/writing-center')
def writing_center():
    if 'email' not in session:
        return redirect(url_for('login', next='/writing-center'))
    return render_template('writing_center.html', email=session['email'])

@app.route('/writing-center/upload', methods=['POST'])
def writing_center_upload():
    if 'email' not in session:
        return Response('Unauthorized', status=401)

    if 'document' not in request.files:
        return Response('No file uploaded', status=400)

    file = request.files['document']
    if file.filename == '':
        return Response('No file selected', status=400)

    # Check allowed extensions
    allowed = {'.txt', '.pdf', '.docx'}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed:
        return Response(f'Unsupported file type. Please upload .txt, .pdf, or .docx', status=400)

    # Save uploaded file temporarily
    upload_path = os.path.join('/tmp', f'{uuid.uuid4()}{ext}')
    file.save(upload_path)

    # Capture form fields before entering generator
    query = request.form.get('query', '').strip()
    mode = request.form.get('mode', 'general').strip()
    if mode not in ('general', 'rephrase', 'rubric', 'brainstorm'):
        mode = 'general'
    filename = file.filename

    def generate():
        try:
            yield "Extracting text...\n"
            text = extract_text(upload_path)

            if not text.strip():
                yield "error:Could not extract text from document\n"
                return

            # Rephrase and rubric modes require content in the query field
            if mode == 'rephrase' and not query:
                yield "error:Rephrase mode requires a passage to rephrase. Please paste it in the text box.\n"
                return
            if mode == 'rubric' and not query:
                yield "error:Rubric mode requires a rubric or assignment prompt. Please paste it in the text box.\n"
                return

            # Build extra_instructions based on mode
            if mode == 'general' and query:
                extra = f"The tutor has provided this additional focus: {query}"
            elif mode in ('rephrase', 'rubric', 'brainstorm'):
                extra = query or None
            else:
                extra = None

            yield "Analyzing with writing consultant...\n"
            try:
                result = get_annotations(text, mode=mode, extra_instructions=extra)
            except ValueError:
                yield "error:Could not parse model response. Try a different document.\n"
                return

            yield "Rendering annotated document...\n"
            html_output = render_full_document(text, result, filename, mode=mode)

            # Save rendered HTML with unique ID
            review_id = str(uuid.uuid4())
            review_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                'reviews',
                f'{review_id}.html'
            )
            with open(review_path, 'w') as f:
                f.write(html_output)

            # Save review to database
            user = User.query.filter_by(email=session['email']).first()
            if user:
                review = Review(
                    id=review_id,
                    user_id=user.id,
                    filename=filename
                )
                db.session.add(review)
                user.last_seen = datetime.utcnow()
                db.session.commit()

            yield f"done:{review_id}\n"

        except Exception as e:
            log_error(str(e), session.get('email'))
            yield f"error:{str(e)}\n"
        finally:
            if os.path.exists(upload_path):
                os.remove(upload_path)

    return Response(stream_with_context(generate()), mimetype='text/plain')

@app.route('/writing-center/review/<review_id>')
def writing_center_review(review_id):
    if 'email' not in session:
        return redirect(url_for('login'))

    # Sanitize review_id to prevent path traversal
    if not review_id.replace('-', '').isalnum():
        return Response('Invalid review ID', status=400)

    review_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'reviews',
        f'{review_id}.html'
    )

    if not os.path.exists(review_path):
        return Response('Review not found', status=404)

    with open(review_path, 'r') as f:
        return f.read(), 200, {'Content-Type': 'text/html'}

@app.route('/writing-center/review/<review_id>/delete', methods=['POST'])
def writing_center_delete(review_id):
    if 'email' not in session:
        return jsonify({'success': False}), 401

    if not review_id.replace('-', '').isalnum():
        return jsonify({'success': False}), 400

    user = User.query.filter_by(email=session['email']).first()
    if not user:
        return jsonify({'success': False}), 404

    review = Review.query.filter_by(id=review_id, user_id=user.id).first()
    if not review:
        return jsonify({'success': False}), 404

    # Delete HTML file
    review_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'reviews',
        f'{review_id}.html'
    )
    if os.path.exists(review_path):
        os.remove(review_path)

    # Delete database entry
    db.session.delete(review)
    db.session.commit()

    return jsonify({'success': True})

@app.route('/writing-center/reviews')
def writing_center_reviews():
    if 'email' not in session:
        return jsonify([])
    user = User.query.filter_by(email=session['email']).first()
    if not user:
        return jsonify([])
    reviews = Review.query.filter_by(user_id=user.id)\
        .order_by(Review.created.desc()).all()
    return jsonify([{
        'id': r.id,
        'filename': r.filename,
        'created': r.created.strftime('%B %d, %Y at %I:%M %p')
    } for r in reviews])

# ============================================================
# Reading Center Routes
# ============================================================

READING_REVIEWS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'reading_reviews')

@app.route('/reading-center')
def reading_center():
    if 'email' not in session:
        return redirect(url_for('login', next='/reading-center'))
    return render_template('reading_center.html', email=session['email'])

@app.route('/reading-center/upload', methods=['POST'])
def reading_center_upload():
    if 'email' not in session:
        return Response('Unauthorized', status=401)

    if 'document' not in request.files:
        return Response('No file uploaded', status=400)

    file = request.files['document']
    if file.filename == '':
        return Response('No file selected', status=400)

    allowed = {'.txt', '.pdf', '.docx'}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed:
        return Response('Unsupported file type. Please upload .txt, .pdf, or .docx', status=400)

    upload_path = os.path.join('/tmp', f'{uuid.uuid4()}{ext}')
    file.save(upload_path)

    prompt = request.form.get('prompt', '').strip()
    filename = file.filename

    def generate():
        try:
            yield "Extracting text...\n"
            try:
                text = extract_text(upload_path)
            except ValueError as e:
                yield f"error:{e}\n"
                return

            if not text.strip():
                yield "error:Could not extract text from document\n"
                return

            yield "Analyzing structure and movement...\n"
            try:
                result = get_annotations(text, mode='reading', extra_instructions=prompt or None)
            except ValueError:
                yield "error:Could not parse model response. Try a different document.\n"
                return

            yield "Rendering reading analysis...\n"
            html_output = render_full_document(text, result, filename, mode='reading')

            review_id = str(uuid.uuid4())
            review_path = os.path.join(READING_REVIEWS_DIR, f'{review_id}.html')
            with open(review_path, 'w') as f:
                f.write(html_output)

            user = User.query.filter_by(email=session['email']).first()
            if user:
                review = ReadingReview(id=review_id, user_id=user.id, filename=filename)
                db.session.add(review)
                user.last_seen = datetime.utcnow()
                db.session.commit()

            yield f"done:{review_id}\n"

        except Exception as e:
            log_error(str(e), session.get('email'))
            yield f"error:{str(e)}\n"
        finally:
            if os.path.exists(upload_path):
                os.remove(upload_path)

    return Response(stream_with_context(generate()), mimetype='text/plain')

@app.route('/reading-center/review/<review_id>')
def reading_center_review(review_id):
    if 'email' not in session:
        return redirect(url_for('login'))

    if not review_id.replace('-', '').isalnum():
        return Response('Invalid review ID', status=400)

    review_path = os.path.join(READING_REVIEWS_DIR, f'{review_id}.html')
    if not os.path.exists(review_path):
        return Response('Review not found', status=404)

    with open(review_path, 'r') as f:
        return f.read(), 200, {'Content-Type': 'text/html'}

@app.route('/reading-center/review/<review_id>/delete', methods=['POST'])
def reading_center_delete(review_id):
    if 'email' not in session:
        return jsonify({'success': False}), 401

    if not review_id.replace('-', '').isalnum():
        return jsonify({'success': False}), 400

    user = User.query.filter_by(email=session['email']).first()
    if not user:
        return jsonify({'success': False}), 404

    review = ReadingReview.query.filter_by(id=review_id, user_id=user.id).first()
    if not review:
        return jsonify({'success': False}), 404

    review_path = os.path.join(READING_REVIEWS_DIR, f'{review_id}.html')
    if os.path.exists(review_path):
        os.remove(review_path)

    db.session.delete(review)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/reading-center/reviews')
def reading_center_reviews():
    if 'email' not in session:
        return jsonify([])
    user = User.query.filter_by(email=session['email']).first()
    if not user:
        return jsonify([])
    reviews = ReadingReview.query.filter_by(user_id=user.id)\
        .order_by(ReadingReview.created.desc()).all()
    return jsonify([{
        'id': r.id,
        'filename': r.filename,
        'created': r.created.strftime('%B %d, %Y at %I:%M %p')
    } for r in reviews])


# ============================================================
# API v1
# ============================================================

def require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get('Authorization', '')
        if not auth.startswith('Bearer '):
            return jsonify({'error': 'Missing API key. Set Authorization: Bearer <key>'}), 401
        key = auth[7:]
        api_key = ApiKey.query.filter_by(key=key, active=True).first()
        if not api_key:
            return jsonify({'error': 'Invalid or inactive API key'}), 401
        return f(*args, **kwargs)
    return decorated

def require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get('Authorization', '')
        if not auth.startswith('Bearer '):
            return jsonify({'error': 'Unauthorized'}), 401
        if auth[7:] != os.environ.get('ADMIN_KEY', ''):
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated

@app.route('/api/v1/generate', methods=['POST'])
@require_api_key
def api_generate():
    if not is_ollama_running():
        return jsonify({'error': 'Model unavailable'}), 503

    data = request.get_json(silent=True)
    if not data or 'prompt' not in data:
        return jsonify({'error': 'Missing required field: prompt'}), 400

    prompt = data['prompt'].strip()
    if not prompt:
        return jsonify({'error': 'prompt cannot be empty'}), 400

    try:
        response = requests.post(OLLAMA_URL,
            json={"model": MODEL, "prompt": prompt},
            stream=True,
            timeout=300
        )
        full_response = ""
        for line in response.iter_lines():
            if line:
                full_response += json.loads(line).get('response', '')

        return jsonify({'response': full_response, 'model': MODEL})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/v1/generate/stream', methods=['POST'])
@require_api_key
def api_generate_stream():
    if not is_ollama_running():
        return jsonify({'error': 'Model unavailable'}), 503

    data = request.get_json(silent=True)
    if not data or 'prompt' not in data:
        return jsonify({'error': 'Missing required field: prompt'}), 400

    prompt = data['prompt'].strip()
    if not prompt:
        return jsonify({'error': 'prompt cannot be empty'}), 400

    def generate():
        try:
            response = requests.post(OLLAMA_URL,
                json={"model": MODEL, "prompt": prompt},
                stream=True,
                timeout=300
            )
            for line in response.iter_lines():
                if line:
                    token = json.loads(line).get('response', '')
                    done = json.loads(line).get('done', False)
                    yield json.dumps({'token': token, 'done': done}) + '\n'
        except Exception as e:
            yield json.dumps({'error': str(e)}) + '\n'

    return Response(stream_with_context(generate()), mimetype='application/x-ndjson')

# ============================================================
# API Admin Routes
# ============================================================

@app.route('/api/admin/keys', methods=['POST'])
@require_admin
def admin_create_key():
    data = request.get_json(silent=True) or {}
    label = data.get('label', '').strip()
    key = data.get('key', '').strip() or secrets.token_urlsafe(16)

    if ApiKey.query.filter_by(key=key).first():
        return jsonify({'error': 'A key with that value already exists'}), 409

    api_key = ApiKey(key=key, label=label)
    db.session.add(api_key)
    db.session.commit()

    return jsonify({'id': api_key.id, 'key': api_key.key, 'label': api_key.label}), 201

@app.route('/api/admin/keys', methods=['GET'])
@require_admin
def admin_list_keys():
    keys = ApiKey.query.order_by(ApiKey.created.desc()).all()
    return jsonify([{
        'id': k.id,
        'key': k.key,
        'label': k.label,
        'active': k.active,
        'created': k.created.isoformat()
    } for k in keys])

@app.route('/api/admin/keys/<int:key_id>', methods=['DELETE'])
@require_admin
def admin_deactivate_key(key_id):
    api_key = ApiKey.query.get(key_id)
    if not api_key:
        return jsonify({'error': 'Key not found'}), 404
    api_key.active = False
    db.session.commit()
    return jsonify({'success': True})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
