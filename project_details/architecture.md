# Current Architecture and Status

## Current baseline

- FastAPI service scaffold exists with entry point in app/main.py.
- Basic middleware and health endpoint exist.
- OAuth2 bearer token scaffolding exists, with JWT encode/decode helpers.
- The token issue endpoint exists but currently returns not implemented for real authentication.
- SQLAlchemy database engine and session setup exist for PostgreSQL.
- Configuration supports loading secrets from environment variables and Google Cloud Secret Manager.
- Dockerfile and docker-compose are present for local API plus Cloud SQL Proxy style development.
- GitHub Actions workflow exists for test, build, and deploy on main branch pushes.
- Cloud SQL, Secret Manager, Artifact Registry, Cloud Run, and GitHub OIDC/WIF wiring are now provisioned in bus-track-480813.

## Important caveat

- This is a generated baseline architecture and should be treated as starter scaffolding.
- Production auth, user lifecycle, and business routes are not fully finalized.
- Existing routes and implementation details are not yet canonical and must be validated against project scope.

## Source inputs to align against

- project_details/scope/FreeStateBusApp_BusinessSpec_v2 - Sean Markup.docx
- project_details/scope/Phase 1 questions_v2.docx

## Architecture direction

- Keep FastAPI as API runtime.
- Use Cloud SQL for PostgreSQL as the system database.
- Use Secret Manager for secrets and sensitive runtime values.
- Use Firebase Authentication as the preferred identity provider, enabled against the project's Google Cloud environment.
- Implement OAuth2/OIDC-compliant auth flow using provider-issued tokens rather than API-issued local login tokens.
- Validate bearer tokens in the API using Firebase/Google signing keys and expected issuer/audience checks.
- Include user identity and role claims in tokens consumed by the API.
- Enforce administrator-managed user lifecycle with no public signup flow.
- Model role-based access around Monitor, Supervisor, and Admin capability inheritance.
- Use CI/CD on main branch as the deployment trigger.

## Auth requirements from questionnaire and scope

- Authentication method: OAuth2 with OIDC-style token content.
- Successful login payload expected by client: token containing at least name, id, and role.
- Tokens are expected to last about 4 hours before re-login is required.
- Failed login responses should be generic, not detailed per failure reason.
- Users already exist; the mobile app must not expose user registration.
- Role names currently expected by the mobile app: Monitor, Supervisor, Admin.

## Business flow points affecting API design

- The system supports around 20 named users under RBAC.
- Checklist data is parameterised and administratively managed.
- Passenger counting should be supported by a separate API endpoint from inspection submission.
- Vehicle identification is expected via scanning the vehicle licence disc.
- All mobile traffic must go through the API layer; direct database access from the mobile client is prohibited.
