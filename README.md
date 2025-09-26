# richie256/rtl-schedule

![ci workflow](https://github.com/richie256/rtl-schedule/workflows/Docker%20Images%20CI/badge.svg)

Return the time and info of the next bus for a giving bus-stop of the RTL.

## Prerequisite

- Stop Code number.
- Log in to a Docker registry.

## Supported Architectures

This image supports multiple architectures such as `x86-64`, `armhf` and `arm64`. Simply pulling `richie256/rtl-schedule` should retrieve the correct image for your architecture, but you can always pull specific architecture images via tags.

The architectures supported by this image are:

| Architecture | Tag (`latest`) |
| :----: | --- |
| x86-64 | `amd64-latest` |
| armhf | `arm32v7-latest` |
| arm64 | `arm64v8-latest` |

## Usage

### Create and start the container

```
docker run -d \
    --name=rtl-schedule \
    -p 80:80 \
    --restart unless-stopped \
    richie256/rtl-schedule
```

### Container configuration parameters

Refer to the following table for parameters available to the container images:

|       Parameter       | Required | Description |
|:---------------------:| --- | --- |
| `-e RTL_MODE=<mode>`  | | Supported mode: JSON for JSON MS, MQTT. |
| `-e EXTERNAL_PORT:80` | <div align="center">✔</div> | Publish the container's `80` internal port to the host as `EXTERNAL_PORT`. |


### How to call the application

`curl http://localhost:80/rtl_schedule/nextstop/123`

Command line parameters:

| Parameter | Description |
| :----: | --- |
| `<STOP_CODE>` | Your desired stop code.


# Build locally

Build
``` bash
docker build -t rtl-schedule:local .
```

``` bash
docker run -d \
    --name=rtl-schedule \
    -p <EXTERNAL_PORT>:80 \
    --restart unless-stopped \
    rtl-schedule:local
```

# MQTT DAEMON

Here is all the environment variables required if you use the MQTT output.

| Parameter | Required | Description |
| :----: | --- | --- |
| `-e RTL_STOP_CODE=stop_code` | <div align="center">✔</div> | RTL stop code. |
| `-e RTL_MODE=MQTT` | <div align="center">✔</div> | Specify the MQTT mode. |
| `-e MQTT_HOST=<mqtt host>` | <div align="center">✔</div> | Host of your MQTT broker. |
| `-e MQTT_PORT=<mqtt port>` | | Port of your MQTT broker. It will default to 1883 if not specified. |
| `-e MQTT_USERNAME=<mqtt username>` | | Your MQTT username. |
| `-e MQTT_PASSWORD=<mqtt password>` | | Your MQTT password. |

### How to call the mqtt deamon

```
docker run -d \
    --name=rtl-schedule \
    -e RTL_MODE=MQTT \
    -e RTL_STOP_CODE=99999 \
    -e MQTT_HOST=raspberrypi.local \
    -e MQTT_PORT=1883 \
    -e MQTT_USERNAME=username \
    -e MQTT_PASSWORD=password \
    --restart unless-stopped \
    richie256/rtl-schedule
```

## Notes

http://calculateur.rtl-longueuil.qc.ca/taz/rtl/horaire.php?l=44&t=32752&d=AA&date=20191104

http://calculateur.rtl-longueuil.qc.ca/taz/rtl/horaire.php?l=144&t=32752&d=AA&date=20191104

