FROM python:3
#FROM python:3-onbuild

RUN set -o pipefail && wget -O python.tar.xz "https://www.python.org/ftp/python/${PYTHON_VERSION%%[a-z]*}/Python-$PYTHON_VERSION.tar.xz"

COPY . /usr/src/app
WORKDIR /usr/src/app
ENV TZ=America/Montreal
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone
CMD ["python", "test.py"]


