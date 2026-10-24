# LOBOSAT EPS Board

Design of the power board for LOBOSAT, the UNM Student Satellite Group's 1U cubesat. It will be one of three boards in the stack.

Goal: solar-powered, solderability (hand solder and hotplate), provide 3V3 and 5V, provide telemetry data that can be downlinked on the health status of the EPS system.

## What it does

- Takes power from 12x Anysolar SM141K10TF solar cells (string configuration still open)
- Charges an LG MJ1 18650 pack (2S2P, cells in Keystone clips on the board) through an LT3652 MPPT charger, 8.4 V float, 2 A
- Protects the battery in three layers: S-8252AAC (primary: over/under-voltage, overcurrent, short circuit, drives the FS8205A cutoff FETs), BQ29209 (independent backup overvoltage → stops the charger, plus cell balancing), and a fuse + PTC
- Regulates the battery bus with two LMZM33602 buck modules: Rail A = 3V3, Rail B = 5V
- Switches three subsystems (videography, telemetry, comms) through TPS2553 current-limited load switches the flight computer can turn on/off
- Monitors battery current, bus voltage and charge with an INA228, and solar voltage, bus voltage, mid-cell voltage and battery temperature with an ADS1015, all over I²C
- Has an RBF / deployment switch (SS-5GL) that disconnects the bus from the regulators until deployment

## Status (2026-10-24)

- Schematic complete as **one A0 sheet**, every block in its own box. ERC: **0 violations**.
- Netlist checked pin-by-pin against `expected_nets.json` (`scripts/check_netlist.py`): PASS.
- Every symbol is linked to a footprint and a 3D model (except the SS-5GL switch, see below).
- **Not done:** the values marked `TBD` (below), the SS-5GL footprint, connector choice, PCB layout.

## Why some values are `TBD`

These are left blank on purpose because they depend on decisions or data that don't exist yet. Picking a number now would be a guess that looks like a decision.

| Part | Why it's open | What decides it |
|---|---|---|
| R201 / R202: LT3652 VIN_REG divider | Sets the solar panel voltage the charger holds (MPPT point). The old 143k/100k was for a 1S pack | Solar string configuration (12 cells in series/parallel?) → its max-power voltage |
| R203: LT3652 SHDN pull-up, C202: TIMER cap | Need the LT3652 datasheet (analog.com blocks scripted downloads, it's not in `datasheets/` yet) | LT3652 datasheet |
| R601 / R603 / R605: TPS2553 ILIM | Sets each subsystem's current limit (15k–232k) | Peak current of the camera, telemetry radio and comms |
| F301–F305: fuse ratings | Main fuse and per-cell fuses must sit above normal current and below cell/trace limits | Max bus current (sum of the subsystems) |
| Q201 / Q202: charger shutdown FETs | Any small logic-level N-FET works (2N7002-type); just needs a part choice | Pick one you can buy |
| J101, J601–J603, J701: connectors | Placeholder footprints (JST-PH, 1×20 header) | Stack / harness connector choice |

The full list of open questions is in `docs/06_open_questions.md`; missing parts and datasheets in `MISSING_PARTS.md`.

## What changed in this version (vs. the old hand-drawn schematic)

**Design decisions**
- Telemetry uses the **INA228 + ADS1015** (the ACS37612 current sensor is dropped). The INA228 measures battery current through a 10 mΩ shunt in the pack positive path.
- Rails fixed at **3.3 V (A)** and **5 V (B)**; LMZM33602 feedback, frequency and capacitor values taken from datasheet Table 7-1.
- **Battery heater dropped.** J701 pin 17 (was HEATER_EN) is now a spare pin.
- Schematic is a **single sheet** instead of separate hierarchical sheets.

**Bugs fixed from the old schematic**
- The **SMBJ15A TVS was reversed** (cathode on GND). It would have conducted and shorted the solar panel. Now cathode → panel +.
- The **STPS140ZY boost diode was reversed** (cathode on BAT). The LT3652 boost capacitor could never charge, so the charger wouldn't switch. Now anode → BAT, cathode → BOOST.
- The **BQ29209 footprint** numbered its 4 thermal vias 10–13 instead of 9 (the exposed pad). On the PCB they would have been separate nets shorted into the pad.
- Library hygiene: no footprint had a 3D model linked, there was no `fp-lib-table`, and several vendor symbols had wrong pin types. The old schematic had **176 ERC violations**; now 0.

**Battery protection, completed**
- S-8252AAC with the datasheet RC filters (470 Ω / 0.1 µF) and VM resistor (2 kΩ), driving the FS8205A dual FET in the pack negative. `BAT_N` (cell negative) and `GND` (pack negative after the FETs) are separate nets on purpose.
- BQ29209 wired per its datasheet Figure 9 (balance resistors 160/261/100 Ω, 0.33 µF ≈ 3 s delay). Its overvoltage output shuts the charger off through an N-FET; the flight computer can do the same through a second FET (`CHG_SHDN`).
- Note: the S-8252 symbol/footprint were downloaded for the **AAZ** variant. All S-8252 parts share the pinout, so the same symbol is used with the MPN set to **S-8252AAC** (4.300 V overcharge). Order the AAC.

**Repo reorganized**
- `libs/symbols`, `libs/footprints`, `libs/3d` hold one consolidated project library, built by `scripts/consolidate_libs.py`; original vendor downloads are untouched in `libs/_downloads/`.
- Library tables use `${KIPRJMOD}` so the project opens on any machine.
- `.history`, `.DS_Store`, lock files and datasheet PDFs are no longer tracked.

## Things to know before layout

- **5 V rail at low battery:** the LMZM33602 wants VIN ≥ 1.3 × VOUT = 6.5 V, but the pack goes down to 6.0 V. The 5 V rail will drop out near empty.
- **SS-5GL** has solder terminals and no footprint yet. The PCB-terminal version is the **SS-5GLD**.
- **SS34** footprint is SMC (7.9 × 5.9 mm); the parts list says SMA. Pick the package you'll buy.
- Check every vendor part in KiCad's 3D viewer; four parts use a generic KiCad body as their 3D model.

## Bill of materials

Exported from the schematic: `BOM.csv` (62 line items, 121 parts). Generic passives have MPN `generic`; pick specific parts when ordering (0.1 % resistors are for the ADC dividers).

| Refs | Qty | Value | MPN | Manufacturer | Footprint |
|---|---|---|---|---|---|
| BT301 | 1 | 18650 cell 1A | TBD (Keystone 1042?) | Keystone Electronics | BatteryHolder_Keystone_1042_1x18650 |
| BT302 | 1 | 18650 cell 1B | TBD (Keystone 1042?) | Keystone Electronics | BatteryHolder_Keystone_1042_1x18650 |
| BT303 | 1 | 18650 cell 2A | TBD (Keystone 1042?) | Keystone Electronics | BatteryHolder_Keystone_1042_1x18650 |
| BT304 | 1 | 18650 cell 2B | TBD (Keystone 1042?) | Keystone Electronics | BatteryHolder_Keystone_1042_1x18650 |
| C201 | 1 | 10uF 50V X7R | generic | generic | C_1210_3225Metric |
| C202 | 1 | TBD | generic | generic | C_0603_1608Metric |
| C203 | 1 | 0.1uF 25V X7R | generic | generic | C_0603_1608Metric |
| C204 | 1 | 10uF 25V X7R | generic | generic | C_1206_3216Metric |
| C301-C306,C601,C603,C605,C701-C705 | 14 | 0.1uF | generic | generic | C_0603_1608Metric |
| C307 | 1 | 0.33uF | generic | generic | C_0603_1608Metric |
| C501 | 1 | 150pF | generic | generic | C_0603_1608Metric |
| C502,C503,C515,C516 | 4 | 4.7uF 50V X7R | generic | generic | C_1210_3225Metric |
| C504-C507,C518-C521 | 8 | 22uF 25V X7R | generic | generic | C_1210_3225Metric |
| C517 | 1 | 100pF | generic | generic | C_0603_1608Metric |
| C602,C604,C606 | 3 | 10uF 16V X7R | generic | generic | C_1206_3216Metric |
| D101 | 1 | SMBJ15A | SMBJ15A | Littelfuse | DIOM4336X265N |
| D102 | 1 | SS34 | SS34 | onsemi | DIOM7959X265N |
| D201 | 1 | CMSH3-40MA | CMSH3-40MA TR13 PBFREE | Central Semiconductor | CR_SMA-CMSH3-40MA_CNS |
| D202 | 1 | STPS140ZY | STPS140ZY | STMicroelectronics | SOD123_2P8X1P7_STM |
| F301-F305 | 5 | TBD | 0466 series (rating TBD) | Littelfuse | Fuse_1206_3216Metric |
| F306 | 1 | 0ZCJ0100FF2E | 0ZCJ0100FF2E | Bel Fuse | RESC3216X125N |
| J101 | 1 | SOLAR_IN | TBD | TBD | JST_PH_B2B-PH-K_1x02_P2.00mm_Vertical |
| J601 | 1 | OUT_VID | TBD | TBD | JST_PH_B2B-PH-K_1x02_P2.00mm_Vertical |
| J602 | 1 | OUT_TLM | TBD | TBD | JST_PH_B2B-PH-K_1x02_P2.00mm_Vertical |
| J603 | 1 | OUT_COM | TBD | TBD | JST_PH_B2B-PH-K_1x02_P2.00mm_Vertical |
| J701 | 1 | MCU_IF | TBD | TBD | PinHeader_1x20_P2.54mm_Vertical |
| L201 | 1 | 4.7uH | 7447789004 | Wurth Elektronik | WE-PD_7332R |
| Q201,Q202 | 2 | TBD | TBD | TBD | SOT-23 |
| Q301 | 1 | FS8205A | FS8205A | Fortune Semiconductor | SOP65P640X120-8N |
| Q401 | 1 | AO3401A | AO3401A | Alpha & Omega | SOT-23 |
| R201-R203,R601,R603,R605 | 6 | TBD | generic | generic | R_0603_1608Metric |
| R204 | 1 | 1k | generic | generic | R_0603_1608Metric |
| R205,R206,R401,R602,R604,R606 | 6 | 100k | generic | generic | R_0603_1608Metric |
| R207 | 1 | 154k 1% | generic | generic | R_0603_1608Metric |
| R208 | 1 | 100k 1% | generic | generic | R_0603_1608Metric |
| R209 | 1 | 50m 1% | WSL2512R0500FEA | Vishay Dale | R_2512_6332Metric |
| R301 | 1 | 10m 1% | WSL2512R0100FEA | Vishay Dale | R_2512_6332Metric |
| R302,R303 | 2 | 470 | generic | generic | R_0603_1608Metric |
| R304 | 1 | 2k | generic | generic | R_0603_1608Metric |
| R305 | 1 | 160 | generic | generic | R_0603_1608Metric |
| R306 | 1 | 261 1% | generic | generic | R_0603_1608Metric |
| R307,R308 | 2 | 100 | generic | generic | R_0603_1608Metric |
| R309,R503,R509 | 3 | 10k 1% | generic | generic | R_0603_1608Metric |
| R501 | 1 | 133k 1% | generic | generic | R_0603_1608Metric |
| R502 | 1 | 23.2k 1% | generic | generic | R_0603_1608Metric |
| R507 | 1 | 40.2k 1% | generic | generic | R_0603_1608Metric |
| R508 | 1 | 88.7k 1% | generic | generic | R_0603_1608Metric |
| R701 | 1 | 330k 0.1% | generic | generic | R_0603_1608Metric |
| R702 | 1 | 47k 0.1% | generic | generic | R_0603_1608Metric |
| R703 | 1 | 200k 0.1% | generic | generic | R_0603_1608Metric |
| R704-R706 | 3 | 100k 0.1% | generic | generic | R_0603_1608Metric |
| R707-R715 | 9 | 10k | generic | generic | R_0603_1608Metric |
| R716,R717 | 2 | 4.7k | generic | generic | R_0603_1608Metric |
| SW401 | 1 | SS-5GL | SS-5GL | Omron | — (missing) |
| TH201,TH301 | 2 | 10k NTC | NCP18XH103F03RB | Murata | THRMC1608X95N |
| U201 | 1 | LT3652EMSE#PBF | LT3652EMSE#PBF | Analog Devices | MSOP-12_MSE |
| U301 | 1 | INA228 | INA228AIDGSR | Texas Instruments | VSSOP10_DGS_TEX |
| U302 | 1 | S-8252AAC-M6T1U | S-8252AAC-M6T1U | ABLIC | SOT236-A-PKG_MP006-A-P-SD-2.1_ABL |
| U303 | 1 | BQ29209DRBR | BQ29209DRBR | Texas Instruments | SON65P300X300X100-9N |
| U501,U503 | 2 | LMZM33602 3V3 | LMZM33602RLRR | Texas Instruments | VREG_LMZM33602RLRR |
| U601-U603 | 3 | TPS2553DBVR | TPS2553DBVR | Texas Instruments | SOT-23-6 |
| U701 | 1 | ADS1015 | ADS1015IRUGR | Texas Instruments | IC_ADS1015IRUGR |

## Repo map

| Path | What |
|---|---|
| `EPS_Lobosat_V1.kicad_pro` | Open this in KiCad 10 |
| `EPS_Lobosat_V1.kicad_sch` | The schematic (one A0 sheet) |
| `BOM.csv` | Bill of materials exported from the schematic |
| `libs/` | Project libraries (`EPS_Symbols`, `EPS_Footprints`, `3d/`); vendor originals in `libs/_downloads/` |
| `docs/` | Design spec, connections per block, parts list, open questions, KiCad workflow notes |
| `MISSING_PARTS.md` | Parts, datasheets and decisions still needed |
| `LINK_REPORT.md` | Symbol → footprint → 3D model audit |
| `expected_nets.json` | Verified connections, used by `check_netlist.py` to catch accidental changes |
| `scripts/` | `consolidate_libs.py`, `audit_libs.py`, `check_netlist.py`, `fetch_datasheets.sh`; `archive/gen_schematic.py` built the first version (retired, don't run) |
| `datasheets/` | PDFs (not committed; run `bash scripts/fetch_datasheets.sh`) |

## Checking the schematic after edits

```bash
K=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli
$K sch erc --severity-all -o out/erc.rpt EPS_Lobosat_V1.kicad_sch
$K sch export netlist --format kicadsexpr -o out/EPS_Lobosat_V1.net EPS_Lobosat_V1.kicad_sch
python3 scripts/check_netlist.py out/EPS_Lobosat_V1.net expected_nets.json
$K sch export bom --fields 'Reference,Value,MPN,Manufacturer,Footprint,${QUANTITY},${DNP},Description' \
  --labels 'Refs,Value,MPN,Manufacturer,Footprint,Qty,DNP,Description' --group-by 'Value,MPN,Footprint,${DNP}' -o BOM.csv EPS_Lobosat_V1.kicad_sch
```

If `check_netlist.py` fails after an intentional change, regenerate `expected_nets.json` from the new netlist (see `CLAUDE.md`).

## Notes to future me
