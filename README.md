# :bus: transit-schedule

[![Docker CI](https://github.com/richie256/transit-schedule/actions/workflows/dockerimage.yml/badge.svg?branch=master)](https://github.com/richie256/transit-schedule/actions/workflows/dockerimage.yml)
[![Unit Tests](https://github.com/richie256/transit-schedule/actions/workflows/tests.yml/badge.svg?branch=master)](https://github.com/richie256/transit-schedule/actions/workflows/tests.yml)
[![codecov](https://codecov.io/gh/richie256/transit-schedule/graph/badge.svg)](https://codecov.io/gh/richie256/transit-schedule)

[![GitHub Release](https://img.shields.io/github/v/release/richie256/transit-schedule)](https://github.com/richie256/transit-schedule/releases)

A multi-transit bus schedule information provider for Greater Montreal. :rocket:

This project provides an application to get bus schedule information for:
- **RTL:** Réseau de transport de Longueuil :oncoming_bus:
- **STM:** Société de transport de Montréal :metro:
- **STL:** Société de transport de Laval :bus:

The application can run in two different modes:

1.  **HTTP Mode:** A web service to get the next bus for a given stop. :globe_with_meridians:
2.  **MQTT Mode:** An MQTT publisher that periodically fetches the next bus time and publishes it to an MQTT broker. :satellite:

## :hammer_and_wrench: Usage

### 1. Build the Docker Image :whale:

To build the Docker image locally, run the following command in the root of the project:

```bash
docker build -t transit-schedule .
```

### 2. Run the Container :rocket:

#### HTTP Mode :globe_with_meridians:

To run the container in HTTP mode, which provides a web service to get the next bus schedule:

```bash
docker run -p 8080:80 -v ./data:/data -e MODE=http -e TRANSIT=STM transit-schedule
```

-   **Endpoint:** `GET /transit-schedule/nextstop/<STOP_CODE>`

**Example using curl:**

```bash
curl http://localhost:8080/transit-schedule/nextstop/52611
```

#### MQTT Mode :satellite:

Create a `.env` file with the following content:

```
TRANSIT=STM
STOP_CODE=52611
MQTT_HOST=your_mqtt_broker_host
...
```

Then run the container:

```bash
docker run --env-file .env -v ./data:/data -e MODE=mqtt transit-schedule
```

### :gear: Configuration Options

| Environment Variable | Description | Default |
| --- | --- | --- |
| `TRANSIT` | Transit agency (`RTL`, `STM`, `STL`) | `RTL` |
| `MODE` | Application mode (`http` or `mqtt`) | `http` |
| `STOP_CODE` | Public stop code (Required for MQTT mode) | None |
| `TARGET_ROUTE` | Filter by specific route ID (e.g., `44`) | None |
| `TARGET_DIRECTION` | Filter by trip headsign (e.g., `Direction Terminus Panama`) | `Direction Terminus Panama` (RTL only) |
| `FORCE_CACHE_REFRESH` | Manually invalidate and refresh the live scraper cache | `False` |
| `RETRIEVAL_METHOD` | Data source strategy (`live` or `gtfs`) | `live` for RTL, `gtfs` others |

### :mag: Filtering Logic

The application supports two layers of filtering to ensure you get exactly the bus you're looking for:

1.  **`TARGET_ROUTE`**: Used to isolate a specific route number. This is highly recommended if your stop is served by multiple routes with similar numbers (e.g., route `44` vs route `144`). When set, only exact matches for the route ID are returned.
2.  **`TARGET_DIRECTION`**: Used to filter by the destination or direction (headsign). For **RTL**, this defaults to `Direction Terminus Panama`. 

If both are set, the bus must match **both** the route ID and the direction string to be included in the schedule.

## :bar_chart: Data Sources

- **RTL GTFS:** http://www.rtl-longueuil.qc.ca/transit/latestfeed/RTL.zip
- **STM GTFS:** https://www.stm.info/sites/default/files/gtfs/gtfs_stm.zip
- **STL GTFS:** https://www.stlaval.ca/datas/opendata/GTF_STL.zip
- **RTL Live Scraper:** Fallback for RTL when GTFS is unavailable.

## :test_tube: Unit Tests

```bash
python3 -m pytest tests/
```
