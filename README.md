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
activation, staff administration, farm-scoped custom roles, centralized
permission evaluation, cattle registration and profile management, structured
breed data, lifecycle and weight history, secure cattle media handling,
PostgreSQL migrations, and isolated security tests. See
[docs/security-foundation.md](docs/security-foundation.md) for migration
prechecks, local email testing, and rate-limit deployment notes. The audited
implementation status and roadmap are in
[docs/ICMS_FULL_PROJECT_STATUS_REPORT.md](docs/ICMS_FULL_PROJECT_STATUS_REPORT.md).
The Step 16 cattle-module handover is in
[docs/STEP_16_CATTLE_MODULE_REPORT.md](docs/STEP_16_CATTLE_MODULE_REPORT.md).
The post-Step-16 router refactoring and PostgreSQL CI validation are documented
in [docs/STEP_16_5_MAINTENANCE_REPORT.md](docs/STEP_16_5_MAINTENANCE_REPORT.md).
