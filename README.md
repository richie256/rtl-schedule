# richie256/rtl-schedule

![ci workflow](https://github.com/richie256/rtl-schedule/workflows/Docker%20Images%20CI/badge.svg)

Return the time and info of the next bus for a giving bus-stop of the RTL.

## Prerequisite

- Stop Code number.
- Log in to a Docker registry.

# TODO List

- [x] Finalize the coding.
- [ ] Fully test GitHub Automated actions.
- [ ] Add 24h expiration for the zip file.
- [ ] Indicate how to find a stop code.
- [ ] Create a Docker container registry.
- [ ] Sometimes, the rage of date in the file `calendar.txt` in the current zip file is in the future.

## Supported Architectures

This image supports multiple architectures such as `x86-64` and `armhf`. Simply pulling `richie256/rtl-schedule` should retrieve the correct image for your architecture, but you can always pull specific architecture images via tags.

The architectures supported by this image are:

| Architecture | Tag (`latest`) |
| :----: | --- |
| x86-64 | `amd64-latest` |
| armhf | `arm32v7-latest` |

## Usage

### Create and start the container

docker run -d \
    --name=rtl-schedule \
    -p <EXTERNAL_PORT>:80 \
    --restart unless-stopped \
    richie256/rtl-schedule

### Container configuration parameters

Refer to the following table for parameters available to the container images:

| Parameter | Required | Description |
| :----: | --- | --- |
| `-p <EXTERNAL_PORT>:80` | <div align="center">✔</div> | Publish the container's `80` internal port to the host as `<EXTERNAL_PORT>`.<br>This is necessary for the Authentication process (more on that below). |

### How to call the application

`curl http://localhost:<EXTERNAL_PORT>/rtl_schedule/nextstop/<STOP_CODE>`

Command line parameters:

| Parameter | Description |
| :----: | --- |
| `<STOP_CODE>` | Your desired stop code.


## Notes

http://calculateur.rtl-longueuil.qc.ca/taz/rtl/horaire.php?l=44&t=32752&d=AA&date=20191104
http://calculateur.rtl-longueuil.qc.ca/taz/rtl/horaire.php?l=144&t=32752&d=AA&date=20191104

