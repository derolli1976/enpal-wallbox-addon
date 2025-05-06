ARG BUILD_FROM
FROM $BUILD_FROM

ENV LANG C.UTF-8

ENV BASE_URL="http://192.168.178.178"

RUN apk add --no-cache \
    python3 py3-pip \
    chromium \
    chromium-chromedriver \
    xvfb \
    ttf-freefont \
    bash

COPY requirements.txt /tmp/
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt

COPY run.py /app/run.py
WORKDIR /app

CMD ["python3", "run.py"]
