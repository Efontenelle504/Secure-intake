import os
import secrets
import logging
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, make_response, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from crypto_utils import get_fernet, encrypt_dict, decrypt_dict
import json
import re
import qrcode
import io
import base64
from functools import wraps

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

# Create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key-change-in-production")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Configure the database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///secure_intake.db")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# Initialize the app with the extension
db.init_app(app)

# Test encryption key on startup - fail fast if invalid
try:
    fernet = get_fernet()
    logger.info("Encryption key validated successfully")
except Exception as e:
    logger.error(f"Failed to initialize encryption: {e}")
    raise

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = 'Please log in to access this page.'

@login_manager.user_loader
def load_user(user_id):
    from models import User
    return User.query.get(int(user_id))

with app.app_context():
    # Import models after app is initialized to avoid circular imports
    import models
    from models import Intake, User  # Import the models for use in routes
    db.create_all()
    logger.info("Database tables created successfully")

@app.before_request
def add_security_headers():
    """Add security headers to all responses"""
    pass

@app.after_request
def apply_security_headers(response):
    """Apply security headers to all responses"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, private'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    # TODO: Add HSTS and CSP headers in production behind HTTPS
    return response

def generate_csrf_token():
    """Generate a CSRF token"""
    if 'csrf_token' not in request.cookies:
        token = secrets.token_urlsafe(32)
    else:
        token = request.cookies.get('csrf_token')
    return token

def validate_csrf_token():
    """Validate CSRF token for POST requests"""
    if request.method == 'POST':
        token = request.form.get('_csrf')
        cookie_token = request.cookies.get('csrf_token')
        if not token or not cookie_token or token != cookie_token:
            flash('Security token validation failed. Please try again.', 'error')
            return False
    return True

def admin_required(f):
    """Decorator to require admin role"""
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin():
            flash('Admin access required.', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def role_required(roles):
    """Decorator to require specific roles"""
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            if current_user.role not in roles:
                flash('Insufficient permissions.', 'error')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def validate_intake_data(data):
    """Validate intake form data"""
    errors = []
    
    # Required fields
    required_fields = [
        'first_name', 'last_name', 'email', 'mobile_phone', 'ssn', 'dob',
        'employer', 'occupation', 'monthly_income', 'employment_status', 
        'driver_license_number', 'driver_license_state', 'address_line1', 
        'city', 'state', 'zip', 'project_cost'
    ]
    
    for field in required_fields:
        if not data.get(field, '').strip():
            errors.append(f'{field.replace("_", " ").title()} is required')
    
    # Consent checkboxes are required
    if not data.get('consent_soft_pull'):
        errors.append('Consent for soft credit pull is required')
    if not data.get('consent_share'):
        errors.append('Consent to share information with lenders is required')
    
    # Validate zip code (5 digits)
    zip_code = data.get('zip', '').strip()
    if zip_code and not re.match(r'^\d{5}$', zip_code):
        errors.append('ZIP code must be exactly 5 digits')
    
    # Validate state (2 letters)
    state = data.get('state', '').strip()
    if state and not re.match(r'^[A-Z]{2}$', state.upper()):
        errors.append('State must be exactly 2 letters')
    
    # Validate date of birth (MM/DD/YYYY)
    dob = data.get('dob', '').strip()
    if dob:
        if not re.match(r'^\d{2}/\d{2}/\d{4}$', dob):
            errors.append('Date of birth must be in MM/DD/YYYY format')
    
    # Validate email format
    email = data.get('email', '').strip()
    if email and not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email):
        errors.append('Invalid email format')
    
    # Validate phone number format
    mobile_phone = data.get('mobile_phone', '').strip()
    if mobile_phone:
        phone_digits = ''.join(filter(str.isdigit, mobile_phone))
        if len(phone_digits) != 10:
            errors.append('Mobile phone must be exactly 10 digits')
    
    # Validate SSN format
    ssn = data.get('ssn', '').strip()
    if ssn:
        ssn_digits = ''.join(filter(str.isdigit, ssn))
        if len(ssn_digits) != 9:
            errors.append('Social Security Number must be exactly 9 digits')
    
    # Validate numeric fields
    numeric_fields = ['monthly_income', 'project_cost']
    for field in numeric_fields:
        value = data.get(field, '').strip()
        if value:
            try:
                float(value)
            except ValueError:
                errors.append(f'{field.replace("_", " ").title()} must be a valid number')
    
    # Validate additional income sources if present
    if data.get('additional_income'):
        for i, income in enumerate(data['additional_income']):
            try:
                float(income['amount'])
            except (ValueError, KeyError):
                errors.append(f'Additional income source {i+1} amount must be a valid number')
    
    # Validate co-applicant data if present
    if data.get('co_applicant'):
        co_data = data['co_applicant']
        
        # Co-applicant phone validation
        if co_data.get('co_mobile_phone'):
            phone_digits = ''.join(filter(str.isdigit, co_data['co_mobile_phone']))
            if len(phone_digits) != 10:
                errors.append('Co-applicant mobile phone must be exactly 10 digits')
        
        # Co-applicant SSN validation
        if co_data.get('co_ssn'):
            ssn_digits = ''.join(filter(str.isdigit, co_data['co_ssn']))
            if len(ssn_digits) != 9:
                errors.append('Co-applicant Social Security Number must be exactly 9 digits')
        
        # Co-applicant date validation
        if co_data.get('co_dob'):
            if not re.match(r'^\d{2}/\d{2}/\d{4}$', co_data['co_dob']):
                errors.append('Co-applicant date of birth must be in MM/DD/YYYY format')
        
        # Co-applicant income validation
        if co_data.get('co_monthly_income'):
            try:
                float(co_data['co_monthly_income'])
            except ValueError:
                errors.append('Co-applicant monthly income must be a valid number')
    
    return errors

def build_generic_payload(data, lender):
    """Build a generic JSON payload for lender submission"""
    return {
        "lender": lender,
        "applicant": {
            "firstName": data.get('first_name', ''),
            "lastName": data.get('last_name', ''),
            "email": data.get('email', ''),
            "phone": data.get('mobile_phone', ''),
            "ssn": data.get('ssn', ''),
            "dob": data.get('dob', ''),
            "employer": data.get('employer', ''),
            "occupation": data.get('occupation', ''),
            "monthlyIncome": data.get('monthly_income', ''),
            "employmentStatus": data.get('employment_status', ''),
            "additionalIncome": data.get('additional_income', []),
            "driverLicense": {
                "number": data.get('driver_license_number', ''),
                "state": data.get('driver_license_state', '')
            },
            "address": {
                "line1": data.get('address_line1', ''),
                "line2": data.get('address_line2', ''),
                "city": data.get('city', ''),
                "state": data.get('state', ''),
                "zip": data.get('zip', '')
            }
        },
        "coApplicant": data.get('co_applicant', {}),
        "projectCost": data.get('project_cost', ''),
        "consent": {
            "softPull": bool(data.get('consent_soft_pull')),
            "shareWithLenders": bool(data.get('consent_share'))
        },
        "notes": data.get('notes', '')
    }

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login route with 2FA"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    csrf_token = generate_csrf_token()
    
    if request.method == 'POST':
        if not validate_csrf_token():
            return redirect(url_for('login'))
        
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        totp_token = request.form.get('totp_token', '').strip()
        
        from models import User
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            if user.totp_secret:
                # 2FA is set up, verify token
                if not totp_token:
                    flash('Please enter your Google Authenticator code.', 'error')
                    response = make_response(render_template('login.html', csrf_token=csrf_token, show_2fa=True, username=username))
                    response.set_cookie('csrf_token', csrf_token or '', httponly=True, samesite='Lax')
                    return response
                
                if not user.verify_totp(totp_token):
                    flash('Invalid Google Authenticator code.', 'error')
                    response = make_response(render_template('login.html', csrf_token=csrf_token, show_2fa=True, username=username))
                    response.set_cookie('csrf_token', csrf_token or '', httponly=True, samesite='Lax')
                    return response
            
            login_user(user)
            next_page = request.args.get('next')
            logger.info(f"User {user.username} logged in successfully")
            return redirect(next_page) if next_page else redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password.', 'error')
    
    response = make_response(render_template('login.html', csrf_token=csrf_token))
    response.set_cookie('csrf_token', csrf_token or '', httponly=True, samesite='Lax')
    return response

@app.route('/logout')
@login_required
def logout():
    """Logout route"""
    logger.info(f"User {current_user.username} logged out")
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Registration route (admin only in production)"""
    csrf_token = generate_csrf_token()
    
    if request.method == 'POST':
        if not validate_csrf_token():
            return redirect(url_for('register'))
        
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        role = request.form.get('role', 'salesman')
        
        # Basic validation
        if not username or not email or not password:
            flash('All fields are required.', 'error')
            response = make_response(render_template('register.html', csrf_token=csrf_token))
            response.set_cookie('csrf_token', csrf_token or '', httponly=True, samesite='Lax')
            return response
        
        from models import User
        
        # Check if user already exists
        if User.query.filter_by(username=username).first():
            flash('Username already exists.', 'error')
            response = make_response(render_template('register.html', csrf_token=csrf_token))
            response.set_cookie('csrf_token', csrf_token or '', httponly=True, samesite='Lax')
            return response
        
        if User.query.filter_by(email=email).first():
            flash('Email already exists.', 'error')
            response = make_response(render_template('register.html', csrf_token=csrf_token))
            response.set_cookie('csrf_token', csrf_token or '', httponly=True, samesite='Lax')
            return response
        
        try:
            # Create new user
            user = User()
            user.username = username
            user.email = email
            user.set_password(password)
            user.role = role if role in ['admin', 'salesman'] else 'salesman'
            
            db.session.add(user)
            db.session.commit()
            
            logger.info(f"New user registered: {username} ({role})")
            flash('Registration successful! Please set up Google Authenticator.', 'success')
            return redirect(url_for('setup_2fa', user_id=user.id))
            
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            db.session.rollback()
            flash('An error occurred during registration.', 'error')
    
    response = make_response(render_template('register.html', csrf_token=csrf_token))
    response.set_cookie('csrf_token', csrf_token or '', httponly=True, samesite='Lax')
    return response

@app.route('/setup-2fa/<int:user_id>')
def setup_2fa(user_id):
    """Setup Google Authenticator 2FA"""
    from models import User
    user = User.query.get_or_404(user_id)
    
    # Generate QR code for Google Authenticator
    totp_uri = user.get_totp_uri()
    
    # Generate QR code
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(totp_uri)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert to base64 for display
    img_buffer = io.BytesIO()
    img.save(img_buffer, format='PNG')
    img_base64 = base64.b64encode(img_buffer.getvalue()).decode()
    
    # Save the user's TOTP secret
    db.session.commit()
    
    csrf_token = generate_csrf_token()
    response = make_response(render_template('setup_2fa.html', 
                                           csrf_token=csrf_token,
                                           qr_code=img_base64,
                                           secret=user.totp_secret,
                                           user_id=user.id))
    response.set_cookie('csrf_token', csrf_token or '', httponly=True, samesite='Lax')
    return response

@app.route('/verify-2fa/<int:user_id>', methods=['POST'])
def verify_2fa(user_id):
    """Verify 2FA setup"""
    if not validate_csrf_token():
        return redirect(url_for('setup_2fa', user_id=user_id))
    
    from models import User
    user = User.query.get_or_404(user_id)
    
    token = request.form.get('token', '').strip()
    
    if user.verify_totp(token):
        flash('Google Authenticator setup successfully!', 'success')
        login_user(user)
        return redirect(url_for('dashboard'))
    else:
        flash('Invalid code. Please try again.', 'error')
        return redirect(url_for('setup_2fa', user_id=user_id))

@app.route('/dashboard')
@login_required
def dashboard():
    """User dashboard"""
    csrf_token = generate_csrf_token()
    
    from models import Intake
    
    if current_user.is_admin():
        # Admin can see all records
        recent_records = Intake.query.order_by(Intake.created_at.desc()).limit(10).all()
        total_records = Intake.query.count()
    else:
        # Salesman can only see their own records
        recent_records = Intake.query.filter_by(created_by=current_user.id).order_by(Intake.created_at.desc()).limit(10).all()
        total_records = Intake.query.filter_by(created_by=current_user.id).count()
    
    response = make_response(render_template('dashboard.html', 
                                           csrf_token=csrf_token,
                                           recent_records=recent_records,
                                           total_records=total_records))
    response.set_cookie('csrf_token', csrf_token or '', httponly=True, samesite='Lax')
    return response

def submit_to_ghl(payload):
    """Send lead payload to GoHighLevel webhook when configured."""
    webhook_url = os.environ.get('GHL_WEBHOOK_URL', '').strip()
    if not webhook_url:
        logger.warning('GHL_WEBHOOK_URL not set; lead captured locally only.')
        return False, 'Webhook is not configured.'

    try:
        import urllib.request

        request_payload = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            webhook_url,
            data=request_payload,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )

        with urllib.request.urlopen(req, timeout=10) as response:
            status = response.getcode()

        if 200 <= status < 300:
            return True, None

        logger.error(f'Unexpected GHL status code: {status}')
        return False, f'Unexpected status code: {status}'
    except Exception as exc:
        logger.error(f'Failed to submit lead to GHL: {exc}')
        return False, str(exc)


@app.route('/', methods=['GET', 'POST'])
def index():
    """Public marketing landing page with server-side lead capture."""
    csrf_token = generate_csrf_token()

    if request.method == 'POST':
        if not validate_csrf_token():
            return redirect(url_for('index'))

        form_data = {
            'name': request.form.get('name', '').strip(),
            'phone': request.form.get('phone', '').strip(),
            'email': request.form.get('email', '').strip(),
            'zip': request.form.get('zip', '').strip(),
            'service': request.form.get('service', '').strip(),
            'timeline': request.form.get('timeline', '').strip(),
            'message': request.form.get('message', '').strip(),
            'utm_source': request.form.get('utm_source', '').strip(),
            'utm_medium': request.form.get('utm_medium', '').strip(),
            'utm_campaign': request.form.get('utm_campaign', '').strip(),
            'utm_content': request.form.get('utm_content', '').strip(),
            'utm_term': request.form.get('utm_term', '').strip(),
        }

        errors = []
        if not form_data['name']:
            errors.append('Name is required.')
        if not form_data['phone']:
            errors.append('Phone is required.')
        if not form_data['zip'] or not re.match(r'^\d{5}$', form_data['zip']):
            errors.append('ZIP code must be 5 digits.')
        if form_data['email'] and not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', form_data['email']):
            errors.append('Email format is invalid.')

        if errors:
            for error in errors:
                flash(error, 'error')
            response = make_response(render_template('index.html', csrf_token=csrf_token, form_data=form_data))
            response.set_cookie('csrf_token', csrf_token or '', httponly=True, samesite='Lax')
            return response

        payload = {
            'source': 'website',
            'landing_path': request.path,
            'submitted_at': datetime.utcnow().isoformat() + 'Z',
            'name': form_data['name'],
            'phone': form_data['phone'],
            'email': form_data['email'],
            'zip': form_data['zip'],
            'service': form_data['service'],
            'timeline': form_data['timeline'],
            'message': form_data['message'],
            'utm': {
                'source': form_data['utm_source'],
                'medium': form_data['utm_medium'],
                'campaign': form_data['utm_campaign'],
                'content': form_data['utm_content'],
                'term': form_data['utm_term'],
            },
        }

        submitted, error = submit_to_ghl(payload)
        if submitted:
            logger.info('Lead submitted to GHL successfully.')
        else:
            logger.warning(f'Lead not sent to GHL: {error}')

        session['lead_name'] = form_data['name']
        response = make_response(redirect(url_for('thank_you')))
        response.set_cookie('csrf_token', csrf_token or '', httponly=True, samesite='Lax')
        return response

    response = make_response(render_template('index.html', csrf_token=csrf_token))
    response.set_cookie('csrf_token', csrf_token or '', httponly=True, samesite='Lax')
    return response


@app.route('/thank-you')
def thank_you():
    lead_name = session.get('lead_name')
    return render_template('thank_you.html', lead_name=lead_name)

@app.route('/record/<int:id>')
@login_required
def record(id):
    """Sales view for a specific record - role-based access"""
    csrf_token = generate_csrf_token()
    
    try:
        intake = Intake.query.get_or_404(id)
        
        # Role-based access control
        if not current_user.is_admin() and intake.created_by != current_user.id:
            flash('You can only view records you created.', 'error')
            return redirect(url_for('records'))
        
        decrypted_data = decrypt_dict(intake.encrypted_blob)
        
        response = make_response(render_template('record.html', 
                                               record=intake, 
                                               data=decrypted_data, 
                                               csrf_token=csrf_token))
        response.set_cookie('csrf_token', csrf_token or '', httponly=True, samesite='Lax')
        return response
        
    except Exception as e:
        logger.error(f"Error retrieving record {id}: {e}")
        flash('Error retrieving record. Please try again.', 'error')
        return redirect(url_for('records'))

@app.route('/submit_momnt/<int:id>', methods=['POST'])
def submit_momnt(id):
    """Stub submit to Momnt"""
    if not validate_csrf_token():
        return redirect(url_for('record', id=id))
    
    try:
        intake = Intake.query.get_or_404(id)
        decrypted_data = decrypt_dict(intake.encrypted_blob)
        
        # Build generic payload
        payload = build_generic_payload(decrypted_data, "Momnt")
        
        # Log only the structure, not the actual PII values
        payload_keys = {
            "lender": True,
            "applicant": list(payload["applicant"].keys()),
            "projectCost": True,
            "consent": list(payload["consent"].keys()),
            "notes": True
        }
        logger.info(f"Simulated Momnt submission for record {id} with payload structure: {payload_keys}")
        
        flash('Successfully submitted to Momnt (simulated)', 'success')
        
    except Exception as e:
        logger.error(f"Error submitting to Momnt for record {id}: {e}")
        flash('Error submitting to Momnt. Please try again.', 'error')
    
    return redirect(url_for('record', id=id))

@app.route('/submit_greensky/<int:id>', methods=['POST'])
def submit_greensky(id):
    """Stub submit to GreenSky"""
    if not validate_csrf_token():
        return redirect(url_for('record', id=id))
    
    try:
        intake = Intake.query.get_or_404(id)
        decrypted_data = decrypt_dict(intake.encrypted_blob)
        
        # Build generic payload
        payload = build_generic_payload(decrypted_data, "GreenSky")
        
        # Log only the structure, not the actual PII values
        payload_keys = {
            "lender": True,
            "applicant": list(payload["applicant"].keys()),
            "projectCost": True,
            "consent": list(payload["consent"].keys()),
            "notes": True
        }
        logger.info(f"Simulated GreenSky submission for record {id} with payload structure: {payload_keys}")
        
        flash('Successfully submitted to GreenSky (simulated)', 'success')
        
    except Exception as e:
        logger.error(f"Error submitting to GreenSky for record {id}: {e}")
        flash('Error submitting to GreenSky. Please try again.', 'error')
    
    return redirect(url_for('record', id=id))

@app.route('/records')
@login_required
def records():
    """List of recent records - role-based access"""
    csrf_token = generate_csrf_token()
    
    try:
        from models import Intake
        
        if current_user.is_admin():
            # Admin can see all records
            records = Intake.query.order_by(Intake.created_at.desc()).limit(50).all()
        else:
            # Salesman can only see their own records
            records = Intake.query.filter_by(created_by=current_user.id).order_by(Intake.created_at.desc()).limit(50).all()
        
        response = make_response(render_template('records.html', records=records, csrf_token=csrf_token))
        response.set_cookie('csrf_token', csrf_token or '', httponly=True, samesite='Lax')
        return response
    except Exception as e:
        logger.error(f"Error retrieving records: {e}")
        flash('Error retrieving records. Please try again.', 'error')
        response = make_response(render_template('records.html', records=[], csrf_token=csrf_token))
        response.set_cookie('csrf_token', csrf_token or '', httponly=True, samesite='Lax')
        return response

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
