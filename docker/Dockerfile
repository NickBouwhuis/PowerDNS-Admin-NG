# ============================================================================
# Stage 1: Build Next.js frontend
# ============================================================================
FROM node:20-alpine AS frontend-builder

WORKDIR /frontend

# Install dependencies first (cached layer)
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci

# Copy source and build
COPY frontend/ .
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# ============================================================================
# Stage 2: Build Python backend dependencies
# ============================================================================
FROM alpine:3.17 AS backend-builder

ARG BUILD_DEPENDENCIES="build-base \
    libffi-dev \
    libpq-dev \
    libxml2-dev \
    mariadb-connector-c-dev \
    openldap-dev \
    python3-dev \
    xmlsec-dev \
    cargo"

ENV LC_ALL=en_US.UTF-8 \
    LANG=en_US.UTF-8 \
    LANGUAGE=en_US.UTF-8

RUN apk add --no-cache ${BUILD_DEPENDENCIES} && \
    apk add --no-cache py3-pip

WORKDIR /build

COPY ./requirements.txt /build/requirements.txt
RUN pip install --upgrade pip && \
    pip install --use-pep517 -r requirements.txt

COPY . /build

# Move application files (no frontend build needed here)
RUN mkdir -p /app && \
    cp -r /build/migrations/ /build/powerdnsadmin/ /app && \
    mkdir -p /app/configs && \
    cp -r /build/configs/docker_config.py /app/configs && \
    cp /build/run.py /app/

# ============================================================================
# Stage 3: Production image
# ============================================================================
FROM alpine:3.17

LABEL org.opencontainers.image.source="https://github.com/NickBouwhuis/PowerDNS-Admin-NG"
LABEL org.opencontainers.image.description="PowerDNS-Admin NG - Modern DNS management interface"
LABEL org.opencontainers.image.licenses="MIT"

ENV USER=pda \
    NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PYTHONPATH=/app

# Install runtime dependencies (Python + Node.js)
RUN apk add --no-cache \
    mariadb-connector-c \
    postgresql-client \
    py3-gunicorn \
    py3-pyldap \
    py3-psycopg2 \
    xmlsec \
    tzdata \
    libcap \
    nodejs && \
    addgroup -S ${USER} && \
    adduser -S -D -G ${USER} ${USER} && \
    mkdir /data && \
    chown ${USER}:${USER} /data && \
    setcap cap_net_bind_service=+ep $(readlink -f /usr/bin/python3) && \
    apk del libcap

# Copy Python packages and scripts (alembic, gunicorn, uvicorn, etc.)
COPY --from=backend-builder /usr/lib/python3.10/site-packages /usr/lib/python3.10/site-packages/
COPY --from=backend-builder /usr/bin/alembic /usr/bin/gunicorn /usr/bin/uvicorn /usr/bin/

# Copy backend application
COPY --from=backend-builder --chown=root:${USER} /app /app/

# Copy Next.js standalone build
# standalone output nests under /frontend/ since the app is in a subdirectory
COPY --from=frontend-builder --chown=root:${USER} /frontend/.next/standalone/frontend /app/frontend/
COPY --from=frontend-builder --chown=root:${USER} /frontend/.next/static /app/frontend/.next/static
COPY --from=frontend-builder --chown=root:${USER} /frontend/public /app/frontend/public

# Copy entrypoint
COPY ./docker/entrypoint.sh /usr/bin/

WORKDIR /app
RUN chown ${USER}:${USER} ./configs /app && \
    cat ./powerdnsadmin/default_config.py ./configs/docker_config.py > ./powerdnsadmin/docker_config.py

EXPOSE 3000/tcp
USER ${USER}
HEALTHCHECK --interval=5s --timeout=5s --start-period=20s --retries=5 CMD wget --output-document=- --quiet --tries=1 http://127.0.0.1:9191/ping
ENTRYPOINT ["entrypoint.sh"]
CMD ["start"]
