# Free State Bus API Overview

This is an app for the API of the Free State Bus Project.

This service will run as a FastAPI application, with its database hosted in Google Cloud project ID: bus-track-480813.

The app will use Google Cloud Secret Manager for applicable secrets.

The PostgreSQL Cloud SQL instance is hosted in the same Google Cloud project and the API is expected to use it as the system database.

The API needs to use OAuth2/OIDC and we need to provide the identity provider. Firebase Authentication is the current preferred direction for that identity provider.

Users are created and managed by the project administrators. There is no public signup or self-registration flow in the mobile app.

The token must carry user identity and role information. Current scope inputs indicate an OIDC token containing at least name, id, and role.

The current role model from the questionnaire is:

- Monitor
- Supervisor
- Admin

Admin must have Supervisor and Monitor capabilities, and Supervisor must have Monitor capabilities.

Current questionnaire guidance indicates login persistence of roughly 4 hours before re-authentication is required.

The AI assistant should have direct read and write access to the database.

The workflow needs CI/CD deployment on the main branch.

Scope details from the mobile app team, including their questionnaire, are included in project_details/scope.

The current architecture was initially set up by a GitHub repository setup assistant. Google Cloud infrastructure is now largely provisioned, but required business routes, real authentication, and some final implementation details are not yet canonical.
