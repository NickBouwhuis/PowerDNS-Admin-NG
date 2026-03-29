# PowerDNS-Admin NG

A modern PowerDNS web interface with advanced features. Community-maintained fork of [PowerDNS-Admin](https://github.com/PowerDNS-Admin/PowerDNS-Admin) with a completely rewritten backend (FastAPI + SQLAlchemy 2.x) and a new Next.js frontend.

[![CI](https://github.com/NickBouwhuis/PowerDNS-Admin-NG/actions/workflows/ci.yml/badge.svg)](https://github.com/NickBouwhuis/PowerDNS-Admin-NG/actions/workflows/ci.yml)
[![Docker Image](https://ghcr.io/nickbouwhuis/powerdns-admin-ng)](https://github.com/NickBouwhuis/PowerDNS-Admin-NG/pkgs/container/powerdns-admin-ng)

## What's New

PowerDNS-Admin NG is a ground-up modernization of the original PowerDNS-Admin:

- **FastAPI backend** replacing Flask -- async-ready, OpenAPI docs, Pydantic validation
- **SQLAlchemy 2.x** with proper session management
- **Next.js frontend** with App Router, shadcn/ui, TanStack Query/Table
- **API v1** (backwards-compatible, API key + Basic auth) and **API v2** (session-based for the SPA)
- **Multi-arch Docker images** (amd64 + arm64) published to GHCR
- **Service layer** with clean separation of concerns
- **Security hardened** -- bcrypt, CSRF protection, rate limiting

## Features

- Forward and reverse zone management
- Zone templating
- Role-based access control (Administrator, Operator, User)
- Zone-specific access control
- Activity logging
- Authentication:
  - Local users
  - SAML
  - LDAP (OpenLDAP / Active Directory)
  - OAuth (Google / GitHub / Azure / OpenID Connect)
- PDNS server configuration and statistics monitoring
- DynDNS 2 protocol support
- Easy IPv6 PTR record editing
- Full IDN/Punycode support
- REST API for zone and record management

## Quick Start

### Docker (recommended)

```bash
docker run -d \
  -e SECRET_KEY='change-me-to-a-random-string' \
  -e SQLALCHEMY_DATABASE_URI='sqlite:////data/powerdns-admin.db' \
  -v pda-data:/data \
  -p 3000:3000 \
  ghcr.io/nickbouwhuis/powerdns-admin-ng:latest
```

### Docker Compose

```yaml
services:
  app:
    image: ghcr.io/nickbouwhuis/powerdns-admin-ng:latest
    restart: always
    ports:
      - "3000:3000"
    environment:
      - SECRET_KEY=change-me-to-a-random-string
      - SQLALCHEMY_DATABASE_URI=mysql://pda:changeme@db/pda
      - GUNICORN_WORKERS=2
```

Then visit http://localhost:3000.

### With Traefik

```yaml
services:
  app:
    image: ghcr.io/nickbouwhuis/powerdns-admin-ng:latest
    restart: always
    environment:
      - SECRET_KEY=change-me-to-a-random-string
      - SQLALCHEMY_DATABASE_URI=mysql://pda:changeme@db/pda
    networks:
      - web
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.pdnsa.rule=Host(`dns-admin.example.com`)"
      - "traefik.http.routers.pdnsa.tls.certresolver=letsencrypt"
      - "traefik.http.services.pdnsa.loadbalancer.server.port=3000"
```

## Configuration

Configuration is loaded from environment variables. Key settings:

| Variable | Description | Default |
|---|---|---|
| `SECRET_KEY` | Session encryption key (required) | -- |
| `SALT` | API key hashing salt | auto-generated |
| `SQLALCHEMY_DATABASE_URI` | Database connection string | `sqlite:///pdns.db` |
| `GUNICORN_WORKERS` | Number of backend workers | `4` |
| `GUNICORN_TIMEOUT` | Worker timeout in seconds | `120` |

All settings from [AppSettings.defaults](powerdnsadmin/lib/settings.py) can be set via environment variables. Append `_FILE` to any variable to read the value from a file (Docker secrets convention).

## Architecture

```
Browser --> Next.js (port 3000) --> FastAPI (port 9191) --> PowerDNS API
                |                        |
                |                        +---> MySQL/PostgreSQL/SQLite
                +-- Static assets, SSR
```

Inside the Docker container:
- **Next.js** serves the SPA on port 3000 (user-facing)
- **Gunicorn + Uvicorn** runs the FastAPI backend on port 9191 (internal)
- **Alembic** handles database migrations on startup

## Development

```bash
# Backend
pip install -r requirements.txt
uvicorn powerdnsadmin.app:create_app --factory --reload --port 9191

# Frontend
cd frontend
npm install
npm run dev
```

The Next.js dev server proxies API requests to the FastAPI backend at localhost:9191.

## API

- **API v1** (`/api/v1/`) -- PowerDNS-Admin compatible, Basic auth + API key
- **API v2** (`/api/v2/`) -- Session-based, used by the SPA frontend
- **OpenAPI docs** at `/api/docs` (Swagger UI) and `/api/redoc`

## License

MIT License. See [LICENSE](LICENSE).
