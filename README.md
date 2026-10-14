# Intelligent Cattle Management System

Final Year Project at COMSATS University Islamabad, Attock Campus.

## Project goal

A mobile and web application for managing private cattle farms,
with role-based access and AI-assisted decision support.

## Planned technologies

- Frontend: React Native, Expo, JavaScript
- Backend: Python, FastAPI
- Database: PostgreSQL
- Database tools: SQLAlchemy, Alembic
- AI: scikit-learn, TensorFlow/Keras

## User roles

- System Admin
- Farm Owner
- Farm Manager
- Worker
- Veterinarian

## Repository structure

- backend: API and database implementation
- frontend: Mobile and web application
- ai: Model training and evaluation
- docs: Project documentation

## Current status

The backend includes authentication, email verification, farm management,
owner-authorized staff invitations, secure invitation acceptance and membership
activation, PostgreSQL migrations, and isolated security tests. See
[docs/security-foundation.md](docs/security-foundation.md) for migration
prechecks, local email testing, and rate-limit deployment notes.
