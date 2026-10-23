# 06 — Open questions (do NOT decide these)

Place the parts, set Value = `TBD` where relevant, and list each one in your phase summary.
Julien decides these.

| # | Question | Affects | Why it's open |
|---|---|---|---|
| 1 | ~~Rail A and Rail B voltages~~ **Decided 2026-10-23: A = 3.3 V, B = 5 V.** Still open: which subsystem on which rail | Load switch inputs | Subsystem power needs not final |
| 2 | Solar string configuration (cells in series/parallel) | VIN_REG divider, SMBJ15A suitability, SS34 count | String Vmp must sit above 8.4 V + LT3652 headroom |
| 3 | VIN_REG divider values | Charger | Depends on #2. Old 143k/100k is for 1S |
| 4 | Main fuse rating and PTC hold current | Battery protection | 0ZCJ0100 (1 A hold) may be too low for the bus |
| 5 | TPS2553 current limits (ILIM resistors) | Load switches | Depends on each subsystem's peak current |
| 6 | Heater fitted or not | Heater sheet (all DNP for now) | Depends on mission thermal environment |
| 7 | Number of launch inhibits | Launch inhibit | Set by the launch provider's interface document |
| 8 | Connector types (solar in, outputs, MCU interface) | J parts | Not chosen; use generic Conn_01xNN placeholders |
| 9 | BQ29209 OUT → LT3652 SHDN inverter part | Charger / battery | Small N-FET or NPN; Julien to approve the part |
| 11 | LT3652 TIMER cap, SHDN pull-up, boost cap value | Charger | LT3652 datasheet not in `datasheets/` yet |
| 12 | INA228 shunt value (10 mΩ proposed) | Battery | Depends on max pack current / fuse rating (#4) |
| 10 | Keystone clip exact MPN | Battery | Use whatever is in the library; report the MPN found |
