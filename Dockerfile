FROM python:3.12-slim

WORKDIR /usr/src/app

COPY . .

RUN apt-get update && apt-get install -y curl
RUN pip install --no-cache-dir -r requirements.txt

ENV TZ=America/Montreal
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && dpkg-reconfigure -f noninteractive tzdata

CMD ["gunicorn", "--bind", "0.0.0.0:80", "--log-level", "info", "main:app"]