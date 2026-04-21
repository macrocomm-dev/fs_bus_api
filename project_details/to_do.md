# To Do

## Platform and cloud wiring

- Validate a DB-backed application path end-to-end against Cloud Run.
- Enable/configure Firebase for the existing Google Cloud project and confirm auth tenancy setup.

## Secrets and configuration

- Validate secret loading behavior in local, CI, and Cloud Run environments.

## Auth and security

- Configure Firebase Authentication as the identity provider for the API and mobile app.
- Implement provider-token validation in the API instead of local placeholder token issuing.
- Define issuer, audience, token lifetime, refresh strategy, and revocation behavior for production.
- Define the token claim contract required by the mobile app, including name, id, and role.
- Model role-based access control for Monitor, Supervisor, and Admin, including inherited capabilities.
- Implement administrator-managed user provisioning with no public signup functionality.
- Define generic login failure responses and session expiry behavior aligned to the 4-hour requirement.

## Data and API surface

- Define canonical data model and database schema from business scope and questionnaire inputs.
- Add migrations workflow for database schema changes.
- Implement canonical API routes required by the mobile app integration scope.
- Add request/response validation and error contracts for mobile integration.
- Add separate passenger counting endpoint as indicated by the questionnaire.
- Add route(s) to support checklist parameter retrieval and administrative checklist management.
- Add route(s) for bus identification flow aligned with vehicle licence disc scanning.

## CI/CD and reliability

- Add automated tests for authentication, health, and core API routes.
- Add integration testing path against a test database.
- Run a post-deploy smoke test against a DB-backed route or migration path, not only health/auth placeholder routes.

## Documentation and governance

- Refine architecture and overview docs as implementation decisions become final.
- Maintain project_details/to_do.md and project_details/done.md continuously.
