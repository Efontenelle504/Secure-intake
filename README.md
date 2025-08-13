# Secure Intake Application

A Flask-based customer data collection application designed for sales teams to securely capture and manage customer pre-qualification information for financial/lending services.

## Features

### 🔒 Security First
- **Encryption at Rest**: All customer PII encrypted using Fernet (AES-128 GCM) before database storage
- **Two-Factor Authentication**: Google Authenticator integration with QR code setup
- **Role-Based Access Control**: Administrators see all records, salesmen only see records they created
- **CSRF Protection**: Secure session management with cookie-based CSRF tokens

### 📋 Enhanced Intake Form
- **Smart Field Formatting**: 
  - Phone numbers format as "(504) 892-1202" while typing
  - SSN fields show as dots but become visible when selected
  - Date fields enforce "MM/DD/YYYY" format with auto-formatting
- **Comprehensive Data Collection**:
  - Monthly income before taxes (not annual)
  - Employer and occupation fields
  - Dynamic additional income sources
  - Full co-applicant functionality
- **Mobile Responsive**: Bootstrap-based design optimized for sales team mobile usage

### 👥 User Management
- **User Registration**: Secure registration with role assignment
- **2FA Setup**: Easy Google Authenticator setup with QR codes
- **Dashboard**: Role-specific views showing relevant records
- **Copy-to-Clipboard**: Sales team convenience features for data handling

### 🏢 Lender Integration Ready
- Stubbed endpoints for Momnt and GreenSky integration
- Standardized JSON payload format for easy lender API integration
- Generic payload builder for future integrations

## Technology Stack

- **Backend**: Flask with SQLAlchemy ORM
- **Database**: PostgreSQL with encrypted blob storage
- **Authentication**: Flask-Login + PyOTP for 2FA
- **Encryption**: Cryptography library (Fernet)
- **Frontend**: Jinja2 templates + Bootstrap + Vanilla JavaScript

## Quick Start

### Prerequisites
- Python 3.8+
- PostgreSQL database
- Environment variables (see Configuration)

### Installation

1. Clone the repository:
```bash
git clone <your-repo-url>
cd secure-intake
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
# Required environment variables
export DATABASE_URL="postgresql://username:password@localhost/dbname"
export SESSION_SECRET="your-session-secret-key"
export ENCRYPTION_KEY="your-base64-encoded-32-byte-key"
```

4. Initialize the database:
```bash
python -c "from app import app, db; app.app_context().push(); db.create_all()"
```

5. Run the application:
```bash
python main.py
```

The application will be available at `http://localhost:5000`

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `DATABASE_URL` | PostgreSQL connection string | Yes |
| `SESSION_SECRET` | Flask session secret key | Yes |
| `ENCRYPTION_KEY` | Base64-encoded 32-byte key for data encryption | Yes |

### Generate Encryption Key

To generate a secure encryption key:

```python
from cryptography.fernet import Fernet
key = Fernet.generate_key()
print(key.decode())  # Use this value for ENCRYPTION_KEY
```

## Usage

### First Time Setup

1. **Register an Admin User**: Visit `/register` and create your first user
2. **Set Up 2FA**: Complete the Google Authenticator setup
3. **Create User Accounts**: Admins can create additional salesman accounts
4. **Start Collecting Data**: Begin using the intake form

### User Roles

- **Admin**: Can view all intake records, manage users, access all features
- **Salesman**: Can create intake records and view only their own submissions

### Data Security

All customer PII is encrypted before database storage using industry-standard encryption. Only decrypted data is shown in the application interface - the database contains only encrypted blobs.

## Development

### Project Structure

```
├── app.py              # Main Flask application
├── models.py           # Database models
├── crypto_utils.py     # Encryption utilities
├── main.py            # Application entry point
├── templates/         # Jinja2 templates
├── static/           # CSS, JS, images
└── requirements.txt  # Python dependencies
```

### Adding New Features

1. Update models in `models.py` if database changes needed
2. Add routes in `app.py`
3. Create/update templates in `templates/`
4. Test with both admin and salesman roles

## Security Considerations

- Never log decrypted customer data
- Regularly rotate encryption keys
- Use HTTPS in production
- Keep dependencies updated
- Review access logs regularly

## License

This project is proprietary software for internal use.

## Support

For questions or issues, contact the development team.