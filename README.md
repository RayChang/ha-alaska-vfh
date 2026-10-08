<p align="center">
  <img src="https://raw.githubusercontent.com/RayChang/ha-alaska-vfh/main/custom_components/alaska_vfh/brand/logo.png" alt="Alaska" width="320">
</p>

# Alaska Bath Heater for Home Assistant

[![Validate](https://github.com/RayChang/ha-alaska-vfh/actions/workflows/validate.yml/badge.svg)](https://github.com/RayChang/ha-alaska-vfh/actions/workflows/validate.yml)
[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

A Home Assistant custom integration for **Alaska** bathroom ventilation fan
heaters (阿拉斯加 浴室暖風乾燥機) of the 300 and 968 series, fitted with the optional RS-485 control module and
reached through a Modbus TCP to RTU gateway. It gives each heater a proper Home
Assistant device with a mode selector, a work-time setting, quick-start buttons and
status sensors, and takes care of the quirky Modbus write rules of the device.

> **Unofficial project.** This integration is not made, endorsed or supported by
> Alaska or its manufacturer. "Alaska" and the Alaska logo are trademarks of their
> respective owners. They are used here only to identify the hardware this integration
> works with. The logo will be removed on request of the trademark owner. The MIT license of this repository does not cover the logo (see `custom_components/alaska_vfh/brand/README.md`).

## Supported hardware

You choose the model when you add a heater. The 110 V and 220 V variants of a model
share one protocol.

| Model | Status |
|-------|--------|
| Alaska **300BKP** with RS-485 module | Verified on real hardware, firmware **2.11** |
| Alaska **300BRP** | Experimental — implemented from the manufacturer's manual, not verified on hardware; please report |
| Alaska **300SRP** | Experimental — implemented from the manufacturer's manual, not verified on hardware; please report |
| Alaska **968SRN / 968SRP** | Experimental — implemented from the manufacturer's manual, not verified on hardware; please report |
| Alaska **968SKN / 968SKP** | Experimental — implemented from the manufacturer's manual, not verified on hardware; please report |

The models differ in their mode lists (the same register value can mean a different
mode), time limits and registers, which is why each has its own profile. Do not pick a
model "close enough": a wrong model can start the wrong mode. See
[docs/PROTOCOL.md](docs/PROTOCOL.md) for the tables and the places where the manuals
are ambiguous.

### Help verify other models

If you own one of the experimental models, please try every mode once, watch what the
heater really does and open a **Model verification report** issue with the result and
the diagnostics file. A report that a mode does something different from its name is
as valuable as one that everything works.

## Hardware requirements

The heater cannot talk to Home Assistant on its own: it has no network port and no
RS-485 port. Besides the heater you need **two extra pieces of hardware, both bought
separately**:

| # | What you need | Why |
|---|---------------|-----|
| 1 | The manufacturer's **RS-485 control module** for your heater (阿拉斯加 RS-485 控制模組) | An optional accessory that is not included with the heater. It plugs into the heater's controller with a ribbon cable and exposes the heater as a Modbus RTU device on an RS-485 bus. Ask Alaska or your dealer for it; see the [module manual](https://www.alaska.com.tw/pdf/69638) (Chinese; it covers all models listed above). |
| 2 | A **Modbus TCP to RTU gateway** (an RS-485 to Ethernet or Wi-Fi converter) | Home Assistant reaches the heater over the network with Modbus TCP, while the module only speaks Modbus RTU on a serial line. The gateway translates between the two. |

```
Alaska heater ── ribbon cable ── RS-485 module ── D+ / D- ── gateway ── Ethernet / Wi-Fi ── Home Assistant
                                              Modbus RTU, 9600 8N1        Modbus TCP
```

About the gateway:

- Developed and tested with the **Waveshare RS485 TO ETH (B)**. Any gateway with a real
  "Modbus TCP to RTU" protocol conversion mode should work.
- A gateway that only offers a transparent serial tunnel (raw RTU frames over TCP) does
  **not** work, and neither does a USB RS-485 adapter plugged into the Home Assistant
  host: the integration speaks Modbus TCP only.
- One gateway can serve several heaters on the same RS-485 bus.

## Prerequisites

- The **RS-485 control module** installed, with its ribbon cable connected to the
  heater controller.
- A unique **device id (1–255)** set with the DIP switches on the module. The id is the
  sum of the weights (128, 64, 32, 16, 8, 4, 2, 1) of the switches that are ON, so
  "only switch 2 ON" means id 2. All switches OFF is id 0, the broadcast address, which
  never answers.
- The **gateway** on the same network as Home Assistant, set to **9600 baud, 8N1**,
  protocol "Modbus TCP to RTU", and reachable on a TCP port (commonly 4196 or 502).
- RS-485 wiring: D+ to D+ and D- to D- on every device, common ground, a 120 Ω
  terminator at each end of long runs.
- Home Assistant **2026.4** or newer.

## Installation

### HACS (recommended)

[![Open your Home Assistant instance and open this repository inside HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=RayChang&repository=ha-alaska-vfh&category=integration)

1. In HACS open the three-dot menu, choose **Custom repositories**, add
   `https://github.com/RayChang/ha-alaska-vfh` with the category **Integration**
   (or use the button above).
2. Download **Alaska Bath Heater (Modbus)** and restart Home Assistant.

### Manual

Copy the `custom_components/alaska_vfh` folder of this repository into the
`custom_components` folder of your Home Assistant configuration and restart.

## Configuration

1. Go to **Settings → Devices & services → Add integration** and search for
   **Alaska Bath Heater**.
2. **Gateway**: enter the host name or IP address and the TCP port of the gateway
   (default 4196). The integration checks that it can connect.
3. **Heater model**: pick the model. All models other than the 300BKP are
   experimental.
4. **Device**: enter a name for the heater (the default is the model name) and its
   device id (1–255). The integration reads the heater's id register to confirm that
   the device answers and that the id matches.
5. Repeat for every further heater, each with its own device id and model. Heaters on
   the same gateway share a single TCP connection.
6. To change the gateway, device id or model of an existing device, use the
   three-dot menu of the entry → **Reconfigure**. The form is validated like the
   initial setup. The device (with its area and name) and the entities common to all
   models keep their ids. **Changing the model recreates the mode buttons** (a mode
   number means a different mode on another model) and removes entities the new
   model does not have; the mode buttons get new entity ids that match their new
   names, so check automations and scripts that use them. Entities that are kept keep
   their ids; use *Recreate entity IDs* on the device page if you want them all to
   follow a new device name.
7. Optional: **Configure** on the integration entry sets the polling interval
   (5–60 s, default 10 s).

## Entities

Entity ids are generated by Home Assistant from the device name you chose and the
entity name below (for a device called "Alaska 300BKP", for example
`select.alaska_300bkp_mode`). Entities that depend on the model are marked.

| Entity | Platform | Notes |
|--------|----------|-------|
| Mode | `select` | The modes of your model (see [docs/PROTOCOL.md](docs/PROTOCOL.md)); on the 300BKP: `heat_high`, `heat_dry`, `cool_fast`, `dry_eco`, `vent_high`, `vent_low`, `vent_24h`, `off` |
| Work time | `number` | 1 min up to the largest limit of the model (480 min on the 300BKP and 968SKN/SKP, 720 min on the others), box input, default 30 min, restored after restart |
| Mode: … | `button` (one per mode) | Start the mode with the current work time (or stop). Named after the mode, for example "Mode: High heat" |
| Reset | `button` | Resets the heater's power board (only accepted while stopped). Disabled by default, configuration category |
| Remaining time | `sensor` | Minutes, see below |
| Usage hours | `sensor` | Accumulated usage (filter) hours |
| 24h ventilation remaining | `sensor` | Minutes left in 24 hour ventilation mode |
| System status | `sensor` | Diagnostic: OK / temperature sensor open / overheat or filter needs replacing |
| Feedback status | `sensor` | Diagnostic: OK / power relay fault / motor open (the 300BRP and 300SRP have no relay fault) |
| Problem | `binary_sensor` | On when the system or feedback status is not OK |
| Heater element type | `sensor` | **968 models only.** Diagnostic: PTC / carbon |
| Air zone | `select` | **300SRP only.** Off / diffuse / focus (the manual mentions only diffuse or focus as settable while running) |
| Air direction | `select` | **300SRP only.** 65° to 125° in 15° steps, or auto swing; shows no option while the louvre is off |
| Clear filter message | `button` | **300SRP only.** Clears the "clean filter" message (writes the reset word to the usage hours register); the heater accepts it only while the system status is overheat or filter needs replacing. Configuration category |

On the **300SRP** the system status is a bit field, so it can also report "Filter
needs replacing", "Overheat" (without the filter) and "Multiple faults". The manual
says that air zone and air direction can only be changed while a mode 1–6 is running;
the integration does not check this and shows the device's error if it refuses.

Entity names are translated (English and Traditional Chinese).

## Behaviour notes

- **Write rules (FC06 / FC16).** The heater only starts the timed modes when the mode and the
  work time are written together with Modbus function code 16. A plain single-register
  write (function code 6), which is what generic Modbus tools use, is rejected with
  exception 01 for those modes (verified on the 300BKP), while "stop" and 24 hour
  ventilation use function code 6.
  The integration applies this automatically. See [docs/PROTOCOL.md](docs/PROTOCOL.md).
- **Work time** is at least 1 minute; the maximum depends on the model and on the
  mode (8 hours or 12 hours, see [docs/PROTOCOL.md](docs/PROTOCOL.md)); a longer value
  is clamped to the limit of the mode being started. Changing the **Work
  time** number while a timed mode is running pushes the new time to the heater; while
  the heater is stopped it only stores the value for the next start. Whether the heater
  is running is checked with a fresh read before anything is written, so a stale value
  cannot restart a heater that has just stopped.
- **Remaining time** is the heater's work-time register in minutes for the timed modes, the
  24 hour countdown in mode `vent_24h`, and 0 when stopped.
- **Errors are reported.** A Modbus exception or a timeout on a write is raised as a
  Home Assistant error that includes the exception code. If polling fails, the entities
  become unavailable.
- The integration keeps one TCP connection per gateway and serialises requests, so it
  can share a bus with several heaters. It declares Home Assistant's `modbus`
  integration as a dependency only to make sure `pymodbus` is installed; it does not
  use any `modbus:` hub from your YAML.

## Troubleshooting

- **Reconfigure cannot connect** to the same gateway under a new address (for example an
  IP changed to a host name): a gateway that accepts a single TCP client refuses the
  second connection while the device is loaded. Disable the device first, then
  reconfigure and enable it again.
- **Cannot connect** while adding: check host and port, and that the gateway accepts
  TCP connections from Home Assistant (some gateways allow only a limited number of
  simultaneous clients).
- **No response from device**: the device id does not match the DIP switches, the
  module is unpowered or not wired, or the id is 0. Check D+/D- polarity and the
  gateway serial settings (9600 8N1).
- **Wrong or odd modes, or Off does not stop the heater**: you probably picked the
  wrong model, and the Off button may then not stop the heater. Stop it with the wall
  panel and correct the model with **Reconfigure** (see above).
- **Modbus exception 01** when you try to start a mode: something other than this
  integration is writing mode registers with a single-register write. Use the entities
  of this integration instead. On an experimental model the profile itself may be
  wrong; please open a Model verification report.
- **Entities unavailable**: the heater stopped answering; check power, wiring and the
  gateway. The entities recover on their own after a successful poll.
- Download **diagnostics** from the device page when you open an issue. The gateway host is redacted; the port, device id, the name you gave the heater and the last raw register values are included.

## 繁體中文簡介

這是 Home Assistant 的自訂整合，用來控制裝有 RS-485 控制模組的**阿拉斯加 300／968 系列**
浴室暖風乾燥機，透過 Modbus TCP 轉 RTU 閘道器連線。每台暖風機會成為一個 HA 裝置，
提供模式選擇、運作時間、各模式按鈕，以及剩餘時間、使用時數、系統／反饋狀態與
問題感測器。

- **非官方專案**：與阿拉斯加（Alaska）及其製造商無關，「Alaska」名稱與標誌為其所有人之商標，
  此處僅用於標示相容的硬體。
- 支援機型（新增裝置時選擇，110 V 與 220 V 版本共用同一協定）：**300BKP**（已在實機驗證，
  韌體 2.11）；**300BRP、300SRP、968SRN／968SRP、968SKN／968SKP** 為**實驗性**：僅依原廠
  手冊實作，尚未在實機上驗證，歡迎回報。各機型的模式編號不同（同一個數值在不同機型代表
  不同模式），請務必選對機型，詳見 [docs/PROTOCOL.md](docs/PROTOCOL.md)。
- 300SRP 另有風域、風向選擇與「清除濾網提示」按鈕；968 系列另有發熱體類型感測器。
- 型號選錯時，模式會對應錯誤，「停止」按鈕可能無法停止暖風機（請用牆上面板停止）。可在整合項目的選單
  選「重新設定」修改閘道、裝置編號與型號（裝置與共用實體的 ID 保留；改變型號會重建模式按鈕，其實體 ID 會依新名稱改變，請檢查自動化）。
- 協助驗證：若您有實驗性機型，請逐一試過所有模式，並開一則「Model verification report」
  issue，附上實際行為與診斷檔。
- **需另外添購的硬體**（暖風機本身沒有網路或 RS-485 介面，缺一不可）：
  1. 原廠 **RS-485 控制模組**（選購配件，不隨機附贈；以排線接到暖風機主機板，
     [模組說明書](https://www.alaska.com.tw/pdf/69638)）。
  2. **Modbus TCP 轉 RTU 閘道器**（RS-485 轉乙太網路或 Wi-Fi 的轉換器）。模組只會在
     RS-485 上講 Modbus RTU，HA 則是經由網路以 Modbus TCP 連線，必須靠閘道器轉換。
     本專案以 Waveshare RS485 TO ETH (B) 開發與測試；僅提供透通模式的轉換器，或直接插在
     HA 主機上的 USB RS-485 轉接器都不支援。
- 設定：以模組上的 DIP 開關設定裝置編號（1–255，為撥到 ON 的各開關權重
  128、64、32、16、8、4、2、1 的總和；全部 OFF 為 0，不會回應），閘道器設為
  9600 8N1、「Modbus TCP to RTU」模式。
- 安裝：HACS → 自訂儲存庫 → 加入本專案網址，類別選「Integration」；或手動複製
  `custom_components/alaska_vfh`。重啟後到「設定 → 裝置與服務 → 新增整合」搜尋
  **Alaska Bath Heater**，先填閘道器位址與連接埠，再選擇機型，最後填名稱與裝置編號。
- 定時模式必須用 Modbus 功能碼 16 連同運作時間一起寫入，整合已自動處理；詳見
  [docs/PROTOCOL.md](docs/PROTOCOL.md)。

## License

[MIT](LICENSE) © 2026 Ray Chang. The Alaska name and logo (`custom_components/alaska_vfh/brand/`)
are trademarks of their owners and are not covered by this license.
