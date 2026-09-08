# To Do

## Platform and cloud wiring

- Validate a DB-backed application path end-to-end against Cloud Run.
- Enable/configure Firebase for the existing Google Cloud project and confirm auth tenancy setup.

## Secrets and configuration

- Validate secret loading behavior in local, CI, and Cloud Run environments.

## Auth and security

- Define issuer, audience, token lifetime, refresh strategy, and revocation behavior for production.
- Replace temporary Firebase role test users with formal administrator-managed user provisioning and lifecycle controls.
- Define generic login failure responses and session expiry behavior aligned to the 4-hour requirement.
- Apply role enforcement dependencies to business routes as they are implemented.
- Remove remaining legacy local-JWT fallback settings and helper paths once Firebase-only auth is fully adopted.

## Data and API surface

- Define canonical data model and database schema from business scope and questionnaire inputs.
- Add migrations workflow for database schema changes.
- Implement canonical API routes required by the mobile app integration scope.
- Add request/response validation and error contracts for mobile integration.
- Add separate passenger counting endpoint as indicated by the questionnaire.
- Add route(s) to support checklist parameter retrieval and administrative checklist management.
- Add route(s) for bus identification flow aligned with vehicle licence disc scanning.

## CI/CD and reliability

- Deploy the route-departure CSV endpoint through the backend `main` workflow and smoke-test it with a mobile user's Firebase token.
- Expand automated tests beyond auth to health and core API routes.
- Add integration testing path against a test database.
- Run a post-deploy smoke test against a DB-backed route or migration path, not only health/auth placeholder routes.

## Documentation and governance

- Refine architecture and overview docs as implementation decisions become final.
- Maintain project_details/to_do.md and project_details/done.md continuously.
