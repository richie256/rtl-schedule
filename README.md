# richie256/rtl-schedule

![ci workflow](https://github.com/richie256/rtl-schedule/workflows/Docker%20Images%20CI/badge.svg)
![image size](https://img.shields.io/microbadger/image-size/richie256/rtl-schedule.svg)
![layers](https://img.shields.io/microbadger/layers/richie256/rtl-schedule.svg)
![docker pulls](https://img.shields.io/docker/pulls/richie256/rtl-schedule.svg)
![docker Stars](https://img.shields.io/docker/stars/richie256/rtl-schedule.svg)

Return the time and info of the next bus for a giving bus-stop of the RTL.

## Prerequisite

- Stop Code number.

# TODO List

- [x] Finalize the coding.
- [ ] Adding GitHub Automated actions.
- [ ] Add 24h expiration for the zip file.
- [ ] Indicate how to find a stop code.
- [ ] Create a Docker container registry.
- [ ] Sometimes, the rage of date in the file `calendar.txt` in the current zip file is in the future.

## Build

`docker build . -t rtl-schedule`
`docker run -p 80:80 rtl-schedule`

## How to start it

curl http://localhost/rtl_schedule/nextstop/32752

