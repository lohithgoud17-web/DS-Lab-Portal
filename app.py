import os
import mimetypes
import uuid
from functools import wraps
from flask import (
    Flask, render_template, request, jsonify, redirect, url_for,
    session, send_file, abort, flash
)
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash, generate_password_hash
from dotenv import load_dotenv

try:
    import cloudinary
    from cloudinary import uploader
except ImportError:  # pragma: no cover
    cloudinary = None
    uploader = None

from database import query_db, init_db

# Load environment
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, '.env'))

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'dslab_default_secret_key_2026_xyz')
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100 MB max upload
app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'uploads')

# Initialize database schema and initial records on app load
try:
    init_db()
except Exception as _init_err:
    print(f"[Database Startup Notice] init_db deferred: {_init_err}")

ALLOWED_EXTENSIONS_PDF = {'pdf'}
ALLOWED_EXTENSIONS_IMG = {'png', 'jpg', 'jpeg', 'webp', 'svg'}
ALLOWED_EXTENSIONS_VID = {'mp4', 'webm', 'ogg', 'mov'}
ALLOWED_EXTENSIONS_CODE = {'py', 'ipynb', 'txt', 'sql', 'r', 'java', 'c', 'cpp', 'js', 'json', 'csv'}


def storage_is_configured():
    cloud_name = os.getenv('CLOUDINARY_CLOUD_NAME')
    api_key = os.getenv('CLOUDINARY_API_KEY')
    api_secret = os.getenv('CLOUDINARY_API_SECRET')
    return bool(cloud_name and api_key and api_secret and cloudinary is not None)


def upload_to_storage(file_storage, folder, prefix='upload'):
    if not file_storage or not getattr(file_storage, 'filename', None):
        raise ValueError('No file selected.')

    cloud_name = os.getenv('CLOUDINARY_CLOUD_NAME')
    api_key = os.getenv('CLOUDINARY_API_KEY')
    api_secret = os.getenv('CLOUDINARY_API_SECRET')

    if cloud_name and api_key and api_secret and cloudinary is not None:
        cloudinary.config(
            cloud_name=cloud_name,
            api_key=api_key,
            api_secret=api_secret,
        )
        public_id = f"{prefix}_{uuid.uuid4().hex}_{secure_filename(file_storage.filename).rsplit('.', 1)[0] if '.' in secure_filename(file_storage.filename) else secure_filename(file_storage.filename)}"
        res = uploader.upload(file_storage, folder=folder, public_id=public_id, resource_type='auto')
        return {
            'url': res.get('secure_url') or res.get('url'),
            'path': res.get('secure_url') or res.get('url'),
            'name': file_storage.filename,
            'public_id': res.get('public_id'),
            'storage': 'cloudinary',
        }

    target_dir = os.path.join(app.config['UPLOAD_FOLDER'], folder)
    os.makedirs(target_dir, exist_ok=True)
    safe_name = secure_filename(file_storage.filename)
    unique_name = f"{prefix}_{uuid.uuid4().hex}_{safe_name}"
    local_path = os.path.join(target_dir, unique_name)
    file_storage.save(local_path)
    relative_path = os.path.join('uploads', folder, unique_name).replace('\\', '/')
    return {
        'url': f"/uploads/{folder}/{unique_name}",
        'path': relative_path,
        'name': safe_name,
        'public_id': unique_name,
        'storage': 'local',
    }


def allowed_file(filename, allowed_set):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_set

def extract_code_from_file(file_storage, save_path):
    file_storage.save(save_path)
    ext = save_path.rsplit('.', 1)[-1].lower()
    if ext == 'ipynb':
        try:
            import json
            with open(save_path, 'r', encoding='utf-8', errors='ignore') as f:
                nb = json.load(f)
            cells = []
            for cell in nb.get('cells', []):
                if cell.get('cell_type') == 'code':
                    src = "".join(cell.get('source', []))
                    if src.strip():
                        cells.append(src)
            return "\n\n# --- Notebook Cell ---\n".join(cells)
        except Exception as e:
            return f"# Notebook loaded. Error parsing cells: {e}"
    else:
        try:
            with open(save_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except Exception as e:
            return f"# Code file loaded. Could not read text: {e}"

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            if request.is_json:
                return jsonify({'error': 'Unauthorized. Admin login required.'}), 401
            return redirect(url_for('admin_login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

# --------------------------------------------------------------------------
# Context Processors & Helpers
# --------------------------------------------------------------------------
@app.context_processor
def inject_global_data():
    profile = query_db("SELECT * FROM students WHERE id = 1", fetch='one') or {
        'name': 'Data Science Scholar',
        'register_no': '22DS101',
        'section': 'DS-A',
        'branch': 'Data Science & AI',
        'faculty_name': 'Dr. S. Ramanathan',
        'photo_url': '/static/images/default_student.svg',
        'github_url': 'https://github.com/lohitkumar/ds-laboratory'
    }
    return {
        'current_student': profile,
        'is_admin': bool(session.get('admin_logged_in')),
        'admin_user': session.get('admin_username', '')
    }

# --------------------------------------------------------------------------
# Front-end HTML Pages
# --------------------------------------------------------------------------
@app.route('/')
def home():
    """Home page with Student Profile ID card, Explore cards, and Overview stats."""
    modules_count = query_db("SELECT COUNT(*) as count FROM modules", fetch='one')['count']
    experiments_count = query_db("SELECT COUNT(*) as count FROM experiments", fetch='one')['count']
    pdf_count = query_db("SELECT COUNT(*) as count FROM pdf_resources", fetch='one')['count']
    
    return render_template(
        'index.html',
        stats={
            'modules': modules_count,
            'experiments': experiments_count,
            'tools': 8,
            'resources': pdf_count
        }
    )

@app.route('/modules')
def modules_page():
    """Modules section displaying the five modules, expandable subtopics, and PDF resources."""
    modules = query_db("SELECT * FROM modules ORDER BY id ASC", fetch='all')
    for m in modules:
        subtopics = query_db("""
            SELECT s.*, p.id as pdf_id, p.file_name as pdf_file_name, p.file_path as pdf_file_path
            FROM subtopics s
            LEFT JOIN pdf_resources p ON s.id = p.subtopic_id
            WHERE s.module_id = %s
            ORDER BY s.display_order ASC, s.id ASC
        """, (m['id'],), fetch='all')
        m['subtopics'] = subtopics
    return render_template('modules.html', modules=modules)

@app.route('/modules/<int:module_id>')
def module_details_page(module_id):
    """Detailed view for a specific module."""
    module = query_db("SELECT * FROM modules WHERE id = %s", (module_id,), fetch='one')
    if not module:
        abort(404)
    subtopics = query_db("""
        SELECT s.*, p.id as pdf_id, p.file_name as pdf_file_name, p.file_path as pdf_file_path
        FROM subtopics s
        LEFT JOIN pdf_resources p ON s.id = p.subtopic_id
        WHERE s.module_id = %s
        ORDER BY s.display_order ASC, s.id ASC
    """, (module_id,), fetch='all')
    module['subtopics'] = subtopics
    all_modules = query_db("SELECT id, module_number, title FROM modules ORDER BY id ASC", fetch='all')
    return render_template('module_details.html', module=module, all_modules=all_modules)

@app.route('/pdf-viewer/<int:resource_id>')
def pdf_viewer_page(resource_id):
    """Dedicated embedded PDF reading page."""
    resource = query_db("""
        SELECT p.*, s.title as subtopic_title, s.description as subtopic_desc, 
               m.id as module_id, m.module_number, m.title as module_title
        FROM pdf_resources p
        JOIN subtopics s ON p.subtopic_id = s.id
        JOIN modules m ON s.module_id = m.id
        WHERE p.id = %s
    """, (resource_id,), fetch='one')
    if not resource:
        abort(404)
    return render_template('pdf_viewer.html', resource=resource)

@app.route('/lab-execution')
def lab_execution_page():
    """Lab Execution section listing executed experiments with Add and Delete capabilities."""
    experiments = query_db("SELECT * FROM experiments ORDER BY CAST(experiment_no AS UNSIGNED) ASC, id ASC", fetch='all')
    for exp in experiments:
        subs = query_db("SELECT * FROM sub_experiments WHERE experiment_id = %s ORDER BY letter ASC", (exp['id'],), fetch='all')
        exp['sub_experiments'] = subs
    return render_template('lab_execution.html', experiments=experiments)

@app.route('/experiment/<int:exp_id>')
def experiment_details_page(exp_id):
    """Full detail view for an experiment with sticky sidebar and two-column reading panel."""
    exp = query_db("SELECT * FROM experiments WHERE id = %s", (exp_id,), fetch='one')
    if not exp:
        abort(404)
    subs = query_db("SELECT * FROM sub_experiments WHERE experiment_id = %s ORDER BY letter ASC", (exp['id'],), fetch='all')
    media = query_db("SELECT * FROM experiment_media WHERE experiment_id = %s", (exp['id'],), fetch='all')
    all_exps = query_db("SELECT id, experiment_no, title FROM experiments ORDER BY CAST(experiment_no AS UNSIGNED) ASC", fetch='all')
    return render_template('experiment_details.html', experiment=exp, sub_experiments=subs, media=media, all_experiments=all_exps)

# --------------------------------------------------------------------------
# Administrator Auth & Management
# --------------------------------------------------------------------------
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Admin login page and authentication."""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        admin = query_db("SELECT * FROM admins WHERE username = %s", (username,), fetch='one')
        if admin and check_password_hash(admin['password_hash'], password):
            session['admin_logged_in'] = True
            session['admin_username'] = admin['username']
            flash('Logged in successfully.', 'success')
            next_url = request.args.get('next') or url_for('admin_resources')
            return redirect(next_url)
        else:
            flash('Invalid admin username or password.', 'error')
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    session.pop('admin_username', None)
    flash('Logged out successfully.', 'info')
    return redirect(url_for('home'))

@app.route('/admin/resources')
@admin_required
def admin_resources():
    """Administrator resource management interface."""
    modules = query_db("SELECT * FROM modules ORDER BY id ASC", fetch='all')
    for m in modules:
        m['subtopics'] = query_db("""
            SELECT s.*, p.id as pdf_id, p.file_name, p.file_path, p.uploaded_at
            FROM subtopics s
            LEFT JOIN pdf_resources p ON s.id = p.subtopic_id
            WHERE s.module_id = %s
            ORDER BY s.display_order ASC, s.id ASC
        """, (m['id'],), fetch='all')
    return render_template('admin_resources.html', modules=modules)

# --------------------------------------------------------------------------
# PDF Streaming & Download API
# --------------------------------------------------------------------------
@app.route('/api/pdf/read/<int:resource_id>')
def api_pdf_read(resource_id):
    """Streams the PDF file for reading inside the browser embedded viewer."""
    resource = query_db("SELECT * FROM pdf_resources WHERE id = %s", (resource_id,), fetch='one')
    if not resource:
        abort(404, description="PDF resource not found.")

    file_path_value = resource['file_path']
    if str(file_path_value).startswith('http://') or str(file_path_value).startswith('https://'):
        return redirect(file_path_value)

    file_path = os.path.join(BASE_DIR, file_path_value)
    if not os.path.exists(file_path):
        abort(404, description="PDF file not found on disk.")

    return send_file(
        file_path,
        mimetype='application/pdf',
        as_attachment=False,
        download_name=resource['file_name']
    )

@app.route('/api/pdf/download/<int:resource_id>')
def api_pdf_download(resource_id):
    """Downloads the PDF file to the user's device."""
    resource = query_db("SELECT * FROM pdf_resources WHERE id = %s", (resource_id,), fetch='one')
    if not resource:
        abort(404, description="PDF resource not found.")

    file_path_value = resource['file_path']
    if str(file_path_value).startswith('http://') or str(file_path_value).startswith('https://'):
        return redirect(file_path_value)

    file_path = os.path.join(BASE_DIR, file_path_value)
    if not os.path.exists(file_path):
        abort(404, description="PDF file not found on disk.")

    return send_file(
        file_path,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=resource['file_name']
    )

# --------------------------------------------------------------------------
# REST API Endpoints (Profile, Modules, Experiments, Admin CRUD)
# --------------------------------------------------------------------------
@app.route('/api/profile', methods=['GET', 'PUT'])
def api_profile():
    if request.method == 'GET':
        profile = query_db("SELECT * FROM students WHERE id = 1", fetch='one')
        if not profile:
            return jsonify({'error': 'Profile not found'}), 404
        return jsonify(profile)
    
    # PUT update
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    register_no = data.get('register_no') or data.get('roll', '').strip()
    section = data.get('section', '').strip()
    branch = data.get('branch', '').strip()
    faculty_name = data.get('faculty_name') or data.get('assistantProfessor', '').strip()
    github_url = data.get('github_url') or data.get('githubRepo', '').strip()
    photo_url = data.get('photo_url') or data.get('photo', '').strip()

    query_db("""
        UPDATE students SET 
            name = COALESCE(NULLIF(%s, ''), name),
            register_no = COALESCE(NULLIF(%s, ''), register_no),
            section = COALESCE(NULLIF(%s, ''), section),
            branch = COALESCE(NULLIF(%s, ''), branch),
            faculty_name = COALESCE(NULLIF(%s, ''), faculty_name),
            github_url = %s,
            photo_url = COALESCE(NULLIF(%s, ''), photo_url)
        WHERE id = 1
    """, (name, register_no, section, branch, faculty_name, github_url, photo_url), commit=True)

    updated = query_db("SELECT * FROM students WHERE id = 1", fetch='one')
    return jsonify(updated)

@app.route('/api/profile/photo', methods=['POST'])
def api_profile_photo():
    """Upload photo for student profile."""
    if 'photo' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['photo']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if file and allowed_file(file.filename, ALLOWED_EXTENSIONS_IMG):
        if os.getenv('FLASK_ENV') == 'production' and not storage_is_configured():
            return jsonify({'error': 'Cloud storage is not configured: set CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, and CLOUDINARY_API_SECRET.'}), 500
        upload_meta = upload_to_storage(file, 'students', 'student_profile')
        photo_url = upload_meta['url']
        query_db("UPDATE students SET photo_url = %s WHERE id = 1", (photo_url,), commit=True)
        return jsonify({'photo_url': photo_url})
    return jsonify({'error': 'Invalid image file format'}), 400

@app.route('/api/modules', methods=['GET'])
def api_modules():
    """Returns all modules with their subtopics and PDF resources."""
    query = request.args.get('q', '').strip().lower()
    modules = query_db("SELECT * FROM modules ORDER BY id ASC", fetch='all')
    for m in modules:
        subtopics = query_db("""
            SELECT s.*, p.id as pdf_id, p.file_name, p.file_path, p.uploaded_at
            FROM subtopics s
            LEFT JOIN pdf_resources p ON s.id = p.subtopic_id
            WHERE s.module_id = %s
            ORDER BY s.display_order ASC, s.id ASC
        """, (m['id'],), fetch='all')
        m['subtopics'] = subtopics
    
    if query:
        # Filter modules or subtopics matching query
        filtered = []
        for m in modules:
            match_module = query in m['title'].lower() or query in m['module_number'].lower() or query in (m['description'] or '').lower()
            matching_subs = [s for s in m['subtopics'] if query in s['title'].lower() or query in (s['description'] or '').lower()]
            if match_module or matching_subs:
                m_copy = dict(m)
                if not match_module:
                    m_copy['subtopics'] = matching_subs
                filtered.append(m_copy)
        return jsonify(filtered)
    
    return jsonify(modules)

@app.route('/api/modules/add-topic', methods=['POST'])
def api_add_topic():
    """Allows uploading a new topic and associated PDF directly from the Modules page."""
    module_id = request.form.get('module_id')
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()

    if not module_id or not title:
        return jsonify({'error': 'Module and topic title are required.'}), 400

    mod = query_db("SELECT id, module_number FROM modules WHERE id = %s", (module_id,), fetch='one')
    if not mod:
        return jsonify({'error': 'Selected module not found.'}), 404

    # Calculate next display_order
    max_order = query_db("SELECT MAX(display_order) as m FROM subtopics WHERE module_id = %s", (module_id,), fetch='one')
    next_order = (max_order['m'] or 0) + 1 if max_order else 1

    sub_id = query_db("""
        INSERT INTO subtopics (module_id, title, description, display_order)
        VALUES (%s, %s, %s, %s)
    """, (module_id, title, description, next_order), commit=True)

    pdf_id = None
    if 'pdf_file' in request.files and request.files['pdf_file'].filename:
        pfile = request.files['pdf_file']
        if allowed_file(pfile.filename, ALLOWED_EXTENSIONS_PDF):
            if os.getenv('FLASK_ENV') == 'production' and not storage_is_configured():
                return jsonify({'error': 'Cloud storage is not configured: set CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, and CLOUDINARY_API_SECRET.'}), 500
            upload_meta = upload_to_storage(pfile, f'modules/module_{module_id}', f'subtopic_{sub_id}')
            rel_path = upload_meta.get('path') or upload_meta['url']
            pdf_id = query_db("""
                INSERT INTO pdf_resources (subtopic_id, file_name, file_path)
                VALUES (%s, %s, %s)
            """, (sub_id, pfile.filename, rel_path), commit=True)

    return jsonify({
        'success': True,
        'subtopic_id': sub_id,
        'pdf_id': pdf_id,
        'module_id': module_id,
        'title': title
    }), 201

# --- Admin Module & Subtopic Endpoints ---
@app.route('/api/admin/modules', methods=['POST'])
@admin_required
def api_admin_save_module():
    """Create or update a module title and description."""
    data = request.get_json() or {}
    module_id = data.get('id')
    module_number = data.get('module_number', '').strip()
    title = data.get('title', '').strip()
    description = data.get('description', '').strip()

    if not title:
        return jsonify({'error': 'Module title is required.'}), 400

    if module_id:
        query_db("""
            UPDATE modules SET module_number = %s, title = %s, description = %s
            WHERE id = %s
        """, (module_number, title, description, module_id), commit=True)
        return jsonify({'success': True, 'id': module_id})
    else:
        new_id = query_db("""
            INSERT INTO modules (module_number, title, description)
            VALUES (%s, %s, %s)
        """, (module_number, title, description), commit=True)
        return jsonify({'success': True, 'id': new_id})

@app.route('/api/admin/subtopics', methods=['POST'])
@admin_required
def api_admin_save_subtopic():
    """Create or update a subtopic."""
    data = request.get_json() or {}
    subtopic_id = data.get('id')
    module_id = data.get('module_id')
    title = data.get('title', '').strip()
    description = data.get('description', '').strip()
    display_order = data.get('display_order', 1)

    if not module_id or not title:
        return jsonify({'error': 'Module ID and subtopic title are required.'}), 400

    if subtopic_id:
        query_db("""
            UPDATE subtopics SET title = %s, description = %s, display_order = %s
            WHERE id = %s AND module_id = %s
        """, (title, description, display_order, subtopic_id, module_id), commit=True)
        return jsonify({'success': True, 'id': subtopic_id})
    else:
        new_id = query_db("""
            INSERT INTO subtopics (module_id, title, description, display_order)
            VALUES (%s, %s, %s, %s)
        """, (module_id, title, description, display_order), commit=True)
        return jsonify({'success': True, 'id': new_id})

@app.route('/api/admin/subtopics/<int:subtopic_id>', methods=['DELETE'])
@admin_required
def api_admin_delete_subtopic(subtopic_id):
    """Delete a subtopic and its associated PDF."""
    pdf = query_db("SELECT file_path FROM pdf_resources WHERE subtopic_id = %s", (subtopic_id,), fetch='one')
    if pdf:
        file_path_value = pdf['file_path']
        if not str(file_path_value).startswith('http://') and not str(file_path_value).startswith('https://'):
            full_p = os.path.join(BASE_DIR, file_path_value)
            if os.path.exists(full_p):
                try:
                    os.remove(full_p)
                except Exception:
                    pass
    query_db("DELETE FROM subtopics WHERE id = %s", (subtopic_id,), commit=True)
    return jsonify({'success': True})

@app.route('/api/admin/upload-pdf', methods=['POST'])
@admin_required
def api_admin_upload_pdf():
    """Upload or replace a PDF file for a subtopic."""
    subtopic_id = request.form.get('subtopic_id')
    if not subtopic_id:
        return jsonify({'error': 'Subtopic ID is required.'}), 400
    
    subtopic = query_db("SELECT s.*, m.id as module_id FROM subtopics s JOIN modules m ON s.module_id = m.id WHERE s.id = %s", (subtopic_id,), fetch='one')
    if not subtopic:
        return jsonify({'error': 'Subtopic not found.'}), 404

    if 'pdf_file' not in request.files:
        return jsonify({'error': 'No PDF file selected.'}), 400
    
    file = request.files['pdf_file']
    if file.filename == '' or not allowed_file(file.filename, ALLOWED_EXTENSIONS_PDF):
        return jsonify({'error': 'Please select a valid .pdf file.'}), 400

    if os.getenv('FLASK_ENV') == 'production' and not storage_is_configured():
        return jsonify({'error': 'Cloud storage is not configured: set CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, and CLOUDINARY_API_SECRET.'}), 500

    upload_meta = upload_to_storage(file, f'modules/module_{subtopic["module_id"]}', f'subtopic_{subtopic_id}')
    rel_path = upload_meta.get('path') or upload_meta['url']

    # Check if a PDF resource already exists for this subtopic
    existing_pdf = query_db("SELECT id, file_path FROM pdf_resources WHERE subtopic_id = %s", (subtopic_id,), fetch='one')
    if existing_pdf:
        # Delete old file from disk if different
        old_path = os.path.join(BASE_DIR, existing_pdf['file_path'])
        if os.path.exists(old_path) and old_path != abs_save_path:
            try:
                os.remove(old_path)
            except Exception:
                pass
        query_db("""
            UPDATE pdf_resources SET file_name = %s, file_path = %s, uploaded_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (file.filename, rel_path, existing_pdf['id']), commit=True)
        pdf_id = existing_pdf['id']
    else:
        pdf_id = query_db("""
            INSERT INTO pdf_resources (subtopic_id, file_name, file_path)
            VALUES (%s, %s, %s)
        """, (subtopic_id, file.filename, rel_path), commit=True)

    return jsonify({
        'success': True,
        'pdf_id': pdf_id,
        'file_name': file.filename,
        'file_path': rel_path
    })

@app.route('/api/admin/pdf/<int:resource_id>', methods=['DELETE'])
@admin_required
def api_admin_delete_pdf(resource_id):
    """Delete a PDF resource."""
    resource = query_db("SELECT * FROM pdf_resources WHERE id = %s", (resource_id,), fetch='one')
    if not resource:
        return jsonify({'error': 'PDF resource not found.'}), 404

    file_path_value = resource['file_path']
    if not str(file_path_value).startswith('http://') and not str(file_path_value).startswith('https://'):
        abs_path = os.path.join(BASE_DIR, file_path_value)
        if os.path.exists(abs_path):
            try:
                os.remove(abs_path)
            except Exception:
                pass

    query_db("DELETE FROM pdf_resources WHERE id = %s", (resource_id,), commit=True)
    return jsonify({'success': True})

# --- Lab Execution / Experiments API ---
@app.route('/api/experiments', methods=['GET', 'POST'])
def api_experiments():
    if request.method == 'GET':
        query = request.args.get('q', '').strip().lower()
        experiments = query_db("SELECT * FROM experiments ORDER BY CAST(experiment_no AS UNSIGNED) ASC, id ASC", fetch='all')
        for exp in experiments:
            exp['sub_experiments'] = query_db("SELECT * FROM sub_experiments WHERE experiment_id = %s ORDER BY letter ASC", (exp['id'],), fetch='all')
            exp['media'] = query_db("SELECT * FROM experiment_media WHERE experiment_id = %s", (exp['id'],), fetch='all')
        
        if query:
            filtered = [
                e for e in experiments 
                if query in str(e['experiment_no']).lower() 
                or query in (e['title'] or '').lower() 
                or query in (e['short_description'] or '').lower()
            ]
            return jsonify(filtered)
        return jsonify(experiments)

    # POST add/update experiment
    # Accepts multipart form data or json
    if request.is_json:
        data = request.get_json()
        exp_no = str(data.get('experiment_no') or data.get('number', '')).strip()
        title = data.get('title') or data.get('name', '').strip()
        short_desc = data.get('short_description') or data.get('shortDescription', '').strip()
        cover_image = data.get('cover_image') or data.get('cover', '').strip()
        d2_heading = data.get('d2_heading') or data.get('d2Heading', 'Experiment Implementation Details').strip()
        long_content = data.get('long_content') or data.get('d2Content', '').strip()
        github_url = data.get('github_url') or data.get('githubUrl', '').strip()
        code_file_name = data.get('code_file_name', '')
        code_file_path = data.get('code_file_path', '')
        code_content = data.get('code_content', '')
        output_image = data.get('output_image', '')
        output_text = data.get('output_text', '')
        sub_experiments = data.get('sub_experiments') or data.get('subExperiments', [])
    else:
        exp_no = request.form.get('number', '').strip()
        title = request.form.get('name', '').strip()
        short_desc = request.form.get('description', '').strip()
        d2_heading = request.form.get('d2Heading', 'Experiment Implementation Details').strip()
        long_content = request.form.get('d2Content', '').strip()
        github_url = request.form.get('github', '').strip()
        output_text = request.form.get('output_text', '').strip()
        cover_image = ''
        code_file_name = ''
        code_file_path = ''
        code_content = request.form.get('code_content', '').strip()
        output_image = ''
        
        # Check uploaded cover file
        if 'cover' in request.files and request.files['cover'].filename:
            cfile = request.files['cover']
            if allowed_file(cfile.filename, ALLOWED_EXTENSIONS_IMG):
                if os.getenv('FLASK_ENV') == 'production' and not storage_is_configured():
                    return jsonify({'error': 'Cloud storage is not configured: set CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, and CLOUDINARY_API_SECRET.'}), 500
                upload_meta = upload_to_storage(cfile, 'experiments/images', f'exp_{exp_no}_cover')
                cover_image = upload_meta.get('url') or upload_meta.get('path')

        # Check uploaded execution code file
        if 'code_file' in request.files and request.files['code_file'].filename:
            cd_file = request.files['code_file']
            if allowed_file(cd_file.filename, ALLOWED_EXTENSIONS_CODE):
                if os.getenv('FLASK_ENV') == 'production' and not storage_is_configured():
                    return jsonify({'error': 'Cloud storage is not configured: set CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, and CLOUDINARY_API_SECRET.'}), 500
                upload_meta = upload_to_storage(cd_file, 'experiments/code', f'exp_{exp_no}_code')
                code_file_name = cd_file.filename
                code_file_path = upload_meta.get('path') or upload_meta.get('url')
                extracted = extract_code_from_file(cd_file, os.path.join(app.config['UPLOAD_FOLDER'], 'experiments', 'code', f"exp_{exp_no}_{secure_filename(cd_file.filename)}"))
                code_content = extracted

        # Check uploaded execution output image
        if 'output_image_file' in request.files and request.files['output_image_file'].filename:
            out_img = request.files['output_image_file']
            if allowed_file(out_img.filename, ALLOWED_EXTENSIONS_IMG):
                if os.getenv('FLASK_ENV') == 'production' and not storage_is_configured():
                    return jsonify({'error': 'Cloud storage is not configured: set CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, and CLOUDINARY_API_SECRET.'}), 500
                upload_meta = upload_to_storage(out_img, 'experiments/outputs', f'exp_{exp_no}_output')
                output_image = upload_meta.get('url') or upload_meta.get('path')

        sub_experiments = []

    if not exp_no or not title:
        return jsonify({'error': 'Experiment number and name are required.'}), 400

    if not cover_image:
        cover_image = output_image or '/static/images/exp1_cover.svg'
    if not output_image:
        output_image = cover_image

    exp_id = query_db("""
        INSERT INTO experiments (experiment_no, title, short_description, cover_image, d2_heading, long_content, code_file_name, code_file_path, code_content, output_image, output_text, github_url)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (exp_no, title, short_desc, cover_image, d2_heading, long_content, code_file_name, code_file_path, code_content, output_image, output_text, github_url), commit=True)

    # Insert sub_experiments if provided
    for s in sub_experiments:
        letter = s.get('letter', 'A')
        stitle = s.get('title', '')
        sdesc = s.get('shortDescription', '')
        s_d2head = s.get('d2Heading', f'Sub-Experiment {exp_no}{letter}')
        s_d2content = s.get('d2Content', '')
        s_cover = s.get('cover', cover_image)
        query_db("""
            INSERT INTO sub_experiments (experiment_id, letter, title, short_description, d2_heading, long_content, cover_image)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (exp_id, letter, stitle, sdesc, s_d2head, s_d2content, s_cover), commit=True)

    new_exp = query_db("SELECT * FROM experiments WHERE id = %s", (exp_id,), fetch='one')
    new_exp['sub_experiments'] = query_db("SELECT * FROM sub_experiments WHERE experiment_id = %s", (exp_id,), fetch='all')
    return jsonify(new_exp), 201

@app.route('/api/experiments/<int:exp_id>/upload-execution', methods=['POST'])
def api_upload_execution(exp_id):
    """Allows uploading or updating the executed code file and execution output for an experiment."""
    exp = query_db("SELECT * FROM experiments WHERE id = %s", (exp_id,), fetch='one')
    if not exp:
        return jsonify({'error': 'Experiment not found.'}), 404

    title = request.form.get('title', exp['title']).strip()
    short_desc = request.form.get('description', exp['short_description']).strip()
    output_text = request.form.get('output_text', exp.get('output_text') or '').strip()
    
    code_file_name = exp.get('code_file_name') or ''
    code_file_path = exp.get('code_file_path') or ''
    code_content = exp.get('code_content') or ''
    output_image = exp.get('output_image') or exp.get('cover_image') or ''

    # Code file upload
    if 'code_file' in request.files and request.files['code_file'].filename:
        cfile = request.files['code_file']
        if allowed_file(cfile.filename, ALLOWED_EXTENSIONS_CODE):
            if os.getenv('FLASK_ENV') == 'production' and not storage_is_configured():
                return jsonify({'error': 'Cloud storage is not configured: set CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, and CLOUDINARY_API_SECRET.'}), 500
            upload_meta = upload_to_storage(cfile, 'experiments/code', f"exp_{exp['experiment_no']}_code")
            clean_name = secure_filename(cfile.filename)
            save_name = f"exp_{exp['experiment_no']}_{clean_name}"
            abs_p = os.path.join(app.config['UPLOAD_FOLDER'], 'experiments', 'code', save_name)
            code_content = extract_code_from_file(cfile, abs_p)
            code_file_name = cfile.filename
            code_file_path = upload_meta.get('path') or upload_meta.get('url')

    # Output image upload
    if 'output_image' in request.files and request.files['output_image'].filename:
        ofile = request.files['output_image']
        if allowed_file(ofile.filename, ALLOWED_EXTENSIONS_IMG):
            if os.getenv('FLASK_ENV') == 'production' and not storage_is_configured():
                return jsonify({'error': 'Cloud storage is not configured: set CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, and CLOUDINARY_API_SECRET.'}), 500
            upload_meta = upload_to_storage(ofile, 'experiments/outputs', f"exp_{exp['experiment_no']}_output")
            output_image = upload_meta.get('url') or upload_meta.get('path')

    query_db("""
        UPDATE experiments SET 
            title = %s,
            short_description = %s,
            code_file_name = %s,
            code_file_path = %s,
            code_content = %s,
            output_image = %s,
            output_text = %s
        WHERE id = %s
    """, (title, short_desc, code_file_name, code_file_path, code_content, output_image, output_text, exp_id), commit=True)

    updated = query_db("SELECT * FROM experiments WHERE id = %s", (exp_id,), fetch='one')
    return jsonify({
        'success': True,
        'experiment': updated
    })

@app.route('/api/experiments/<int:exp_id>/download-code')
def api_download_code(exp_id):
    """Downloads the executed code file."""
    exp = query_db("SELECT * FROM experiments WHERE id = %s", (exp_id,), fetch='one')
    if not exp:
        abort(404)
    
    code_path = exp.get('code_file_path')
    if code_path:
        full_p = os.path.join(BASE_DIR, code_path)
        if os.path.exists(full_p):
            return send_file(full_p, as_attachment=True, download_name=exp.get('code_file_name') or f"experiment_{exp['experiment_no']}.py")

    # If code is in database content but not on disk
    content = exp.get('code_content') or '# No code recorded'
    filename = exp.get('code_file_name') or f"experiment_{exp['experiment_no']}.py"
    return send_file(
        io.BytesIO(content.encode('utf-8')),
        mimetype='text/plain',
        as_attachment=True,
        download_name=filename
    )

@app.route('/api/experiments/<int:exp_id>', methods=['GET', 'DELETE'])
def api_experiment_single(exp_id):
    if request.method == 'GET':
        exp = query_db("SELECT * FROM experiments WHERE id = %s", (exp_id,), fetch='one')
        if not exp:
            return jsonify({'error': 'Experiment not found'}), 404
        exp['sub_experiments'] = query_db("SELECT * FROM sub_experiments WHERE experiment_id = %s ORDER BY letter ASC", (exp_id,), fetch='all')
        exp['media'] = query_db("SELECT * FROM experiment_media WHERE experiment_id = %s", (exp_id,), fetch='all')
        return jsonify(exp)

    # DELETE
    exp = query_db("SELECT * FROM experiments WHERE id = %s", (exp_id,), fetch='one')
    if not exp:
        return jsonify({'error': 'Experiment not found'}), 404
    
    query_db("DELETE FROM experiments WHERE id = %s", (exp_id,), commit=True)
    return jsonify({'success': True, 'message': f'Experiment {exp_id} deleted.'})

# --- File Serving ---
@app.route('/uploads/<path:filename>')
def serve_uploads(filename):
    """Securely serve uploaded images, PDFs, and videos."""
    safe_dir = app.config['UPLOAD_FOLDER']
    full_path = os.path.abspath(os.path.join(safe_dir, filename))
    if not full_path.startswith(os.path.abspath(safe_dir)):
        abort(403)
    if not os.path.exists(full_path):
        abort(404)
    mime, _ = mimetypes.guess_type(full_path)
    return send_file(full_path, mimetype=mime or 'application/octet-stream')

if __name__ == '__main__':
    init_db()
    port = int(os.getenv('PORT', 5000))
    print(f"==================================================")
    print(f" DS LAB PORTAL RUNNING AT http://127.0.0.1:{port}")
    print(f"==================================================")
    app.run(host='0.0.0.0', port=port, debug=True)
