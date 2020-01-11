FROM python:3
#FROM python:3-onbuild

ARG TARGETPLATFORM
ENV TARGETPLATFORM=${TARGETPLATFORM}
RUN echo "I'm building for $TARGETPLATFORM"

COPY . /usr/src/app
WORKDIR /usr/src/app
ENV TZ=America/Montreal
# RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && dpkg-reconfigure -f noninteractive tzdata

RUN echo "pandas==0.25.3" >> requirements.txt

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "rtl-schedule.py"]

