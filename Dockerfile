FROM python:3.12

ARG TARGETPLATFORM
ENV TARGETPLATFORM=${TARGETPLATFORM}

WORKDIR /usr/src/app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV TZ=America/Montreal
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && dpkg-reconfigure -f noninteractive tzdata

CMD ["gunicorn", "--bind", "0.0.0.0:80", "main:app"]
