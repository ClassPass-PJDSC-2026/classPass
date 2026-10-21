Add these three pieces to docs/assumptions.md if you added the two near-field parameters to params.yaml.

## 1. Two rows at the end of the parameter table (after the `robustness_threshold` row)

| `near_field_multiplier` | 3 | 0–10 | factor | team assumption (heuristic) | low |
| `near_field_decay_m` | 1.5 | 0.5–3 | m | team assumption (heuristic) | low |

## 2. One paragraph in "Why each value" (before the `attack_rate_threshold, robustness_threshold` paragraph)

**`near_field_multiplier`, `near_field_decay_m`.** Used only by the seat map (ticket #26). The model adds extra risk for students sitting close to an infected student: the risk from the well-mixed room is multiplied by 1 + multiplier × exp(−distance / decay distance). Both numbers are team heuristics with no empirical validation and no source. Setting the multiplier to 0 gives the plain well-mixed model, in which every other student has the same risk. They do not affect the Results, Compare or Sensitivity tabs.

## 3. Two lines at the end of the "Low-confidence parameters" list

- `near_field_multiplier`: heuristic with no empirical validation; seat map only.
- `near_field_decay_m`: heuristic with no empirical validation; seat map only.
