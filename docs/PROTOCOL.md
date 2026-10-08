# Alaska bath heater Modbus protocol notes

This document describes the Modbus RTU interface of the Alaska 300 and 968 series
bathroom ventilation fan heaters as implemented by the optional RS-485 control module,
and how this integration uses it. The register maps follow the manufacturer's manuals.
For the 300BKP the register table is on printed page 6 (PDF page 7 in the copy the
author had). Behaviour marked **verified** was observed on real hardware, and only the
**300BKP, firmware 2.11** (register 4 = `0x020B`) has been verified. Everything else,
including all other models, comes from the manuals only and is **experimental**.

The 110 V and 220 V variants of a model share one protocol, so there are five families:
300BKP, 300BRP, 300SRP, 968SRN/968SRP and 968SKN/968SKP. The register numbers and
tables in the first sections below are those of the 300BKP; the per-model differences
follow in "Models". The same register value can mean a different mode on a different
model, so the model must be chosen correctly.

## Link settings

| Item | Value |
|------|-------|
| Physical layer | RS-485, D+ / D- (plus common ground) |
| Framing | 9600 baud, 8 data bits, no parity, 1 stop bit |
| Protocol | Modbus RTU, holding registers, 16-bit unsigned values |
| Device id | Set with the DIP switches on the control module, 1–255 (0 is the broadcast address and never answers) |
| Gateway | Any Modbus TCP to RTU gateway; the integration speaks plain Modbus TCP |

Several heaters can share one RS-485 bus, each with its own device id.

## Register map

| Reg | Access | Meaning | Notes |
|----:|--------|---------|-------|
| 0 | R | Device id | 1–255 |
| 1 | R | Baud rate code | 0 = 4800, 1 = 9600, 2 = 19200 |
| 2 | R | Serial format | 0 = N81, 1 = Even, 2 = Odd |
| 3 | R | Reserved | |
| 4 | R | Firmware version | High byte major, low byte minor. `0x020B` is 2.11 |
| 5 | R | Heater element type | 968 models: 1 = PTC, 2 = carbon. Not documented for the 300BKP; treated as opaque |
| 6 | R | System status | 0 = OK, 1 = temperature sensor open, 2 = overheat / filter needs replacing |
| 7 | R | Feedback status | 0 = OK, 1 = power relay fault, 2 = motor open |
| 8 | R | Accumulated usage hours | Filter hours, 0–2000 |
| 9 | R | 24 h ventilation remaining | Minutes, 0–1440; only meaningful in mode 7 |
| 10 | R/W | Work mode | See the mode table |
| 11 | R/W | Work time | High byte = hours (0–12), low byte = minutes (0–59) |
| 12 | W | Reset power board | Write `0xAA55`; only accepted while stopped |

The integration reads registers 6–11 in a single FC03 request on every poll, and
registers 0–5 once while setting up (for the device id check and the firmware version).
Models other than the 300BKP do not read the 0–5 block (registers 3/4 may not exist
there): the config flow reads register 0 alone, and setup reads the firmware register
(and, on 968 models, register 5) alone. A Modbus exception on one of those reads is
logged at debug level and leaves the value unknown; timeouts and connection errors
still fail the setup.

## Work modes (register 10)

| Value | Key used by the integration | Meaning |
|------:|-----------------------------|---------|
| 1 | `heat_high` | High heat |
| 2 | `heat_dry` | Heat and dry |
| 3 | `cool_fast` | Fast cool air |
| 4 | `dry_eco` | Eco dry |
| 5 | `vent_high` | Ventilation, high |
| 6 | `vent_low` | Ventilation, low |
| 7 | `vent_24h` | Continuous 24 hour ventilation |
| 12 (`0x0C`) | `off` | Stop |

Other models list different modes; see "Models" below. The mode table above applies
to the 300BKP only.

## Write rule: FC06 versus FC16

The manual notes that modes 07 and 0C may be set with function code 06 (write single
register) and all others need function code 16 (write multiple registers).

- Modes **7** and **12**: FC06, `write_register(10, mode)`.
- Modes **1–6**: FC16, `write_registers(10, [mode, work_time])`, writing the mode and the
  work time together, where `work_time = hours * 256 + minutes`.

**Verified:** FC06 with value 5 in register 10 is rejected with Modbus exception 01
(illegal function) and the device state does not change. FC16 with `[5, 20]` is
acknowledged, the fan starts and registers 10 / 11 read back as 5 / 20. FC06 with value
12 is acknowledged and stops the heater. A naive client (for example Home Assistant's
built-in `modbus.write_register` with a single integer) therefore appears to be able to
stop the heater but never to start it.

## Work time (register 11)

- Minimum 1 minute (`0x0001`). For modes 1–6 the maximum is 8 hours (`0x0800`, 480
  minutes). The manual text says "0001, 0008", which is read as a typo for modes
  1–6 because the device has no mode 8.
- Work time can only be set while a timed mode (1–6) is running; to change the time of
  a running mode, rewrite the mode and the time together with FC16.
- In mode 7 the register is read-only. **Verified:** it reads back a fixed `0x0100`, so
  it must not be interpreted as a remaining time there; the countdown is register 9.
- **Verified:** after stopping, register 11 reads 0. After starting a timed mode with a
  1 minute work time, register 11 reads `0x0001` immediately.

### Remaining time semantics used by the integration

| Device mode | Remaining time |
|-------------|----------------|
| 1–6 | register 11, `hours * 60 + minutes` |
| 7 | register 9 (starts at 1440; **verified**: 1440 within a second of starting) |
| 12 / unknown | 0 |

## Hardware-verified behaviour (firmware 2.11)

- All seven running modes (1–7) were started and stopped over Modbus TCP, and the mode
  register read back the written value each time.
- Stopping with FC06 takes effect immediately; a direct read right afterwards shows
  register 10 = 12 and register 11 = 0.
- Only one TCP connection per gateway is kept by the integration, which serialises all
  requests with a short gap between them. Gateways differ in how many simultaneous TCP
  clients they accept; check yours if another client talks to the same gateway.

## Models

All models: 9600 N81, registers 0 (device id), 6 (system status), 7 (feedback status,
shown as "Feedback status"), 8 (filter hours), 9 (24 h ventilation remaining minutes,
0–1440), 10 (mode) and 11 (work time, high byte hours, low byte minutes) as in the
register map. Stop and 24 h ventilation are written with FC06 to register 10; every
timed mode is written with FC16 to register 10 as `[mode, hours * 256 + minutes]`. The
minimum work time is 1 minute everywhere.

### Modes (register 10 value → option key)

| Value | 300BKP | 300BRP | 300SRP | 968SRN/SRP | 968SKN/SKP |
|------:|--------|--------|--------|------------|------------|
| 1 | `heat_high` | `heat` | `heat_high` | `heat_high` | `heat_high` |
| 2 | `heat_dry` | `heat_dry` | `heat_low` | `heat_low` | `heat_medium` |
| 3 | `cool_fast` | `dry_eco` | `heat_dry` | `heat_dry` | `heat_dry` |
| 4 | `dry_eco` | `cool` | `dry_eco` | `dry_eco` | `cool_fast` |
| 5 | `vent_high` | `vent_low` | `cool_fast` | `cool_fast` | `cool_slow` |
| 6 | `vent_low` | `vent_high` | `cool_slow` | `cool_slow` | `dry_eco` |
| 7 | `vent_24h` | `vent_24h` | `vent_high` | `vent_high` | `vent_high` |
| 8 | – | – | `vent_low` | `vent_low` | `vent_low` |
| 9 | – | – | `vent_24h` | `vent_24h` | `vent_24h` |
| 10 | – | `off` | `off` | `off` | – |
| 12 | `off` | – | – | – | `off` |

Note that values 5 and 6 are low and high ventilation on the 300BRP, but high and low
ventilation on the 300BKP.

### Maximum work time per timed mode (minutes)

| Model | Limits |
|-------|--------|
| 300BKP | modes 1–6: 480 |
| 300BRP | modes 1–2: 480; modes 3–6: 720 |
| 300SRP | modes 1–3: 480; modes 4–6: 720; modes 7–8: 480 |
| 968SRN/SRP | modes 1–3: 480; modes 4–8: 720 |
| 968SKN/SKP | modes 1–8: 480 |

The work time number allows up to the largest limit of the model; the limit of the
mode being started is applied when it is written (`models.plan_mode_write`, the only
place that chooses FC06 or FC16 and clamps the time).

### Other registers per model

| | Firmware register | Reset register (write `0xAA55`, FC06) | Register 5 | Polled block | Feedback (reg 7) |
|---|---:|---:|---|---|---|
| 300BKP | 4 | 12 | – | 6..11 | 0 ok, 1 relay fault, 2 motor open |
| 300BRP | 5 | 12 | – | 6..11 | 0 ok, 1 motor open |
| 300SRP | 5 | **14** | – | 6..13 | 0 ok, 1 motor open |
| 968SRN/SRP | 4 | 12 | heater type (1 PTC, 2 carbon) | 6..11 | 0 ok, 1 relay fault, 2 motor open |
| 968SKN/SKP | 4 | 12 | heater type (1 PTC, 2 carbon) | 6..11 | 0 ok, 1 relay fault, 2 motor open |

System status (register 6) is 0 = OK, 1 = temperature sensor open, 2 = overheat
(or filter needs replacing) on every model except the 300SRP. On the 300SRP it is a bit
field: bit 0 (1) temperature sensor open, bit 1 (2) overheat, bit 2 (4) filter needs
replacing. Exactly one bit set gives that state; any combination of more than one bit
(3, 5, 6, 7) is reported as "multiple faults". Values outside 0–7 are unknown.

### 300SRP extras

| Reg | Access | Meaning |
|----:|--------|---------|
| 8 | R/W | Filter hours; writing `0xAA55` (FC06) clears the "clean filter" message |
| 12 | R/W | Air zone: 1 off, 2 diffuse, 3 focus |
| 13 | R/W | Air direction: 0 off (read only), 1 = 65°, 2 = 80°, 3 = 95°, 4 = 110°, 5 = 125°, 6 = auto swing 65–125° |

The manual says registers 12 and 13 can only be set while a mode 1–6 is running. The
integration does not check this: it writes and shows the device's Modbus exception
through the normal translated error. Register 12 is the reset register on the other
models, which is why only the 300SRP polls it.

## Manual ambiguities and the interpretation used

The manuals are not always consistent. Where the text could be read in more than one
way, the integration uses the following interpretation. Experimental models are
unverified, so please report any of these that turns out to be wrong.

- **(a) 968SKN/SKP stop value.** The manual prints the stop mode as "12" without a
  radix. It is interpreted as decimal 12 (`0x0C`), because the 300BKP page prints "0C"
  for the same mode and the 968SRN/SRP page mixes "0A" with "10" for decimal 10. If the
  value were hexadecimal it would be 18 (`0x12`).
- **(b) 300SRP FC06 note.** The note says "0009, 000E" may be written with FC06. The
  stop mode is `000A` and `000E` is the reset register, so it is interpreted as 0009
  (24 h ventilation) and 000A (stop).
- **(c) 300SRP work-time limits.** The limits overlap on mode 3 and none are given for
  modes 7–8. Modes 1–3 and 7–8 use 8 hours, the conservative value.
- **(d) 300BKP work-time note.** It says "0001, 0008" although the model has modes
  1–6. It is interpreted as modes 1–6; this was verified on hardware.
- **(e) 300BKP feedback range.** The page states the range of the feedback register as
  0–1 but lists three values (0, 1, 2). All three are decoded.
- **(f) Registers 3/4 on the 300BRP and 300SRP.** Whether they answer is unknown, so
  those models identify the device with single-register reads (register 0 for the id
  check, register 5 for the firmware).

## Expected timing (not measured)

At 9600 baud a request and its reply are short frames and a reply is expected within
roughly 100 ms, but this was not measured on the hardware. A silent (absent or wrongly
addressed) slave is expected to produce a timeout rather than a Modbus exception; the
integration's 2 second timeout with no retries is chosen with that in mind.

## pymodbus usage notes (3.11)

pymodbus 3.11 uses keyword-only arguments for the slave address; older positional
forms raise `TypeError`.

```python
from pymodbus.client import AsyncModbusTcpClient

client = AsyncModbusTcpClient(host, port=port, timeout=2, retries=0, reconnect_delay=0)
await client.connect()  # returns bool
rr = await client.read_holding_registers(6, count=6, device_id=slave_id)
wr = await client.write_registers(10, [mode, work_time], device_id=slave_id)  # FC16
wr = await client.write_register(10, 12, device_id=slave_id)  # FC06
if rr.isError():
    ...  # an ExceptionResponse carries .exception_code
client.close()
```

- `reconnect_delay=0` turns off pymodbus' background reconnection. The integration
  reconnects itself and calls `close()` before `connect()`; otherwise a gateway outage
  can leave a second, leaked TCP connection.
- `timeout=2` and `retries=0` keep one silent device from holding the shared bus lock
  for long.
- Home Assistant's own `modbus` integration is declared as a dependency only to make
  sure pymodbus is installed; this integration does not use the `modbus` hubs.

## References

- Manufacturers' manuals for the RS-485 control modules of the 300BKP, 300BRP, 300SRP, 968SRN/968SRP and 968SKN/968SKP (register tables, mode lists).
