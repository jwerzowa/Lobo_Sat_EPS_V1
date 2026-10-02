# LOBOSAT EPS Board

Design of the power board for LOBOSAT, the UNM Student Satellite Group's 1U cubesat. It will be one of three boards in the stack.

Goal: solar-powered, solderability (Hand solder and hotplate), provide 3V3 and 5V, provide telemtry data that can be downlinked on the health status of the EPS system.

## What it does

- Takes power from 12x Anysolar SM141K10TF solar cells
- Charges a LG MJ1 18650 pack through an LT3652 MPPT charger (2S2P)
- Protects the battery with S-8252 and the BQ29209
- Regulates the battery bus down to two separate rails using LMZM33602 buck modules: 3V3 and 5V.
- Reports battery/solar current and temp using the INA228
- Has an RBF switch (SS-5GL), which is mandated for cubesats in orbit, will need to work on chassis column depression switch for deployment in orbit.

## Status

Actively working through the schematic in KiCad. Solar + LT3652 + MPPT dividers + protection passives are basically done. Actice work on the battery protect ICs and power conversion 

## Parts list

Full BOM will live in the spreadsheet in this repo: links, prices, and my own notes on component purpose/use.

## Notes to future me
