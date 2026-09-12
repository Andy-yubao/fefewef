# T4 action-log analysis

- Source: `task4/outputs/official-run.json`
- Strategy: `geometry_early_optical_clear_probe`
- Actions: 534 (534 accepted)
- Measurement positions: 37
- Measurements: 520
- `no_signal`: 489 (94.04%)
- `direction`: 31
- `near`: 0
- Clears: 11/12
- First clear action: 102
- Last measurement action: 532
- All clears after the last measurement: False
- No-signal measurements spent on channels that were eventually discovered: 174

## Per-channel measurements

| Channel | Measures | No signal | Direction | Near | First signal virtual time (s) |
|---:|---:|---:|---:|---:|---:|
| 1 | 16 | 14 | 2 | 0 | 5 |
| 2 | 35 | 35 | 0 | 0 | - |
| 3 | 19 | 16 | 3 | 0 | 3044.297476 |
| 4 | 20 | 18 | 2 | 0 | 4404.828329 |
| 5 | 17 | 15 | 2 | 0 | 360.2 |
| 6 | 37 | 34 | 3 | 0 | 1543.097476 |
| 7 | 14 | 11 | 3 | 0 | 2845.097476 |
| 8 | 35 | 35 | 0 | 0 | - |
| 9 | 21 | 18 | 3 | 0 | 336.2 |
| 10 | 35 | 35 | 0 | 0 | - |
| 11 | 5 | 2 | 3 | 0 | 65 |
| 12 | 35 | 35 | 0 | 0 | - |
| 13 | 35 | 35 | 0 | 0 | - |
| 14 | 35 | 35 | 0 | 0 | - |
| 15 | 18 | 15 | 3 | 0 | 89 |
| 16 | 33 | 30 | 3 | 0 | 8017.602639 |
| 17 | 5 | 1 | 4 | 0 | 288.2 |
| 18 | 35 | 35 | 0 | 0 | - |
| 19 | 35 | 35 | 0 | 0 | - |
| 20 | 35 | 35 | 0 | 0 | - |

## Interpretation boundary

This report uses only robot-visible request/response logs. It does not infer the hidden true emitter count, source positions, radii, types, or directions.
