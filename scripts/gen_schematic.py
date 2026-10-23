#!/usr/bin/env python3
"""Generate the hierarchical LOBOSAT EPS schematic from the tables in this file.

    python3 scripts/gen_schematic.py          # writes EPS_Lobosat_V1.kicad_sch, sheets/*.kicad_sch,
                                              # expected_nets.json

Every part is described as `ref, symbol, value, {pin: net}`. Pins are matched by number,
then by name, then by a trailing-`*` name prefix (for the LMZM33602's stacked pads).
Every pin of every placed unit must be listed: net "NC" places a no-connect flag, and a
pin you forget makes the script stop instead of silently leaving it floating.

Connections are made by putting a label (or GND symbol) exactly on each pin's connection
point; no wires. Electrically exact, visually crowded: tidy in KiCad afterwards.
Output is deterministic (UUIDs derive from refs), so re-running gives the same files.
KiCad must be closed while this runs.
"""
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kicad_sexp import Q, parse, dump, children, child, prop, fmt, new_uuid  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PROJECT = "EPS_Lobosat_V1"
KICAD_SYM = Path("/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols")
LIB_FILES = {"EPS_Symbols": ROOT / "libs/symbols/EPS_Symbols.kicad_sym"}
SCH_VERSION = "20260306"
ROOT_UUID = new_uuid("root")
GRID = 2.54

# Nets that cross sheets -> global labels. GND -> power:GND symbol. Everything else -> local label.
GLOBAL_NETS = {
    "VSOLAR", "VBUS", "VBUS_SW", "BAT_MID", "RAIL_A", "RAIL_B",
    "EN_VID", "EN_TLM", "EN_COM", "FLT_VID_N", "FLT_TLM_N", "FLT_COM_N",
    "CHG_SHDN", "CHG_OVP", "CHG_STAT_N", "CHG_FAULT_N", "NTC_BAT",
    "I2C_SDA", "I2C_SCL", "ADC_ALERT_N", "INA_ALERT_N", "HEATER_EN",
    "PG_RAIL_A", "PG_RAIL_B", "PWR_VID", "PWR_TLM", "PWR_COM",
}

R0603, C0603 = "Resistor_SMD:R_0603_1608Metric", "Capacitor_SMD:C_0603_1608Metric"
C1206, C1210 = "Capacitor_SMD:C_1206_3216Metric", "Capacitor_SMD:C_1210_3225Metric"
R2512 = "Resistor_SMD:R_2512_6332Metric"
F1206 = "Fuse:Fuse_1206_3216Metric"
SOT23 = "Package_TO_SOT_SMD:SOT-23"
CONN2 = "Connector_JST:JST_PH_B2B-PH-K_1x02_P2.00mm_Vertical"  # placeholder, connector TBD
CELL_FP = "Battery:BatteryHolder_Keystone_1042_1x18650"


# --------------------------------------------------------------------------------------
# Part tables
# --------------------------------------------------------------------------------------
class Part:
    def __init__(self, ref, lib_id, value, pins, fp=None, mpn=None, mfr=None, dnp=False,
                 unit=1, desc=None, ds=None):
        self.ref, self.lib_id, self.value, self.pins = ref, lib_id, value, pins
        self.fp, self.mpn, self.mfr, self.dnp, self.unit = fp, mpn, mfr, dnp, unit
        self.desc, self.ds = desc, ds


class Sheet:
    def __init__(self, name, title, base, notes):
        self.name, self.title, self.base, self.notes = name, title, base, notes
        self.parts, self.flags, self._n = [], [], {}

    def ref(self, prefix):
        self._n[prefix] = self._n.get(prefix, 0) + 1
        return f"{prefix}{self.base + self._n[prefix]}"

    def add(self, prefix, lib_id, value, pins, **kw):
        ref = kw.pop("ref", None) or self.ref(prefix)
        self.parts.append(Part(ref, lib_id, value, pins, **kw))
        return ref

    def R(self, value, a, b, fp=R0603, **kw):
        kw.setdefault("mpn", "generic")
        kw.setdefault("mfr", "generic")
        return self.add("R", "Device:R", value, {"1": a, "2": b}, fp=fp, **kw)

    def C(self, value, a, b, fp=C0603, **kw):
        kw.setdefault("mpn", "generic")
        kw.setdefault("mfr", "generic")
        return self.add("C", "Device:C", value, {"1": a, "2": b}, fp=fp, **kw)


def build_sheets():
    S = []

    # ---------------------------------------------------------------- solar_input
    s = Sheet("solar_input", "Solar input + surge / backfeed protection", 100, [
        "Panel string -> TVS clamp -> SS34 blocking diode -> VSOLAR (charger input).",
        "Open: string Voc must stay below 15 V for SMBJ15A (docs/06 #2). Connector type TBD (#8).",
        "FIXED vs old schematic: TVS was reversed (cathode on GND) and would have shorted the panel.",
        "SS34 footprint is SMC (DIOM7959) from SnapEDA; parts list said SMA. Pick one before ordering.",
    ])
    s.add("J", "Connector_Generic:Conn_01x02", "SOLAR_IN", {"1": "VSOLAR_RAW", "2": "GND"},
          fp=CONN2, mpn="TBD", mfr="TBD", desc="Solar panel input, 1 = +, 2 = -. Connector TBD")
    s.add("D", "EPS_Symbols:SMBJ15A", "SMBJ15A", {"K": "VSOLAR_RAW", "A": "GND"})
    s.add("D", "EPS_Symbols:SS34", "SS34", {"A": "VSOLAR_RAW", "C": "VSOLAR"})
    s.flags = ["VSOLAR_RAW"]
    S.append(s)

    # ---------------------------------------------------------------- charger
    s = Sheet("charger", "LT3652 solar MPPT charger (2S, 8.4 V float)", 200, [
        "Charge current = 100 mV / R_SENSE = 2 A with 50 mOhm (verify against LT3652 datasheet).",
        "VFB divider 154k/100k: 3.3 V x (1 + 154/100) = 8.38 V float. Verify the datasheet's bias-current",
        "  correction (LT3652 datasheet could not be downloaded automatically - put 3652fe.pdf in datasheets/).",
        "TBD: VIN_REG divider (docs/06 #3, old 143k/100k was for 1S), TIMER cap, SHDN pull-up (#9).",
        "SHDN: BQ29209 OUT (CHG_OVP, high = overvoltage) and MCU CHG_SHDN (high = stop) each drive an",
        "  N-FET that pulls SHDN low. Inverter FET part TBD (#9).",
        "FIXED vs old schematic: STPS140ZY boost diode was reversed; anode must be on BAT (VBUS).",
    ])
    s.add("U", "EPS_Symbols:LT3652EMSE_PBF", "LT3652EMSE#PBF", {
        "VIN": "VSOLAR", "VIN_REG": "CHG_VINREG", "*SHDN": "CHG_SHDN_PIN",
        "*CHRG": "CHG_STAT_N", "*FAULT": "CHG_FAULT_N", "TIMER": "CHG_TIMER",
        "VFB": "CHG_VFB", "NTC": "CHG_NTC", "BAT": "VBUS", "SENSE": "CHG_SENSE",
        "BOOST": "CHG_BOOST", "SW": "CHG_SW", "EPAD": "GND"})
    s.C("10uF 50V X7R", "VSOLAR", "GND", fp=C1210, desc="VIN input cap")
    s.R("TBD", "VSOLAR", "CHG_VINREG", desc="VIN_REG divider top (docs/06 #3)")
    s.R("TBD", "CHG_VINREG", "GND", desc="VIN_REG divider bottom (docs/06 #3)")
    s.R("TBD", "VSOLAR", "CHG_SHDN_PIN", desc="SHDN pull-up; check LT3652 SHDN threshold/abs max")
    s.add("Q", "Transistor_FET:2N7002", "TBD", {"G": "CHG_OVP_G", "D": "CHG_SHDN_PIN", "S": "GND"},
          fp=SOT23, mpn="TBD", mfr="TBD", desc="BQ29209 OVP -> SHDN inverter (docs/06 #9)")
    s.R("1k", "CHG_OVP", "CHG_OVP_G", desc="Gate series R, per BQ29209 Fig. 9")
    s.R("100k", "CHG_OVP_G", "GND", desc="Gate pull-down")
    s.add("Q", "Transistor_FET:2N7002", "TBD", {"G": "CHG_SHDN", "D": "CHG_SHDN_PIN", "S": "GND"},
          fp=SOT23, mpn="TBD", mfr="TBD", desc="MCU charger shutdown (docs/06 #9)")
    s.R("100k", "CHG_SHDN", "GND", desc="Charger enabled while MCU is off")
    s.C("TBD", "CHG_TIMER", "GND", desc="TIMER cap: value per LT3652 datasheet")
    s.R("154k 1%", "VBUS", "CHG_VFB", desc="Float divider top")
    s.R("100k 1%", "CHG_VFB", "GND", desc="Float divider bottom")
    s.add("TH", "EPS_Symbols:NCP18XH103F03RB", "10k NTC", {"1": "CHG_NTC", "2": "GND"},
          desc="Charge NTC, mount against the cells")
    s.add("L", "EPS_Symbols:7447789004", "4.7uH", {"1": "CHG_SW", "2": "CHG_SENSE"})
    s.R("50m 1%", "CHG_SENSE", "VBUS", fp=R2512, mpn="WSL2512R0500FEA", mfr="Vishay Dale",
        desc="Charge current sense")
    s.add("D", "EPS_Symbols:CMSH3-40MA", "CMSH3-40MA", {"K": "CHG_SW", "A": "GND"},
          desc="Catch diode")
    s.C("0.1uF 25V X7R", "CHG_BOOST", "CHG_SW", desc="Boost cap (verify value vs datasheet)")
    s.add("D", "EPS_Symbols:STPS140ZY", "STPS140ZY", {"A": "VBUS", "K": "CHG_BOOST"},
          desc="Boost diode, BAT -> BOOST")
    s.C("10uF 25V X7R", "VBUS", "GND", fp=C1206, desc="BAT output cap")
    S.append(s)

    # ---------------------------------------------------------------- battery
    s = Sheet("battery", "2S2P pack on Keystone clips + protection + current monitor", 300, [
        "Ground reference: S-8252 and BQ29209 sit on BAT_N (cell negative). Everything else is on GND (P-).",
        "Only the FS8205A joins BAT_N and GND. FET1 (G1) = discharge, FET2 (G2) = charge.",
        "Per-cell fuses F301-F304 are FITTED, not DNP: DNP would open each cell. Use 0 Ohm 1206 if unwanted.",
        "Fuse/PTC ratings TBD (docs/06 #4). Shunt 10 mOhm: 4 A -> 40 mV = INA228 ADCRANGE=1 full scale.",
        "INA228 address 0x40 (A0 = A1 = GND). ACS37612 dropped (decision 2026-10-23).",
        "Keystone 1042 holder footprint from KiCad library; exact clip MPN TBD (docs/06 #10).",
    ])
    cell = dict(fp=CELL_FP, mpn="TBD (Keystone 1042?)", mfr="Keystone Electronics",
                desc="LG MJ1 18650 in holder")
    s.add("BT", "Device:Battery_Cell", "18650 cell 1A", {"+": "CELL1A_P", "-": "BAT_N"}, **cell)
    s.add("BT", "Device:Battery_Cell", "18650 cell 1B", {"+": "CELL1B_P", "-": "BAT_N"}, **cell)
    s.add("BT", "Device:Battery_Cell", "18650 cell 2A", {"+": "CELL2A_P", "-": "BAT_MID"}, **cell)
    s.add("BT", "Device:Battery_Cell", "18650 cell 2B", {"+": "CELL2B_P", "-": "BAT_MID"}, **cell)
    fuse = dict(fp=F1206, mpn="0466 series (rating TBD)", mfr="Littelfuse")
    s.add("F", "Device:Fuse", "TBD", {"1": "CELL1A_P", "2": "BAT_MID"}, desc="Per-cell fuse 1A", **fuse)
    s.add("F", "Device:Fuse", "TBD", {"1": "CELL1B_P", "2": "BAT_MID"}, desc="Per-cell fuse 1B", **fuse)
    s.add("F", "Device:Fuse", "TBD", {"1": "CELL2A_P", "2": "BAT_P"}, desc="Per-cell fuse 2A", **fuse)
    s.add("F", "Device:Fuse", "TBD", {"1": "CELL2B_P", "2": "BAT_P"}, desc="Per-cell fuse 2B", **fuse)
    s.add("F", "Device:Fuse", "TBD", {"1": "BAT_P", "2": "BAT_P_F"}, desc="Main pack fuse", **fuse)
    s.R("10m 1%", "BAT_P_F", "BAT_P_S", fp=R2512, mpn="WSL2512R0100FEA", mfr="Vishay Dale",
        desc="INA228 shunt (value proposed, confirm with fuse rating)")
    s.add("U", "EPS_Symbols:INA228AIDGSR", "INA228", {
        "IN+": "BAT_P_F", "IN-": "BAT_P_S", "VBUS": "VBUS", "VS": "RAIL_A", "GND": "GND",
        "SDA": "I2C_SDA", "SCL": "I2C_SCL", "ALERT": "INA_ALERT_N", "A0": "GND", "A1": "GND"})
    s.C("0.1uF", "RAIL_A", "GND", desc="INA228 VS bypass")
    s.add("F", "EPS_Symbols:0ZCJ0100FF2E", "0ZCJ0100FF2E", {"1": "BAT_P_S", "2": "VBUS"},
          desc="PTC, hold current may be too low (docs/06 #4)")
    s.add("U", "EPS_Symbols:S-8252AAC-M6T1U", "S-8252AAC-M6T1U", {
        "VDD": "S8252_VDD", "VC": "S8252_VC", "VSS": "BAT_N",
        "DO": "DSG_G", "CO": "CHG_G", "VM": "S8252_VM"})
    s.R("470", "BAT_P", "S8252_VDD", desc="S-8252 R1")
    s.C("0.1uF", "S8252_VDD", "BAT_N", desc="S-8252 C1 (VDD-VSS)")
    s.R("470", "BAT_MID", "S8252_VC", desc="S-8252 R2")
    s.C("0.1uF", "S8252_VC", "BAT_N", desc="S-8252 C2 (VC-VSS)")
    s.R("2k", "S8252_VM", "GND", desc="S-8252 R3 (VM to EB-)")
    s.add("Q", "EPS_Symbols:FS8205A", "FS8205A", {
        "2": "BAT_N", "3": "BAT_N", "4": "DSG_G", "1": "FET_D", "8": "FET_D",
        "5": "CHG_G", "6": "GND", "7": "GND"})
    s.add("U", "EPS_Symbols:BQ29209DRBR", "BQ29209DRBR", {
        "VC2": "BQ_VC2", "VC1": "BQ_VC1", "VC1_CB": "BQ_VC1CB", "CD": "BQ_CD",
        "GND": "BAT_N", "EXP": "BAT_N", "~{CB_EN}": "BAT_N", "VDD": "BQ_VDD", "OUT": "CHG_OVP"})
    s.R("160", "BAT_P", "BQ_VC2", desc="BQ29209 RCB2")
    s.C("0.1uF", "BQ_VC2", "BQ_VC1", desc="BQ29209 VC2-VC1")
    s.R("261 1%", "BAT_MID", "BQ_VC1", desc="BQ29209 RCB1 (datasheet 260)")
    s.C("0.1uF", "BQ_VC1", "BAT_N", desc="BQ29209 VC1-GND")
    s.R("100", "BAT_MID", "BQ_VC1CB", desc="BQ29209 RCB")
    s.R("100", "BAT_P", "BQ_VDD", desc="BQ29209 RVD")
    s.C("0.1uF", "BQ_VDD", "BAT_N", desc="BQ29209 VDD")
    s.C("0.33uF", "BQ_CD", "BAT_N", desc="BQ29209 delay ~3 s")
    s.add("TH", "EPS_Symbols:NCP18XH103F03RB", "10k NTC", {"1": "NTC_BAT", "2": "GND"},
          desc="Telemetry NTC, mount against the cells")
    s.R("10k 1%", "RAIL_A", "NTC_BAT", desc="NTC divider, ADS1015 supply as reference")
    # PWR_FLAG: nets fed from the cells (directly or through RC filters / the PTC)
    s.flags = ["BAT_P", "BAT_N", "BAT_MID", "GND", "VBUS", "S8252_VDD", "S8252_VC", "BQ_VDD"]
    S.append(s)

    # ---------------------------------------------------------------- launch_inhibit
    s = Sheet("launch_inhibit", "Launch inhibit / RBF", 400, [
        "Gate pulled up to VBUS = FET off by default. Switch NC contact closes INH_GATE -> GND when the",
        "  lever is released (deployed) = FET on. Stowed / RBF inserted = lever pressed = NC open = off.",
        "SS-5GL has SOLDER terminals; for PCB mounting consider SS-5GLD. No footprint yet (MISSING_PARTS).",
        "Symbol pin map: 2 = COM, 1 = NC, 3 = NO (verify against the switch you buy).",
        "Only ONE inhibit built; count depends on the launch provider (docs/06 #7).",
        "AO3401A Vgs max +/-12 V; pack max 8.4 V so no gate zener fitted.",
    ])
    s.add("Q", "Transistor_FET:AO3401A", "AO3401A", {"S": "VBUS", "D": "VBUS_SW", "G": "INH_GATE"},
          fp=SOT23, mpn="AO3401A", mfr="Alpha & Omega", ds="${KIPRJMOD}/datasheets/AO3401A.pdf")
    s.R("100k", "INH_GATE", "VBUS", desc="Gate pull-up, FET off by default")
    s.add("SW", "Switch:SW_SPDT", "SS-5GL", {"2": "GND", "1": "INH_GATE", "3": "NC"},
          fp="", mpn="SS-5GL", mfr="Omron", ds="${KIPRJMOD}/datasheets/SS-5GL.pdf",
          desc="Deployment / RBF microswitch, 2 = COM, 1 = NC, 3 = NO")
    S.append(s)

    # ---------------------------------------------------------------- regulation
    s = Sheet("regulation", "Rail A 3.3 V / Rail B 5 V (2x LMZM33602)", 500, [
        "Values from LMZM33602 datasheet Table 7-1 (RFBB = 10k): 3.3 V -> RFBT 23.2k, CFF 150 pF,",
        "  RT 133k (300 kHz), COUT >= 88 uF; 5 V -> RFBT 40.2k, CFF 100 pF, RT 88.7k (450 kHz), COUT >= 66 uF.",
        "AGND must NOT be tied to PGND externally (datasheet 5): each module has its own AGND net.",
        "Pins 12/13 are DNC (no symbol pin). SW pins only go to a small copper island.",
        "WARNING: datasheet recommends VIN >= 1.3 x VOUT = 6.5 V for the 5 V rail; pack goes to 6.0 V.",
        "EN tied to VIN (allowed by datasheet). Add an EN divider later if you want a UVLO.",
    ])
    for rail, v, rfbt, cff, rt in (("A", "3V3", "23.2k 1%", "150pF", "133k 1%"),
                                   ("B", "5V", "40.2k 1%", "100pF", "88.7k 1%")):
        out, ag = f"RAIL_{rail}", f"REG{rail}_AGND"
        s.add("U", "EPS_Symbols:LMZM33602RLRR", f"LMZM33602 {v}", {
            "VIN": "VBUS_SW", "EN/SYNC": "VBUS_SW", "RT": f"REG{rail}_RT", "FB": f"REG{rail}_FB",
            "AGND": ag, "PGND": "GND", "PGND*": "GND", "VOUT": out, "VOUT*": out,
            "SW": f"REG{rail}_SW", "SW*": f"REG{rail}_SW", "PGOOD": f"PG_RAIL_{rail}"})
        s.R(rt, f"REG{rail}_RT", ag, desc=f"RT, rail {rail}")
        s.R(rfbt, out, f"REG{rail}_FB", desc=f"RFBT, rail {rail} = {v}")
        s.C(cff, out, f"REG{rail}_FB", desc=f"CFF, rail {rail}")
        s.R("10k 1%", f"REG{rail}_FB", ag, desc=f"RFBB, rail {rail}")
        for _ in range(2):
            s.C("4.7uF 50V X7R", "VBUS_SW", "GND", fp=C1210, desc="CIN (2 x 4.7 uF min)")
        for _ in range(4):
            s.C("22uF 25V X7R", out, "GND", fp=C1210, desc="COUT")
    s.flags = ["REGA_AGND", "REGB_AGND", "VBUS_SW"]
    S.append(s)

    # ---------------------------------------------------------------- load_switches
    s = Sheet("load_switches", "Subsystem load switches (3x TPS2553)", 600, [
        "TPS2553 (not -1): EN active HIGH, auto-retry. 100k EN pull-downs keep loads off until the MCU says so.",
        "ILIM resistors TBD (docs/06 #5): 15k..232k, see TPS2553 datasheet Fig. 23.",
        "Output caps 10 uF chosen (datasheet: 0.1 uF min on IN; output cap per load).",
        "Rail assignment default: VID, TLM on RAIL_A (3.3 V); COM on RAIL_B (5 V). Output connectors TBD (#8).",
    ])
    for name, rail in (("VID", "RAIL_A"), ("TLM", "RAIL_A"), ("COM", "RAIL_B")):
        s.add("U", "EPS_Symbols:TPS2553DBVR", "TPS2553DBVR", {
            "IN": rail, "EN": f"EN_{name}", "OUT": f"PWR_{name}", "~{FAULT}": f"FLT_{name}_N",
            "ILIM": f"LSW_{name}_ILIM", "GND": "GND"})
        s.R("TBD", f"LSW_{name}_ILIM", "GND", desc=f"ILIM {name} (docs/06 #5)")
        s.R("100k", f"EN_{name}", "GND", desc="EN pull-down")
        s.C("0.1uF", rail, "GND", desc="IN bypass")
        s.C("10uF 16V X7R", f"PWR_{name}", "GND", fp=C1206, desc="Output cap")
        s.add("J", "Connector_Generic:Conn_01x02", f"OUT_{name}", {"1": f"PWR_{name}", "2": "GND"},
              fp=CONN2, mpn="TBD", mfr="TBD", desc=f"{name} output, 1 = +, 2 = GND. Connector TBD")
    S.append(s)

    # ---------------------------------------------------------------- telemetry
    s = Sheet("telemetry", "Telemetry: ADS1015 + MCU / OBC interface", 700, [
        "ADS1015 at 0x48 (ADDR = GND), VDD = RAIL_A 3.3 V. Use FSR +/-4.096 V; inputs must stay <= VDD.",
        "AIN0 VSOLAR x 47/377 (15 V -> 1.87 V, TVS clamp 24 V -> 3.0 V)   AIN1 VBUS x 1/3 (8.4 V -> 2.8 V)",
        "AIN2 BAT_MID x 1/2 (4.2 V -> 2.1 V)   AIN3 NTC_BAT. Battery current/voltage come from the INA228.",
        "Note: the BAT_MID divider draws ~21 uA from the bottom cells only; BQ29209 balancing covers it.",
        "MCU connector pin order (placeholder 1x20 header, real connector TBD docs/06 #8):",
        "  1 RAIL_A  2 GND  3 SDA  4 SCL  5 GND  6 EN_VID  7 EN_TLM  8 EN_COM  9 FLT_VID_N  10 FLT_TLM_N",
        "  11 FLT_COM_N  12 CHG_STAT_N  13 CHG_FAULT_N  14 CHG_SHDN  15 ADC_ALERT_N  16 INA_ALERT_N",
        "  17 HEATER_EN  18 PG_RAIL_A  19 PG_RAIL_B  20 GND",
    ])
    s.add("U", "EPS_Symbols:ADS1015IRUGR", "ADS1015", {
        "VDD": "RAIL_A", "GND": "GND", "ADDR": "GND", "SDA": "I2C_SDA", "SCL": "I2C_SCL",
        "ALERT/RDY": "ADC_ALERT_N", "AIN0": "ADC_VSOLAR", "AIN1": "ADC_VBUS",
        "AIN2": "ADC_BATMID", "AIN3": "NTC_BAT"})
    s.C("0.1uF", "RAIL_A", "GND", desc="ADS1015 VDD bypass")
    for top, bot, src, node in (("330k 0.1%", "47k 0.1%", "VSOLAR", "ADC_VSOLAR"),
                                ("200k 0.1%", "100k 0.1%", "VBUS", "ADC_VBUS"),
                                ("100k 0.1%", "100k 0.1%", "BAT_MID", "ADC_BATMID")):
        s.R(top, src, node, desc=f"{src} divider top")
        s.R(bot, node, "GND", desc=f"{src} divider bottom")
        s.C("0.1uF", node, "GND", desc="ADC input filter")
    s.C("0.1uF", "NTC_BAT", "GND", desc="ADC input filter")
    for net in ("FLT_VID_N", "FLT_TLM_N", "FLT_COM_N", "CHG_STAT_N", "CHG_FAULT_N",
                "ADC_ALERT_N", "INA_ALERT_N", "PG_RAIL_A", "PG_RAIL_B"):
        s.R("10k", "RAIL_A", net, desc=f"Pull-up {net}")
    s.R("4.7k", "RAIL_A", "I2C_SDA", desc="I2C pull-up")
    s.R("4.7k", "RAIL_A", "I2C_SCL", desc="I2C pull-up")
    mcu = ["RAIL_A", "GND", "I2C_SDA", "I2C_SCL", "GND", "EN_VID", "EN_TLM", "EN_COM",
           "FLT_VID_N", "FLT_TLM_N", "FLT_COM_N", "CHG_STAT_N", "CHG_FAULT_N", "CHG_SHDN",
           "ADC_ALERT_N", "INA_ALERT_N", "HEATER_EN", "PG_RAIL_A", "PG_RAIL_B", "GND"]
    s.add("J", "Connector_Generic:Conn_01x20", "MCU_IF",
          {str(i + 1): n for i, n in enumerate(mcu)},
          fp="Connector_PinHeader_2.54mm:PinHeader_1x20_P2.54mm_Vertical", mpn="TBD", mfr="TBD",
          desc="MCU / OBC interface, placeholder footprint")
    S.append(s)

    # ---------------------------------------------------------------- heater
    s = Sheet("heater", "Battery heater (optional, all DNP)", 800, [
        "All parts DNP until the heater decision (docs/06 #6). Thresholds TBD.",
        "Heater ON = (too cold OR HEATER_EN) AND NOT too hot.",
        "  U801A: NTC node above V_COLD -> output released -> D801 pulls the gate up.",
        "  U801B: NTC node below V_HOT -> output low -> forces the gate low (overrides both).",
        "LM393 runs from VBUS: its input common-mode range is only up to Vcc - 1.5 V.",
        "No hysteresis yet: add a feedback resistor per comparator when thresholds are chosen.",
        "D801/D802 (BAT54WS) were added to make the OR; not in the kit parts list.",
    ])
    dnp = dict(dnp=True)
    s.R("TBD", "VBUS", "HTR_SW", fp=R2512, desc="Heater element", **dnp)
    s.R("TBD", "VBUS", "HTR_SW", fp=R2512, desc="Heater element", **dnp)
    s.add("Q", "Transistor_FET:AO3400A", "AO3400A", {"D": "HTR_SW", "S": "GND", "G": "HTR_GATE"},
          fp=SOT23, mpn="AO3400A", mfr="Alpha & Omega", ds="${KIPRJMOD}/datasheets/AO3400A.pdf", **dnp)
    s.R("100k", "HTR_GATE", "GND", desc="Gate pull-down", **dnp)
    lm = dict(fp="Package_SO:SOIC-8_3.9x4.9mm_P1.27mm", mpn="LM393DR", mfr="Texas Instruments",
              ds="${KIPRJMOD}/datasheets/LM393.pdf", **dnp)
    u = s.add("U", "Comparator:LM393", "LM393", {"+": "HTR_NTC", "-": "HTR_VCOLD", "1": "HTR_COLD"},
              unit=1, desc="Too cold -> heater on", **lm)
    s.add("U", "Comparator:LM393", "LM393", {"+": "HTR_NTC", "-": "HTR_VHOT", "7": "HTR_GATE"},
          ref=u, unit=2, desc="Too hot -> force off", **lm)
    s.add("U", "Comparator:LM393", "LM393", {"V+": "VBUS", "V-": "GND"}, ref=u, unit=3, **lm)
    s.C("0.1uF", "VBUS", "GND", desc="LM393 bypass", **dnp)
    s.R("10k", "RAIL_A", "HTR_COLD", desc="U801A output pull-up", **dnp)
    sch = dict(fp="Diode_SMD:D_SOD-323", mpn="BAT54WS", mfr="onsemi", **dnp)
    s.add("D", "Device:D_Schottky", "BAT54WS", {"A": "HTR_COLD", "K": "HTR_GATE"}, **sch)
    s.add("D", "Device:D_Schottky", "BAT54WS", {"A": "HTR_EN_R", "K": "HTR_GATE"}, **sch)
    s.R("1k", "HEATER_EN", "HTR_EN_R", desc="MCU series R", **dnp)
    s.R("100k", "HEATER_EN", "GND", desc="Heater off while MCU is off", **dnp)
    s.add("TH", "EPS_Symbols:NCP18XH103F03RB", "10k NTC", {"1": "HTR_NTC", "2": "GND"},
          desc="Heater thermostat NTC, on the cells", **dnp)
    s.R("10k 1%", "RAIL_A", "HTR_NTC", desc="NTC divider", **dnp)
    s.R("TBD", "RAIL_A", "HTR_VCOLD", desc="Cold threshold top", **dnp)
    s.R("TBD", "HTR_VCOLD", "GND", desc="Cold threshold bottom", **dnp)
    s.R("TBD", "RAIL_A", "HTR_VHOT", desc="Hot threshold top", **dnp)
    s.R("TBD", "HTR_VHOT", "GND", desc="Hot threshold bottom", **dnp)
    S.append(s)
    return S


# --------------------------------------------------------------------------------------
# Library symbols
# --------------------------------------------------------------------------------------
_lib_cache = {}


def _lib(libname):
    if libname not in _lib_cache:
        path = LIB_FILES.get(libname, KICAD_SYM / f"{libname}.kicad_sym")
        tree = parse(path.read_text(encoding="utf-8"))
        _lib_cache[libname] = {str(s[1]): s for s in children(tree, "symbol")}
    return _lib_cache[libname]


def flat_symbol(lib_id):
    """Library symbol with `extends` resolved, renamed to the full lib_id for embedding."""
    libname, name = lib_id.split(":")
    syms = _lib(libname)
    sym = copy.deepcopy(syms[name])
    ext = child(sym, "extends")
    if ext:
        parent = flat_symbol(f"{libname}:{ext[1]}")
        pname = str(parent[1]).split(":")[1]
        merged = [c for c in parent if not (isinstance(c, list) and c[0] == "property")]
        own_props = children(sym, "property")
        keys = {str(p[1]) for p in own_props}
        props = own_props + [p for p in children(parent, "property") if str(p[1]) not in keys]
        merged = merged[:2] + props + merged[2:]
        for sub in children(merged, "symbol"):
            sub[1] = Q(name + str(sub[1])[len(pname):])
        sym = merged
    sym[1] = Q(lib_id)
    return sym


def unit_pins(sym, unit):
    """[(number, name, x, y, angle)] for a unit (unit 0 sub-symbols are common to all)."""
    name = str(sym[1]).split(":")[1]
    out = []
    for sub in children(sym, "symbol"):
        u, b = str(sub[1])[len(name) + 1:].split("_")
        if int(u) not in (0, unit) or int(b) not in (0, 1):
            continue
        for pin in children(sub, "pin"):
            at = child(pin, "at")
            out.append((str(child(pin, "number")[1]), str(child(pin, "name")[1]),
                        float(at[1]), float(at[2]), int(float(at[3])) % 360 if len(at) > 3 else 0))
    return out


def body_box(sym, unit):
    xs, ys = [], []
    for x, y in [(p[2], p[3]) for p in unit_pins(sym, unit)]:
        xs.append(x)
        ys.append(y)
    name = str(sym[1]).split(":")[1]
    for sub in children(sym, "symbol"):
        u = int(str(sub[1])[len(name) + 1:].split("_")[0])
        if u not in (0, unit):
            continue
        for r in children(sub, "rectangle"):
            for k in ("start", "end"):
                xs.append(float(child(r, k)[1]))
                ys.append(float(child(r, k)[2]))
    return min(xs), max(xs), min(ys), max(ys)


# --------------------------------------------------------------------------------------
# Schematic writing
# --------------------------------------------------------------------------------------
def snap(v):
    return round(round(v / GRID) * GRID, 4)


def font(justify=None, hide=False):
    e = ["effects", ["font", ["size", "1.27", "1.27"]]]
    if justify:
        e.append(["justify"] + justify.split())
    if hide:
        e.append(["hide", "yes"])
    return e


def sym_prop(key, value, x, y, hide=False, justify=None):
    return ["property", Q(key), Q(value), ["at", fmt(x), fmt(y), "0"], font(justify, hide)]


LABEL_ANGLE = {0: 180, 180: 0, 90: 270, 270: 90}  # pin angle (lib) -> label angle (schematic)
GND_ROT = {270: 0, 0: 90, 90: 180, 180: 270}       # label direction -> GND symbol rotation


class Writer:
    def __init__(self, sheet_path, base=0):
        self.items, self.lib_ids, self.base = [], [], base
        self.path = sheet_path  # instance path for symbols
        self.pwr_n = 0

    def use(self, lib_id):
        if lib_id not in self.lib_ids:
            self.lib_ids.append(lib_id)
        return flat_symbol(lib_id)

    def symbol(self, lib_id, ref, value, x, y, unit=1, rot=0, props=(), dnp=False, pins=(),
               ref_at=None, val_at=None, hide_ref=False, hide_val=False):
        self.use(lib_id)
        uid = new_uuid(f"{self.path}/{ref}/{unit}/{x}/{y}")
        node = ["symbol", ["lib_id", Q(lib_id)], ["at", fmt(x), fmt(y), str(rot)], ["unit", str(unit)],
                ["body_style", "1"], ["exclude_from_sim", "no"], ["in_bom", "yes"], ["on_board", "yes"],
                ["dnp", "yes" if dnp else "no"], ["uuid", Q(uid)]]
        rx, ry = ref_at or (x, y - 2.54)
        vx, vy = val_at or (x, y + 2.54)
        node.append(sym_prop("Reference", ref, rx, ry, hide=hide_ref))
        node.append(sym_prop("Value", value, vx, vy, hide=hide_val))
        for k, v in props:
            node.append(sym_prop(k, v, x, y, hide=True))
        for num in pins:
            node.append(["pin", Q(num), ["uuid", Q(new_uuid(f"{uid}/pin/{num}"))]])
        node.append(["instances", ["project", Q(PROJECT),
                                   ["path", Q(self.path), ["reference", Q(ref)], ["unit", str(unit)]]]])
        self.items.append(node)

    def power(self, lib_id, x, y, rot=0):
        self.pwr_n += 1
        prefix = "#FLG" if "PWR_FLAG" in lib_id else "#PWR"
        ref = f"{prefix}{self.base + self.pwr_n:04d}"
        name = lib_id.split(":")[1]
        self.symbol(lib_id, ref, name, x, y, rot=rot, pins=["1"], hide_ref=True,
                    val_at=(x, y + 3.81 if rot == 0 and name == "GND" else y - 3.81))

    def label(self, net, x, y, angle):
        uid = Q(new_uuid(f"{self.path}/lbl/{net}/{x}/{y}"))
        just = "right" if angle in (180, 270) else "left"
        if net in GLOBAL_NETS:
            self.items.append(["global_label", Q(net), ["shape", "passive"],
                               ["at", fmt(x), fmt(y), str(angle)], ["fields_autoplaced", "yes"],
                               font(just), ["uuid", uid],
                               ["property", Q("Intersheetrefs"), Q("${INTERSHEET_REFS}"),
                                ["at", fmt(x), fmt(y), str(angle)], font(just, hide=True)]])
        else:
            self.items.append(["label", Q(net), ["at", fmt(x), fmt(y), str(angle)],
                               font(just + " bottom"), ["uuid", uid]])

    def no_connect(self, x, y):
        self.items.append(["no_connect", ["at", fmt(x), fmt(y)],
                           ["uuid", Q(new_uuid(f"{self.path}/nc/{x}/{y}"))]])

    def text(self, s, x, y):
        self.items.append(["text", Q(s), ["exclude_from_sim", "no"], ["at", fmt(x), fmt(y), "0"],
                           font("left top"), ["uuid", Q(new_uuid(f"{self.path}/txt/{x}/{y}"))]])

    def file(self, sheet_uuid, paper, title, extra_tail=()):
        lib = ["lib_symbols"] + [flat_symbol(i) for i in self.lib_ids]
        return (["kicad_sch", ["version", SCH_VERSION], ["generator", Q("eeschema")],
                 ["generator_version", Q("10.0")], ["uuid", Q(sheet_uuid)], ["paper", Q(paper)],
                 ["title_block", ["title", Q(title)], ["company", Q("UNM Student Satellite Group - LOBOSAT")],
                  ["comment", "1", Q("Generated by scripts/gen_schematic.py - edit the script, not this file")]],
                 lib] + self.items + list(extra_tail) + [["embedded_fonts", "no"]])


def resolve_pins(part, sym):
    """Map every pin of the placed unit to a net, checking nothing is left out."""
    pins = unit_pins(sym, part.unit)
    res, used = [], set()
    for num, name, x, y, a in pins:
        net = None
        for key in (num, name):
            if key in part.pins:
                net, k = part.pins[key], key
                break
        else:
            for key, val in part.pins.items():
                if key.endswith("*") and name.startswith(key[:-1]):
                    net, k = val, key
                    break
        if net is None:
            raise SystemExit(f"{part.ref} ({part.lib_id} unit {part.unit}): pin {num} '{name}' not assigned")
        used.add(k)
        res.append((num, name, x, y, a, net))
    unused = set(part.pins) - used
    if unused:
        raise SystemExit(f"{part.ref}: pin keys {sorted(unused)} match no pin of {part.lib_id}")
    return res


def label_width(net):
    return len(net) * 1.1 + (5 if net in GLOBAL_NETS else 2)


def write_sheet(sheet, sheet_uuid, expected):
    w = Writer(f"/{ROOT_UUID}/{sheet_uuid}", sheet.base * 10)
    placed = []
    for p in sheet.parts:
        sym = w.use(p.lib_id)
        pins = resolve_pins(p, sym)
        x0, x1, y0, y1 = body_box(sym, p.unit)
        left = max([label_width(n) for (_, _, x, _, a, n) in pins if a == 0] + [3])
        right = max([label_width(n) for (_, _, x, _, a, n) in pins if a == 180] + [3])
        top = max([label_width(n) for (_, _, x, _, a, n) in pins if a == 270] + [4])
        bot = max([label_width(n) for (_, _, x, _, a, n) in pins if a == 90] + [4])
        placed.append((p, sym, pins, (x0 - left, x1 + right, -y1 - top - 3, -y0 + bot + 3)))

    # shelf packing, origin of each symbol snapped to the grid
    width = 380 if sum((b[1] - b[0]) * (b[3] - b[2]) for *_, b in placed) < 60000 else 540
    x, y, row_h = 20.0, 30.0 + 3.0 * len(sheet.notes), 0.0
    positions = []
    for p, sym, pins, (bx0, bx1, by0, by1) in placed:
        wdt, hgt = bx1 - bx0 + 6, by1 - by0 + 4
        if x + wdt > 20 + width:
            x, y, row_h = 20.0, y + row_h, 0.0
        positions.append((snap(x - bx0), snap(y - by0)))
        x += wdt
        row_h = max(row_h, hgt)
    total_h = y + row_h + 15
    paper = "A3" if width <= 380 and total_h <= 280 else ("A2" if total_h <= 400 and width <= 540 else "A1")

    for i, line in enumerate(sheet.notes):
        w.text(line, 20, 22 + 3.0 * i)

    for (p, sym, pins, (bx0, bx1, by0, by1)), (X, Y) in zip(placed, positions):
        props = [("Footprint", p.fp if p.fp is not None else str(prop(sym, "Footprint")[2] if prop(sym, "Footprint") else "")),
                 ("Datasheet", p.ds or (str(prop(sym, "Datasheet")[2]) if prop(sym, "Datasheet") else "~")),
                 ("Description", p.desc or (str(prop(sym, "Description")[2]) if prop(sym, "Description") else "")),
                 ("MPN", p.mpn or (str(prop(sym, "MPN")[2]) if prop(sym, "MPN") else p.value)),
                 ("Manufacturer", p.mfr or (str(prop(sym, "Manufacturer")[2]) if prop(sym, "Manufacturer") else ""))]
        x0, x1, y0, y1 = body_box(sym, p.unit)
        w.symbol(p.lib_id, p.ref, p.value, X, Y, unit=p.unit, props=props, dnp=p.dnp,
                 pins=[n for n, *_ in pins],
                 # centred above / below the pin labels so the text never sits on a label
                 ref_at=(X + (x0 + x1) / 2, Y + by0 + 1.27), val_at=(X + (x0 + x1) / 2, Y + by1 - 1.27))
        done = set()
        for num, name, px, py, a, net in pins:
            sx, sy = round(X + px, 4), round(Y - py, 4)
            if net != "NC":
                expected.setdefault(net, []).append(f"{p.ref}:{num}")
            if (sx, sy) in done:  # stacked pins share one connection point
                continue
            done.add((sx, sy))
            if net == "NC":
                w.no_connect(sx, sy)
            elif net == "GND":
                w.power("power:GND", sx, sy, rot=GND_ROT[LABEL_ANGLE[a]])
            else:
                w.label(net, sx, sy, LABEL_ANGLE[a])

    # PWR_FLAGs in a row under the parts, each with a label (or GND symbol) on its pin
    fx = 20.0
    for net in sheet.flags:
        fy = snap(total_h - 5)
        w.power("power:PWR_FLAG", snap(fx), fy)
        if net == "GND":
            w.power("power:GND", snap(fx), fy)
        else:
            w.label(net, snap(fx), fy, 270)
        fx += 25
    tree = w.file(new_uuid(f"sheetfile/{sheet.name}"), paper, sheet.title)
    (ROOT / "sheets").mkdir(exist_ok=True)
    (ROOT / "sheets" / f"{sheet.name}.kicad_sch").write_text(dump(tree) + "\n", encoding="utf-8")
    return paper


def write_root(sheets):
    w = Writer(f"/{ROOT_UUID}")
    notes = [
        "LOBOSAT EPS - 2S2P Li-ion, solar charged. One sheet per block; inter-sheet nets are global labels.",
        "Power path: SOLAR_IN -> TVS + SS34 -> VSOLAR -> LT3652 -> VBUS <- PTC <- shunt <- fuse <- BAT_P (2S2P)",
        "  VBUS -> launch inhibit (AO3401A) -> VBUS_SW -> LMZM33602 x2 -> RAIL_A 3.3 V / RAIL_B 5 V -> TPS2553 x3",
        "GND = P- (after the FS8205A cutoff FETs). BAT_N = cell negative, battery sheet only.",
        "Reference designators: 1xx solar, 2xx charger, 3xx battery, 4xx inhibit, 5xx regulation,",
        "  6xx load switches, 7xx telemetry, 8xx heater.",
        "Open items: docs/06_open_questions.md and MISSING_PARTS.md. Values marked TBD are not decided.",
    ]
    for i, line in enumerate(notes):
        w.text(line, 20, 22 + 3.0 * i)
    sheet_nodes = []
    for i, s in enumerate(sheets):
        uid = new_uuid(f"sheet/{s.name}")
        x, y = 20 + (i % 4) * 95, 60 + (i // 4) * 45
        sheet_nodes.append(
            ["sheet", ["at", fmt(x), fmt(y)], ["size", "76.2", "25.4"], ["exclude_from_sim", "no"],
             ["in_bom", "yes"], ["on_board", "yes"], ["dnp", "no"], ["fields_autoplaced", "yes"],
             ["stroke", ["width", "0.1524"], ["type", "solid"]], ["fill", ["color", "0", "0", "0", "0.0000"]],
             ["uuid", Q(uid)],
             ["property", Q("Sheetname"), Q(s.name), ["at", fmt(x), fmt(y - 0.7116), "0"], font("left bottom")],
             ["property", Q("Sheetfile"), Q(f"sheets/{s.name}.kicad_sch"), ["at", fmt(x), fmt(y + 26.0), "0"],
              font("left top")],
             ["instances", ["project", Q(PROJECT), ["path", Q(f"/{ROOT_UUID}"), ["page", Q(str(i + 2))]]]]])
        w.text(s.title, x + 2, y + 10)
    tail = [["sheet_instances", ["path", Q("/"), ["page", Q("1")]]]]
    tree = w.file(ROOT_UUID, "A3", "LOBOSAT EPS - top level")
    tree = tree[:-1] + sheet_nodes + tail + tree[-1:]
    (ROOT / f"{PROJECT}.kicad_sch").write_text(dump(tree) + "\n", encoding="utf-8")


def main():
    sheets = build_sheets()
    refs = [(p.ref, p.unit) for s in sheets for p in s.parts]
    dupes = {r for r in refs if refs.count(r) > 1}
    if dupes:
        raise SystemExit(f"duplicate references: {sorted(dupes)}")
    expected = {}
    for s in sheets:
        paper = write_sheet(s, new_uuid(f"sheet/{s.name}"), expected)
        print(f"sheets/{s.name}.kicad_sch: {len(s.parts)} symbols, paper {paper}")
    write_root(sheets)
    expected = {k: sorted(set(v)) for k, v in sorted(expected.items())}
    (ROOT / "expected_nets.json").write_text(json.dumps(expected, indent=1) + "\n", encoding="utf-8")
    print(f"{PROJECT}.kicad_sch + expected_nets.json ({len(expected)} nets)")


if __name__ == "__main__":
    main()
