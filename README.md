# fixit-backend
FastAPI backend

## CI/CD secrets

Set these under Settings → Secrets and variables → Actions. Until real values exist, they hold placeholders.

| Secret | Used for |
| --- | --- |
| `REGISTRY_URL` | Container registry host and namespace, e.g. `ghcr.io/fixit-garage` |
| `REGISTRY_USERNAME` | Registry login user (not needed for GHCR, which uses `GITHUB_TOKEN`) |
| `REGISTRY_PASSWORD` | Registry password or access token (not needed for GHCR) |
