FROM python:3.12-slim

RUN addgroup --system app && adduser --system --ingroup app app

WORKDIR /usr/src/app

COPY . .

RUN apt-get update && apt-get install -y curl
RUN pip install --no-cache-dir -r requirements.txt

RUN chown -R app:app /usr/src/app
RUN chown -R app:app /data

ENV TZ=America/Montreal
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && dpkg-reconfigure -f noninteractive tzdata

USER app

CMD ["gunicorn", "--bind", "0.0.0.0:80", "--log-level", "info", "main:app"]