# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-10-07

### Added

- First release: Home Assistant config-flow integration for the Alaska 300BKP bath
  heater over Modbus TCP (any TCP to RS-485 gateway).
- Entities per heater: mode select, work time number, one button per mode plus a
  disabled-by-default reset button, remaining time, usage hours, 24 h ventilation
  remaining, system status and feedback status sensors, and a problem binary sensor.
- Correct FC06 / FC16 write handling (modes 1–6 are written together with the work
  time using FC16), with write errors reported to the user including the Modbus
  exception code.
- One shared TCP connection per gateway, so several heaters on one bus work together.
- Options flow for the polling interval, diagnostics download, English and Traditional
  Chinese translations, brand images.
