
FROM python:3.12-slim

RUN apt-get update && apt-get install -y curl procps

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /data

ENV TZ=America/Montreal
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && dpkg-reconfigure -f noninteractive tzdata

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD if [ "$MODE" = "mqtt" ]; then pgrep python; else curl -f http://localhost:80/health || exit 1; fi

CMD ["python", "app.py"]
