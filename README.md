# transit-schedule

A multi-transit bus schedule information provider for Greater Montreal.

This project provides an application to get bus schedule information for:
- **RTL:** Réseau de transport de Longueuil
- **STM:** Société de transport de Montréal
- **STL:** Société de transport de Laval

The application can run in two different modes:

1.  **HTTP Mode:** A web service to get the next bus for a given stop.
2.  **MQTT Mode:** An MQTT publisher that periodically fetches the next bus time and publishes it to an MQTT broker.

## Usage

### 1. Build the Docker Image

To build the Docker image locally, run the following command in the root of the project:

```bash
docker build -t transit-schedule .
```

### 2. Run the Container

#### HTTP Mode

To run the container in HTTP mode, which provides a web service to get the next bus schedule:

```bash
docker run -p 8080:80 -v ./data:/data -e MODE=http -e TRANSIT=STM transit-schedule
```

-   **Endpoint:** `GET /transit-schedule/nextstop/<STOP_CODE>`

**Example using curl:**

```bash
curl http://localhost:8080/transit-schedule/nextstop/52611
```

#### MQTT Mode

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

### Configuration Options

| Environment Variable | Description | Default |
| --- | --- | --- |
| `TRANSIT` | Transit agency (`RTL`, `STM`, `STL`) | `RTL` |
| `MODE` | Application mode (`http` or `mqtt`) | `http` |
| `STOP_CODE` | Public stop code (Required for MQTT mode) | None |
| `RETRIEVAL_METHOD` | Data source strategy (`live` or `gtfs`) | `live` for RTL, `gtfs` others |
| ... | ... | ... |

## Data Sources

- **RTL GTFS:** http://www.rtl-longueuil.qc.ca/transit/latestfeed/RTL.zip
- **STM GTFS:** https://www.stm.info/sites/default/files/gtfs/gtfs_stm.zip
- **STL GTFS:** https://www.stlaval.ca/datas/opendata/GTF_STL.zip
- **RTL Live Scraper:** Fallback for RTL when GTFS is unavailable.

## Unit Tests

```bash
python3 -m pytest tests/
```
