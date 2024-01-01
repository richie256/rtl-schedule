FROM python:3.12

ARG TARGETPLATFORM
ENV TARGETPLATFORM=${TARGETPLATFORM}
RUN echo "I'm building for $TARGETPLATFORM"

COPY . /usr/src/app
WORKDIR /usr/src/app
ENV TZ=America/Montreal
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && dpkg-reconfigure -f noninteractive tzdata

RUN echo "pandas==2.1.4" >> requirements.txt

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "rtl-schedule.py"]

