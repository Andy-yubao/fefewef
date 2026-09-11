# Candidate 020 Route Diagnosis

This read-only diagnosis uses the 10 `candidate_020_grid5_center_approach` records for seeds `321100`--`321109` in `paired_020_vs_champion_visual_10.jsonl.gz`. No new experiment was run.

## Coverage-forced

- Total `coverage_forced` decisions: **0**.
- Mean per case: **0.0**.
- Worst seeds: none; all 10 seeds have zero occurrences.
- Consequently, forced-coverage movement distance has no observations: **mean / median / max are not applicable**, rather than zero-distance measurements.
- The logs do not preserve a complete historical `FOUND` snapshot at every decision, so such state cannot be reconstructed reliably; with no `coverage_forced` decisions, that limitation does not affect the count above.

## Early pass then return

A successful clear is counted when an earlier route point was within **300 m** of its true source, the route subsequently left the 300 m neighborhood, and the robot later returned to clear it. Route points are one-based and include the origin as point 1. This is a proximity diagnostic only; it does not prove that the earlier point supported a useful bearing measurement or clear.

| Seed | `coverage_forced` | Early-pass count | Events: `channel: first distance m @ first point -> clear point` |
|---:|---:|---:|---|
| 321100 | 0 | 4 | `10:272.1@9->19`; `16:22.0@6->31`; `5:77.1@1->34`; `9:275.1@3->37` |
| 321101 | 0 | 2 | `16:85.7@3->29`; `11:180.6@5->71` |
| 321102 | 0 | 2 | `6:208.5@4->31`; `14:64.4@1->34` |
| 321103 | 0 | 2 | `15:166.7@1->10`; `16:191.5@3->22` |
| 321104 | 0 | 3 | `18:299.5@1->11`; `6:237.1@4->29`; `12:219.4@4->31` |
| 321105 | 0 | 3 | `14:290.7@21->24`; `19:156.1@4->33`; `7:114.3@6->43` |
| 321106 | 0 | 7 | `12:246.3@2->12`; `13:46.5@3->13`; `7:275.6@3->15`; `18:211.0@6->53`; `3:224.5@6->55`; `15:277.9@6->58`; `8:152.3@8->64` |
| 321107 | 0 | 1 | `6:281.0@12->17` |
| 321108 | 0 | 5 | `15:227.4@1->24`; `7:62.1@6->32`; `19:96.7@7->33`; `5:270.6@2->34`; `10:127.8@2->39` |
| 321109 | 0 | 4 | `19:187.0@7->24`; `13:180.2@4->31`; `9:99.6@4->32`; `1:292.7@4->34` |

- Total: **33** early-pass-then-return events.
- Mean per case: **3.3**.
- Representative high-count seeds: `321106` (7) and `321108` (5).

## Conclusion

`coverage_forced` is absent in this sample, so there is no evidence here that `local_action_limit=3` is causing the observed turnarounds or long forced moves. Early-pass-then-return behavior is common (33 events across all 10 cases), including several cases where the route later moves far away before clearing the nearby source. Under this deliberately simple proximity test, the evidence therefore supports **B: insufficient opportunistic detection/use of nearby sources** more than A. Coverage order may still shape the large-scale route, but the present logs and this lightweight test do not isolate that effect.
