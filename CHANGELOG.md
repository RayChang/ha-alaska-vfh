# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [0.2.0] - 2026-10-08

### Added

- Multi-model support: the heater model is chosen when a device is added. New
  experimental profiles for the **300BRP**, **300SRP**, **968SRN/968SRP** and
  **968SKN/968SKP**, implemented from the manufacturer's manuals and not verified on
  hardware. The 300BKP stays the verified model.
- Per-model mode tables, work-time limits, firmware/reset registers and status
  decoding in one profile per model (`models.py`).
- 300SRP: air zone and air direction selects, "Clear filter message" button, and a
  bit-field system status (filter needs replacing, overheat, multiple faults).
- 968 models: heater element type diagnostic sensor.
- Diagnostics include the model and heater type.
- Reconfigure flow: host, port, device id and model of an existing entry can be changed
  in one form (validated like the initial setup). The device (area, custom name) and
  the entities common to all models keep their ids. Changing the model recreates the
  mode buttons (their entity ids may change, check automations) and removes entities
  the new model does not have; a default entry name follows the new model.
- Unit tests for the model profiles, translations and (optionally) the Home Assistant
  config flow and migration; a "Model verification report" issue form.

### Changed

- The model step warns that a wrong model can make the Off button ineffective.
- Write guards: air zone, air direction and filter reset are refused (translated error)
  on models without them or for out-of-range values; an unknown model in a config
  entry fails the setup with a clear message instead of a traceback.
- Gateway Modbus exceptions 0x0A / 0x0B on the optional identification reads now fail
  the setup (retry) instead of leaving the firmware unknown.
- Mode button translation keys are now named after the mode (`mode_heat_high`)
  instead of the register value. The 300BKP texts, entity unique ids and behaviour are
  unchanged.
- Config entries are migrated to version 1.2 and get `model: 300bkp`.
- Models other than the 300BKP identify the device with single-register reads (a
  Modbus exception on the firmware or heater type read is tolerated).

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
