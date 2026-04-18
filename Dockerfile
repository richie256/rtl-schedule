FROM python:3.12-slim

RUN apt-get update && apt-get install -y curl procps && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy packaging files
COPY pyproject.toml README.md ./

# Copy source code first to allow pip install . to work
COPY src/ ./src/

# Install the project and its dependencies
RUN pip install --no-cache-dir .

RUN mkdir -p /data

ENV TZ=America/Montreal
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && dpkg-reconfigure -f noninteractive tzdata

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD if [ "$MODE" = "mqtt" ]; then [ $(find /tmp/mqtt_heartbeat -mmin -2) ]; else curl -f http://localhost:80/health || exit 1; fi

# Use the entry point defined in pyproject.toml
CMD ["transit-schedule"]
