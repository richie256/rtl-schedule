# richie256/rtl-schedule

[![Docker Image CI](https://github.com/richie256/rtl-schedule/actions/workflows/dockerimage.yml/badge.svg)](https://github.com/richie256/rtl-schedule/actions/workflows/dockerimage.yml)

This project provides two services to get bus schedule information from the Réseau de transport de Longueuil (RTL):

1.  A web service to get the next bus for a given stop.
2.  An MQTT publisher that periodically fetches the next bus time and publishes it to an MQTT broker.

## Prerequisite

- A bus stop code number.
- Docker and Docker Compose.

## Supported Architectures

This image supports multiple architectures such as `x86-64` and `arm64`. The Docker build process should retrieve the correct image for your architecture.

## Usage with Docker Compose

This project uses Docker Compose to run the services. A `docker-compose.yml` file is provided to define and configure the services.

### 1. Environment Variables

Before starting the services, you need to create a `.env` file in the root of the project. This file will contain the necessary environment variables for the `mqtt-publisher` service.

Create a file named `.env` with the following content:

```
STOP_CODE=your_stop_code
MQTT_HOST=your_mqtt_broker_host
MQTT_PORT=1883
MQTT_USERNAME=your_mqtt_username
MQTT_PASSWORD=your_mqtt_password
```

Replace the placeholder values with your actual bus stop code and MQTT broker details.

### 2. Start the Services

To build and start both the web service and the MQTT publisher, run the following command:

```bash
docker-compose up --build -d
```

This will start the services in detached mode.

### 3. Stop the Services

To stop the services, run:

```bash
docker-compose down
```

## Services

### Web Service (`web`)

The web service provides an HTTP endpoint to get the next bus schedule for a specific stop.

-   **Port:** The service is available on port `8080` of the host machine.
-   **Endpoint:** `GET /rtl_schedule/nextstop/<STOP_CODE>`

**Example using curl:**

```bash
curl http://localhost:8080/rtl_schedule/nextstop/12345
```

### MQTT Publisher (`mqtt-publisher`)

The MQTT publisher periodically fetches the next bus time and publishes it to an MQTT topic.

-   **Topic:** `schedule/bus_stop/<STOP_CODE>`
-   **Interval:**
    -   Every 10 seconds during rush hours (weekdays 6:00-9:00 and 15:00-18:00).
    -   Every 60 seconds at all other times.
-   **Payload:** The message payload is a JSON object containing schedule information.

## Unit Tests

To run the unit tests, execute the following command:

```bash
pytest
```

## Local Development

If you want to run the services without Docker, you can install the dependencies from `requirements.txt` and run the applications directly.

**Install dependencies:**

```bash
pip install -r requirements.txt
```

**Run the web service:**

```bash
gunicorn --bind 0.0.0.0:8080 main:app
```

**Run the MQTT publisher:**

```bash
export STOP_CODE=your_stop_code
export MQTT_HOST=your_mqtt_broker_host
python mqtt_publisher.py
```