FROM python:3-onbuild

COPY . /usr/src/app
WORKDIR /usr/src/app
ENV TZ=America/Montreal
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

CMD ["python", "rtl-schedule.py"]
