# RTL-Schedule

Return the time and info of the next bus for a giving bus-stop of the RTL.

## Prerequisite

- Stop Code number.

# TODO List

- [x] Finalize the coding.
- [ ] Indicate how to find a stop code.
- [ ] Create a Docker container registry.
- [ ] Sometimes, the rage of date in the file `calendar.txt` in the current zip file is in the future.

## Build

`docker build . -t rtl-schedule`
`docker run -p 80:80 rtl-schedule`

## How to start it

curl http://localhost/rtl_schedule/nextstop/32752

