FROM python:3.12-slim as builder

WORKDIR /usr/src/app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.12-slim

RUN addgroup --system app && adduser --system --ingroup app app

WORKDIR /usr/src/app

COPY --from=builder /usr/src/app /usr/src/app

COPY . .

RUN chown -R app:app /usr/src/app

USER app

ENV TZ=America/Montreal
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && dpkg-reconfigure -f noninteractive tzdata

CMD ["gunicorn", "--bind", "0.0.0.0:80", "--log-level", "info", "main:app"]
