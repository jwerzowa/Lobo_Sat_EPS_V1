# LOBOSAT EPS Board

Design of the power board for LOBOSAT, the UNM Student Satellite Group's 1U cubesat. It will be one of three boards in the stack.

Goal: solar-powered, solderability (Hand solder and hotplate), provide 3V3 and 5V, provide telemtry data that can be downlinked on the health status of the EPS system.

## What it does

- Takes power from 12x Anysolar SM141K10TF solar cells
- Charges a LG MJ1 18650 pack through an LT3652 MPPT charger (currently 1S2P, but will likely move to (2S2P)
- Protects the battery with a DW01A + FS8205A (Battery Protection IC, Mosfet, MCU guided by EPS telemetry)
- Regulates the battery bus down to two separate rails using LMZM33602 buck modules: 3V3 and 5V.
- Reports battery/solar current and temp back over I2C
- Has an RBF switch (SS-5GL), which is mandated for cubesats in orbit, will need to work on chassis column depression switch for deployment in orbit.

## Status

Actively working through the schematic in KiCad. Charger stage (LT3652 + MPPT dividers + protection passives) is basically done, just cleaning up a few net labels and double-checking component values and orientations. Will likely need to change out components from our BOM given the schematic. 

## Parts list

Full BOM will live in the spreadsheet in this repo: links, prices, and my own notes on component purpose/use.

## Notes to future me
