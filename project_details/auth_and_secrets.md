# Auth and Secrets SOP

## Purpose

This document defines the standard operating procedure for authentication, secret management, and CI/CD trust for the Free State Bus API project.

## Principles

- Runtime application secrets live in Google Cloud Secret Manager.
- CI/CD authenticates to Google Cloud using GitHub OIDC and Workload Identity Federation.
- Non-sensitive deployment configuration is stored as GitHub repository variables.
- Long-lived Google Cloud service account key files must not be stored in GitHub.

## Runtime secret source of truth

The following runtime secrets are managed in Google Cloud Secret Manager in project `bus-track-480813`:

- `api-secret-key`
- `db-password`
- `db-name`
- `db-user`

These secrets are referenced by Cloud Run during deployment and are also available to local development through Application Default Credentials when appropriate.

## Identity provider direction

Firebase Authentication is the current preferred identity provider for this project.

Operationally, the simplest setup is to enable Firebase against the existing Google Cloud project `bus-track-480813`, rather than creating a disconnected second project just for auth.

Users are not self-registering through the app. User accounts are expected to be created and managed administratively.

The API is expected to consume provider-issued tokens that include user identity and role information.

## GitHub CI/CD configuration model

GitHub Actions should use repository variables for non-sensitive configuration:

- `GCP_PROJECT_ID`
- `GCP_REGION`
- `ARTIFACT_REGISTRY_REPO`
- `CLOUD_RUN_SERVICE`
- `CLOUD_SQL_INSTANCE`
- `WIF_PROVIDER`
- `WIF_SERVICE_ACCOUNT`

These are configuration values, not application secrets.

## CI/CD authentication SOP

GitHub Actions authenticates to Google Cloud through Workload Identity Federation.

Required components:

- Workload Identity Pool: `github-actions-pool`
- Workload Identity Provider: `github-provider`
- CI service account: `fs-bus-cicd@bus-track-480813.iam.gserviceaccount.com`

GitHub must never rely on a stored GCP service account key JSON for this deployment path.

## Cloud Run runtime auth and secret wiring

Cloud Run service `bus-track-api` should:

- run as `fs-bus-api-runtime@bus-track-480813.iam.gserviceaccount.com`
- mount Cloud SQL connection `bus-track-480813:africa-south1:fs-bus-db`
- receive runtime secrets from Secret Manager
- set `GOOGLE_CLOUD_PROJECT=bus-track-480813`
- set `DB_HOST=/cloudsql/bus-track-480813:africa-south1:fs-bus-db`

## Local development SOP

- Use `gcloud auth application-default login` for ADC.
- Prefer `.env` only for local overrides, not as the system of record for secrets.
- Do not commit populated `.env` files.

## Rotation SOP

- Rotate database passwords in Cloud SQL and immediately update `db-password` in Secret Manager.
- Rotate JWT signing material by adding a new Secret Manager version and coordinating rollout.
- Avoid duplicating runtime secrets into GitHub.

## Exception handling

If a CI workflow truly needs a secret value during execution, fetch it from Google Cloud after WIF authentication instead of copying that secret into GitHub.

## Current project state

- Workload Identity Federation is configured.
- GitHub deployment variables are the intended CI/CD config source.
- Redundant GitHub deployment secrets were removed after variables were configured.
- Secret Manager is the intended runtime secret source.
- Application auth is still placeholder-level and must be replaced with Firebase-backed OAuth2/OIDC token validation.