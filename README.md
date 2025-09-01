# Clean Architecture SaaS Templates

Maintained as an Open Source project by Avatarctic™ — https://avatarctic.com

This repository contains production-oriented Clean Architecture SaaS templates implemented in multiple languages. Each language lives in its own subfolder and includes a usable service skeleton, Docker + Docker Compose configuration, migrations, and CI automation so you can run and extend a realistic, full-stack example.

Current language templates

- `go/` — A complete Go example using Clean Architecture principles: Echo HTTP server, PostgreSQL, Redis, migrations, integration tests, and GitHub Actions CI. See `go/README.md` for full setup and development instructions.
- `python/` — Placeholder for a Python implementation following the same layout and CI conventions.

Why these templates

- Practical scaffolding: wiring common SaaS concerns (auth, multi-tenancy, feature flags, email, metrics). 
- Reproducible local dev: Docker Compose setups for DB and Redis so integration tests and local runs match CI.
- CI-ready: example GitHub Actions workflows that show how to run unit and integration tests safely for a multi-service project.

Quick start

1. Pick a language folder (for example `go/`) and follow its README:

```powershell
cd go
# follow instructions in go/README.md
```

2. For local development, copy the example env and start the stack with Docker Compose:

```powershell
cp .env.example .env
docker compose -f docker-compose.yml up -d
```

CI and repository layout notes

- Each language has its own CI workflow under `.github/workflows`. To avoid running all pipelines on every push, workflows should use path filters (for example `paths: ['go/**']` for the Go workflow). This keeps CI fast and scoped to the modified project.
- The repository intentionally separates development compose files (which may mount the source) from CI compose files (which run the baked image without host mounts) to avoid masking artifacts baked into images.

Contributing & Maintainer

This project is Open Source and maintained by Avatarctic™ — https://avatarctic.com. 

Contributions are welcome. Please follow conventional commits, include tests for new behavior, and open a PR describing the change. If you add another language template (for example `python/`), add a short README under that folder and update this root README list.

License

This project is licensed under the MIT License. See `LICENSE.txt` for details.

—

Built with practical Clean Architecture patterns and real infrastructure examples.
