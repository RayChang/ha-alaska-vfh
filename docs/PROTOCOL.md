# Alaska 300BKP Modbus protocol notes

This document describes the Modbus RTU interface of the Alaska 300BKP bathroom
ventilation fan heater as implemented by the optional RS-485 control module, and how
this integration uses it. The register map follows the manufacturer's manual
(`300BKP`, register table on printed page 6, which is PDF page 7 in the copy the
author had). Behaviour marked **verified** was observed on real hardware with
**firmware 2.11** (register 4 = `0x020B`). Everything else comes from the manual only.

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
| 5 | R | Heater element type | Not documented for the 300BKP; treated as opaque |
| 6 | R | System status | 0 = OK, 1 = temperature sensor open, 2 = overheat / filter needs replacing |
| 7 | R | Feedback status | 0 = OK, 1 = power relay fault, 2 = motor open |
| 8 | R | Accumulated usage hours | Filter hours, 0–2000 |
| 9 | R | 24 h ventilation remaining | Minutes, 0–1440; only meaningful in mode 7 |
| 10 | R/W | Work mode | See the mode table |
| 11 | R/W | Work time | High byte = hours (0–12), low byte = minutes (0–59) |
| 12 | W | Reset power board | Write `0xAA55`; only accepted while stopped |

The integration reads registers 6–11 in a single FC03 request on every poll, and
registers 0–5 once while setting up (for the device id check and the firmware version).

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

Other 300/968 series models list different modes. They have not been tested and the
mode table above must not be assumed to apply to them.

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

- Manufacturer manual for the 300BKP RS-485 control module (register table, mode list).
