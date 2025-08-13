from app import db
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import pyotp

class User(UserMixin, db.Model):
    """Model for user authentication with roles and 2FA"""
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='salesman')  # 'admin' or 'salesman'
    totp_secret = db.Column(db.String(32))  # For Google Authenticator
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationship to intake records
    intake_records = db.relationship('Intake', backref='created_by_user', lazy=True)
    
    def set_password(self, password):
        """Set password hash"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check password against hash"""
        return check_password_hash(self.password_hash, password)
    
    def generate_totp_secret(self):
        """Generate a new TOTP secret for Google Authenticator"""
        self.totp_secret = pyotp.random_base32()
        return self.totp_secret
    
    def get_totp_uri(self):
        """Get TOTP URI for QR code generation"""
        if not self.totp_secret:
            self.generate_totp_secret()
        return pyotp.totp.TOTP(self.totp_secret).provisioning_uri(
            name=self.email,
            issuer_name="Secure Intake"
        )
    
    def verify_totp(self, token):
        """Verify TOTP token from Google Authenticator"""
        if not self.totp_secret:
            return False
        totp = pyotp.TOTP(self.totp_secret)
        return totp.verify(token, valid_window=1)
    
    def is_admin(self):
        """Check if user is admin"""
        return self.role == 'admin'
    
    def is_salesman(self):
        """Check if user is salesman"""
        return self.role == 'salesman'
    
    def __repr__(self):
        return f'<User {self.username} ({self.role})>'

class Intake(db.Model):
    """Model for storing encrypted customer intake data"""
    
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    encrypted_blob = db.Column(db.LargeBinary, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # Track who created the record
    
    def __repr__(self):
        return f'<Intake {self.id} created at {self.created_at}>'
