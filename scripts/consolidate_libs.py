#!/usr/bin/env python3
"""Build the project libraries from the vendor downloads in libs/_downloads/.

Outputs (overwritten every run, originals in libs/_downloads/ are never modified):
  libs/symbols/EPS_Symbols.kicad_sym
  libs/footprints/EPS_Footprints.pretty/*.kicad_mod
  libs/3d/*.step
  sym-lib-table, fp-lib-table

Every fix applied to a vendor file is listed in PARTS below with the reason, so the
diff from the original download is reviewable. Run from the project root:
  python3 scripts/consolidate_libs.py
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kicad_sexp import Q, parse, dump, children, child, walk, set_prop, new_uuid  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DL = ROOT / "libs" / "_downloads"
SYM_OUT = ROOT / "libs" / "symbols" / "EPS_Symbols.kicad_sym"
FP_OUT = ROOT / "libs" / "footprints" / "EPS_Footprints.pretty"
MODEL_OUT = ROOT / "libs" / "3d"
KICAD = Path("/Applications/KiCad/KiCad.app/Contents")
KICAD_CLI = KICAD / "MacOS" / "kicad-cli"
KICAD_3D = KICAD / "SharedSupport" / "3dmodels"
KICAD_SYM = KICAD / "SharedSupport" / "symbols"

TI = "Texas Instruments"
DS = "${KIPRJMOD}/datasheets/"

# name in EPS_Symbols -> where it comes from and what it links to.
#   src       : (file, symbol name) inside libs/_downloads, or ("kicad", "Lib:Sym") to clone a built-in
#   fp        : footprint file stem (copied into EPS_Footprints.pretty) or a full KiCad built-in "Lib:Name"
#   fp_src    : vendor footprint path (relative to libs/_downloads)
#   model     : 3D file in libs/_downloads, or ("kicad", "<dir>/<file>") for a generic KiCad body
#   pin_names : {pin number: new name} where the vendor symbol left names blank (verified, see note)
PARTS = {
    "LT3652EMSE_PBF": dict(
        src=("snapeda_symbols/LT3652EMSE_PBF.kicad_sym", "LT3652EMSE_PBF"),
        fp="MSOP-12_MSE", fp_src="snapeda_footprints/MSOP-12_MSE.kicad_mod",
        model="snapeda_3d/LT3652EMSE_PBF.step",
        # vendor typed BAT and VFB as outputs; both are sense inputs (charge current flows in SENSE/BAT R)
        pin_types={"BAT": "input", "VFB": "input"},
        mpn="LT3652EMSE#PBF", mfr="Analog Devices",
        ds="https://www.analog.com/media/en/technical-documentation/data-sheets/3652fe.pdf",
        desc="Solar MPPT Li-ion charger, MSOP-12 exposed pad (pin 13 = EP = GND)"),
    "LMZM33602RLRR": dict(
        src=("snapeda_symbols/LMZM33602RLRR.kicad_sym", "LMZM33602RLRR"),
        fp="VREG_LMZM33602RLRR", fp_src="snapeda_footprints/VREG_LMZM33602RLRR.kicad_mod",
        model="snapeda_3d/LMZM33602RLRR.step",
        # Duplicate VOUT/SW/PGND pins (thermal-via pads) are "output"/"power_in" copies of the main
        # pin; make them passive so ERC doesn't report output-to-output conflicts on one net.
        pin_types={"VOUT": "power_out", "VOUT__*": "passive", "SW__*": "passive", "PGND__*": "passive"},
        mpn="LMZM33602RLRR", mfr=TI, ds=DS + "LMZM33602.pdf",
        desc="36 V 2 A buck power module, QFN-18 (pads 12/13 = DNC, no symbol pin on purpose)"),
    "S-8252AAC-M6T1U": dict(
        # Vendor symbol was downloaded for the AAZ variant. Every S-8252xxx-M6T1U shares the
        # SOT-23-6 pinout (datasheet Table 6), so only the name/MPN changes; AAC = 4.300 V / 2.400 V.
        src=("S-8252AAZ-M6T1U/KiCADv6/S-8252.kicad_sym", "S-8252AAZ-M6T1U"),
        fp="SOT236-A-PKG_MP006-A-P-SD-2.1_ABL",
        fp_src="S-8252AAZ-M6T1U/KiCADv6/footprints.pretty/SOT236-A-PKG_MP006-A-P-SD-2.1_ABL.kicad_mod",
        model=("kicad", "Package_TO_SOT_SMD.3dshapes/SOT-23-6.step"),
        # vendor had VSS power_out (it is the negative supply input) and VM unspecified (it is a sense input)
        pin_types={"VSS": "power_in", "VM": "input"},
        mpn="S-8252AAC-M6T1U", mfr="ABLIC", ds=DS + "S-8252.pdf",
        desc="2-cell Li-ion protection, OC 4.300 V, OD 2.400 V, SOT-23-6"),
    "BQ29209DRBR": dict(
        src=("BQ29209DRBR/BQ29209DRBR.kicad_sym", "BQ29209DRBR"),
        fp="SON65P300X300X100-9N", fp_src="BQ29209DRBR/SON65P300X300X100-9N.kicad_mod",
        model="BQ29209DRBR/BQ29209DRBR.step",
        # Vendor footprint numbers the 4 thermal vias inside the exposed pad 10..13. They sit on
        # top of pad 9 copper, so they must carry pad 9's net (datasheet: thermal pad = GND).
        pad_renumber={"10": "9", "11": "9", "12": "9", "13": "9"},
        mpn="BQ29209DRBR", mfr=TI, ds=DS + "BQ29209.pdf",
        desc="2-cell backup overvoltage protection (4.30 V) + cell balancing, VSON-8"),
    "FS8205A": dict(
        src=("FS8205A/FS8205A.kicad_sym", "FS8205A"),
        fp="SOP65P640X120-8N", fp_src="FS8205A/SOP65P640X120-8N.kicad_mod",
        model="FS8205A/FS8205A.step",
        mpn="FS8205A", mfr="Fortune Semiconductor", ds="",
        desc="Dual N-MOSFET common drain, TSSOP-8 (1,8 D; 2,3 S1; 4 G1; 5 G2; 6,7 S2)"),
    "INA228AIDGSR": dict(
        src=("INA228AIDGSR/KiCADv6/2026-10-02_21-11-31.kicad_sym", "INA228AIDGSR"),
        fp="VSSOP10_DGS_TEX", fp_src="INA228AIDGSR/KiCADv6/footprints.pretty/VSSOP10_DGS_TEX.kicad_mod",
        model=("kicad", "Package_SO.3dshapes/MSOP-10_3x3mm_P0.5mm.step"),
        pin_types={"GND": "power_in"},  # vendor had power_out
        mpn="INA228AIDGSR", mfr=TI, ds=DS + "INA228.pdf",
        desc="85 V 20-bit I2C power/energy/charge monitor, VSSOP-10"),
    "ADS1015IRUGR": dict(
        src=("ADS1015IRUGR/ADS1015IRUGR.kicad_sym", "ADS1015IRUGR"),
        fp="IC_ADS1015IRUGR", fp_src="ADS1015IRUGR/IC_ADS1015IRUGR.kicad_mod",
        model="ADS1015IRUGR/ADS1015IRUGR.step",
        mpn="ADS1015IRUGR", mfr=TI, ds=DS + "ADS1015.pdf",
        desc="4-ch 12-bit I2C ADC, X2QFN-10"),
    "STPS140ZY": dict(
        src=("STPS140ZY/2026-09-20_06-34-23.kicad_sym", "STPS140ZY"),
        fp="SOD123_2P8X1P7_STM", fp_src="STPS140ZY/footprints.pretty/SOD123_2P8X1P7_STM.kicad_mod",
        model=("kicad", "Diode_SMD.3dshapes/D_SOD-123.step"),
        pin_types={"K": "passive", "A": "passive"},  # vendor left them "unspecified"
        mpn="STPS140ZY", mfr="STMicroelectronics", ds="https://www.st.com/resource/en/datasheet/stps140z-y.pdf",
        desc="40 V 1 A Schottky, SOD-123 (pin 1 = K)"),
    "CMSH3-40MA": dict(
        src=("CMSH3-40MA/CSMH.kicad_sym", "CMSH3-40MA_TR13_PBFREE"),
        fp="CR_SMA-CMSH3-40MA_CNS", fp_src="CMSH3-40MA/footprints.pretty/CR_SMA-CMSH3-40MA_CNS.kicad_mod",
        model=("kicad", "Diode_SMD.3dshapes/D_SMA.step"),
        # Vendor pins have no names. The symbol drawing puts the cathode bar on the pin 1 side.
        pin_names={"1": "K", "2": "A"},
        pin_types={"K": "passive", "A": "passive"},  # vendor left them "unspecified"
        mpn="CMSH3-40MA TR13 PBFREE", mfr="Central Semiconductor", ds="https://www.centralsemi.com/get_document.php?cmp=1&mergetype=pd&mergepath=pd&pdf_id=CMSH3-40MA.PDF",
        desc="40 V 3 A Schottky, SMA (pin 1 = K)"),
    "SS34": dict(
        src=("snapeda_symbols/SS34.kicad_sym", "SS34"),
        fp="DIOM7959X265N", fp_src="snapeda_footprints/DIOM7959X265N.kicad_mod",
        model="snapeda_3d/SS34.step",
        mpn="SS34", mfr="onsemi", ds="https://www.onsemi.com/pdf/datasheet/ss34-d.pdf",
        desc="40 V 3 A Schottky. NOTE footprint is SMC (7.9 x 5.9 mm), parts list says SMA"),
    "SMBJ15A": dict(
        # No vendor symbol was downloaded (only footprint + 3D). Clone KiCad's zener drawing
        # (pin 1 = K, pin 2 = A); IPC-7351 diode footprints put the cathode on pad 1.
        src=("kicad", "Device:D_Zener"),
        fp="DIOM4336X265N", fp_src="snapeda_footprints/DIOM4336X265N.kicad_mod",
        model="snapeda_3d/SMBJ15A.step",
        mpn="SMBJ15A", mfr="Littelfuse", ds="https://www.littelfuse.com/assetdocs/tvs-diodes-smbj-datasheet",
        desc="15 V standoff unidirectional TVS, SMB (pin 1 = K)", ref="D"),
    "7447789004": dict(
        src=("WE-PD_7447789004/WE-PD_7332R.kicad_sym", "WE-PD_7332R"),
        fp="WE-PD_7332R", fp_src="WE-PD_7447789004/WE-PD_7332R.kicad_mod",
        model="WE-PD_7447789004/WE-PD_7332R.step",
        mpn="7447789004", mfr="Wurth Elektronik", ds="https://www.we-online.com/catalog/datasheet/7447789004.pdf",
        desc="WE-PD 7332 power inductor (verify 4.7 uH / Isat >= 3 A)", value="4.7uH"),
    "0ZCJ0100FF2E": dict(
        src=("fuse_0ZCJ0100FF2E/0ZCJ0100FF2E.kicad_sym", "0ZCJ0100FF2E"),
        fp="RESC3216X125N", fp_src="fuse_0ZCJ0100FF2E/RESC3216X125N.kicad_mod",
        model="fuse_0ZCJ0100FF2E/0ZCJ0100FF2E.step",
        mpn="0ZCJ0100FF2E", mfr="Bel Fuse", ds="https://www.belfuse.com/media/datasheets/products/circuit-protection/ds-CP-0zcj-series.pdf",
        desc="PTC resettable fuse 1 A hold, 1206", ref="F"),
    "NCP18XH103F03RB": dict(
        src=("snapeda_symbols/NCP18XH103F03RB.kicad_sym", "NCP18XH103F03RB"),
        fp="THRMC1608X95N", fp_src="snapeda_footprints/THRMC1608X95N.kicad_mod",
        model="snapeda_3d/NCP18XH103F03RB.step",
        mpn="NCP18XH103F03RB", mfr="Murata", ds="https://www.murata.com/en-us/products/productdetail?partno=NCP18XH103F03RB",
        desc="NTC 10 kOhm B=3380 K, 0603", ref="TH"),
}

# TPS2553DBV: no symbol exists in the downloads or in KiCad 10. Drawn here from the
# TPS2553 datasheet (SLVS841F) section 6, DBV package: 1 IN, 2 GND, 3 EN (active high),
# 4 FAULT (open drain, active low), 5 ILIM, 6 OUT.
TPS2553_PINS = [  # number, name, type, x, y, angle
    ("1", "IN", "power_in", -10.16, 2.54, 0),
    ("3", "EN", "input", -10.16, -2.54, 0),
    ("6", "OUT", "power_out", 10.16, 2.54, 180),
    ("4", "~{FAULT}", "open_collector", 10.16, 0, 180),
    ("5", "ILIM", "passive", 10.16, -2.54, 180),
    ("2", "GND", "power_in", 0, -7.62, 90),
]


def load_symbol(rel, name):
    lib = parse((DL / rel).read_text(encoding="utf-8"))
    for s in children(lib, "symbol"):
        if s[1] == name:
            return s
    raise SystemExit(f"{name} not found in {rel}")


def load_kicad_symbol(lib_id):
    lib, name = lib_id.split(":")
    tree = parse((KICAD_SYM / f"{lib}.kicad_sym").read_text(encoding="utf-8"))
    return {s[1]: s for s in children(tree, "symbol")}[name]


def rename_symbol(sym, new):
    old = str(sym[1])
    sym[1] = Q(new)
    for sub in children(sym, "symbol"):
        if str(sub[1]).startswith(old + "_"):
            sub[1] = Q(new + str(sub[1])[len(old):])


def tps2553_symbol():
    pins = []
    for num, name, typ, x, y, ang in TPS2553_PINS:
        pins.append(["pin", typ, "line", ["at", str(x), str(y), str(ang)], ["length", "2.54"],
                     ["name", Q(name), ["effects", ["font", ["size", "1.27", "1.27"]]]],
                     ["number", Q(num), ["effects", ["font", ["size", "1.27", "1.27"]]]]])
    body = ["symbol", Q("TPS2553DBVR_0_1"),
            ["rectangle", ["start", "-7.62", "5.08"], ["end", "7.62", "-5.08"],
             ["stroke", ["width", "0.254"], ["type", "default"]], ["fill", ["type", "background"]]]]
    return ["symbol", Q("TPS2553DBVR"), ["exclude_from_sim", "no"], ["in_bom", "yes"], ["on_board", "yes"],
            ["property", Q("Reference"), Q("U"), ["at", "0", "7.62", "0"], ["effects", ["font", ["size", "1.27", "1.27"]]]],
            ["property", Q("Value"), Q("TPS2553DBVR"), ["at", "0", "-10.16", "0"], ["effects", ["font", ["size", "1.27", "1.27"]]]],
            body, ["symbol", Q("TPS2553DBVR_1_1")] + pins]


def fix_footprint(src, name, model, pad_renumber):
    tree = parse(src.read_text(encoding="utf-8"))
    if tree[0] == "module":  # KiCad 5/6 keyword
        tree[0] = "footprint"
    tree[1] = Q(name)
    for pad in children(tree, "pad"):
        if str(pad[1]) in (pad_renumber or {}):
            pad[1] = Q(pad_renumber[str(pad[1])])
    for m in children(tree, "model"):
        tree.remove(m)
    if model:
        tree.append(["model", Q("${KIPRJMOD}/libs/3d/" + model),
                     ["offset", ["xyz", "0", "0", "0"]], ["scale", ["xyz", "1", "1", "1"]],
                     ["rotate", ["xyz", "0", "0", "0"]]])
    (FP_OUT / f"{name}.kicad_mod").write_text(dump(tree) + "\n", encoding="utf-8")


def main():
    for d in (FP_OUT, MODEL_OUT, SYM_OUT.parent):
        d.mkdir(parents=True, exist_ok=True)
    for f in FP_OUT.glob("*.kicad_mod"):
        f.unlink()

    lib = ["kicad_symbol_lib", ["version", "20211014"], ["generator", "consolidate_libs.py"]]
    for name, p in PARTS.items():
        src_file, src_name = p["src"]
        sym = load_kicad_symbol(src_name) if src_file == "kicad" else load_symbol(src_file, src_name)
        rename_symbol(sym, name)
        for pin in walk(sym, "pin"):
            num = child(pin, "number")
            if num and str(num[1]) in p.get("pin_names", {}):
                child(pin, "name")[1] = Q(p["pin_names"][str(num[1])])
            nm = str(child(pin, "name")[1])
            for pat, typ in p.get("pin_types", {}).items():
                if nm == pat or (pat.endswith("*") and nm.startswith(pat[:-1])):
                    pin[1] = typ
        if "ref" in p:
            set_prop(sym, "Reference", p["ref"], hide=False)
        set_prop(sym, "Value", p.get("value", name), hide=False)
        fp = p["fp"] if ":" in p["fp"] else "EPS_Footprints:" + p["fp"]
        set_prop(sym, "Footprint", fp)
        set_prop(sym, "Datasheet", p["ds"])
        set_prop(sym, "Description", p["desc"])
        set_prop(sym, "MPN", p["mpn"])
        set_prop(sym, "Manufacturer", p["mfr"])
        lib.append(sym)

        model = p.get("model")
        model_name = None
        if isinstance(model, tuple):
            model_name = Path(model[1]).name
            shutil.copy2(KICAD_3D / model[1], MODEL_OUT / model_name)
        elif model:
            model_name = Path(model).name
            shutil.copy2(DL / model, MODEL_OUT / model_name)
        if ":" not in p["fp"]:
            fix_footprint(DL / p["fp_src"], p["fp"], model_name, p.get("pad_renumber"))

    tps = tps2553_symbol()
    for k, v in (("Footprint", "Package_TO_SOT_SMD:SOT-23-6"), ("Datasheet", DS + "TPS2553.pdf"),
                 ("Description", "Current-limited load switch, EN active high, auto-retry, SOT-23-6"),
                 ("MPN", "TPS2553DBVR"), ("Manufacturer", TI)):
        set_prop(tps, k, v)
    lib.append(tps)

    SYM_OUT.write_text(dump(lib) + "\n", encoding="utf-8")

    # Normalize both libraries to the installed KiCad's file format.
    subprocess.run([str(KICAD_CLI), "sym", "upgrade", "--force", str(SYM_OUT)], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run([str(KICAD_CLI), "fp", "upgrade", "--force", str(FP_OUT)], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # `fp upgrade` gives old vendor footprints random UUIDs; make them stable so re-runs don't churn git.
    for f in sorted(FP_OUT.glob("*.kicad_mod")):
        n = iter(range(10**6))
        f.write_text(re.sub(r'\(uuid "[0-9a-f-]+"\)', lambda m: f'(uuid "{new_uuid(f"{f.name}/{next(n)}")}")',
                            f.read_text(encoding="utf-8")), encoding="utf-8")

    (ROOT / "sym-lib-table").write_text(
        '(sym_lib_table\n\t(version 7)\n\t(lib (name "EPS_Symbols")(type "KiCad")'
        '(uri "${KIPRJMOD}/libs/symbols/EPS_Symbols.kicad_sym")(options "")(descr "LOBOSAT EPS parts"))\n)\n')
    (ROOT / "fp-lib-table").write_text(
        '(fp_lib_table\n\t(version 7)\n\t(lib (name "EPS_Footprints")(type "KiCad")'
        '(uri "${KIPRJMOD}/libs/footprints/EPS_Footprints.pretty")(options "")(descr "LOBOSAT EPS footprints"))\n)\n')
    print(f"{len(PARTS) + 1} symbols -> {SYM_OUT.relative_to(ROOT)}; "
          f"{len(list(FP_OUT.glob('*.kicad_mod')))} footprints; {len(list(MODEL_OUT.glob('*')))} 3D models")


if __name__ == "__main__":
    main()
