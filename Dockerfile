FROM python:3.12-slim

RUN apt-get update && apt-get install -y curl procps && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install project dependencies
COPY pyproject.toml .
# We need to copy README.md as well if it's referenced in pyproject.toml
COPY README.md .
# Create a dummy src/transit_schedule/__init__.py to allow pip to install dependencies
RUN mkdir -p src/transit_schedule && touch src/transit_schedule/__init__.py
RUN pip install --no-cache-dir .

# Copy the rest of the source code
COPY . .
# Re-install the project to include all source files
RUN pip install --no-cache-dir .

RUN mkdir -p /data

ENV TZ=America/Montreal
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && dpkg-reconfigure -f noninteractive tzdata

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD if [ "$MODE" = "mqtt" ]; then [ $(find /tmp/mqtt_heartbeat -mmin -2) ]; else curl -f http://localhost:80/health || exit 1; fi

# Use the entry point defined in pyproject.toml
CMD ["transit-schedule"]
