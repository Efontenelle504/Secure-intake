# Overview

Secure Intake is a Flask-based customer data collection application designed for sales teams to securely capture and manage customer pre-qualification information. The application prioritizes data security through encryption at rest, provides sales-friendly features like copy-to-clipboard functionality, and includes stubbed integrations with lender services (Momnt and GreenSky). The system is built with a security-first approach, encrypting all personally identifiable information (PII) before database storage and providing a clean, mobile-responsive interface optimized for sales team workflows.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Backend Architecture
- **Framework**: Flask web application with SQLAlchemy ORM for database operations
- **Database**: SQLite with a simple schema storing encrypted customer data as binary blobs
- **Security Layer**: Fernet (AES-128 GCM) encryption for all PII data at rest
- **Session Management**: Flask sessions with CSRF protection using cookie-based tokens
- **Environment Configuration**: Environment variables for sensitive configuration (encryption keys, database URLs)

## Data Model Design
- **Single Table Approach**: `Intake` model with minimal schema (id, timestamps, encrypted_blob)
- **Encrypted Storage**: All customer PII stored as encrypted JSON blobs rather than individual database columns
- **No PII in Logs**: Strict policy preventing decrypted customer data from appearing in application logs

## Frontend Architecture
- **Template Engine**: Jinja2 templates with Bootstrap for responsive UI
- **Client-Side Features**: JavaScript-based copy-to-clipboard functionality with toast notifications
- **Form Handling**: Server-side validation with client-side convenience features
- **Mobile Responsive**: Bootstrap-based design optimized for sales team mobile usage

## Security Design Patterns
- **Encryption at Rest**: All customer data encrypted before database storage using Fernet symmetric encryption
- **CSRF Protection**: Custom CSRF token implementation using cookies and hidden form fields
- **Security Headers**: Basic security headers implementation to prevent common web vulnerabilities
- **Input Validation**: Server-side validation for all form inputs with specific format requirements (SSN, zip codes, state codes)

## Data Flow Architecture
- **Intake Process**: Form submission → validation → encryption → database storage → redirect to sales view
- **Sales Tools**: Individual field copying and bulk lender-formatted copying functionality
- **Lender Integration**: Stubbed endpoints for future integration with Momnt and GreenSky services

# External Dependencies

## Core Framework Dependencies
- **Flask**: Web application framework with SQLAlchemy extension for database operations
- **SQLAlchemy**: ORM for database interactions with SQLite backend
- **Cryptography**: Fernet implementation for AES-128 GCM encryption of customer data

## Frontend Dependencies
- **Bootstrap**: CSS framework loaded via CDN for responsive UI components
- **JavaScript**: Vanilla JavaScript for copy-to-clipboard functionality and toast notifications

## Database
- **SQLite**: File-based database for development and lightweight production deployments
- **Configurable Database URL**: Environment variable configuration allows for easy migration to PostgreSQL or other databases

## Environment Configuration
- **Required Environment Variables**:
  - `ENCRYPTION_KEY`: Fernet-compatible base64-encoded 32-byte encryption key
  - `SESSION_SECRET`: Flask session secret key for CSRF protection
  - `DATABASE_URL`: Database connection string (defaults to SQLite)

## Stubbed Integrations
- **Momnt API**: Placeholder endpoint for future lender integration
- **GreenSky API**: Placeholder endpoint for future lender integration
- **Generic JSON Payload**: Standardized format for lender data submission when integrations are implemented