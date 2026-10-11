# Results

Output directory of the experiment scripts (override with the environment variable
`MEMSTUDY_RESULTS`).

| File | Written by | Content |
|---|---|---|
| `runs.jsonl` | `experiments/run_study.py` | one JSON object per line and per run (710 runs) |
| `tuned_eta.json` | `experiments/run_study.py` | the selected strength `eta`, the failure budget and the validation means |
| `summary.json` | `experiments/analyze.py` | paired comparisons, repeatability indices and their relation |
| `threshold_eval.json`, `threshold_eval.txt` | `experiments/threshold_eval.py` | the skill threshold in-sample, with one environment or one group of environments held out, and on the 12 ns-3 configurations with the threshold fixed |
| `logs/<id>.npz` | `experiments/run_study.py` | event log of every logged control run; not in the repository (see below) |
| `smoke/` | `experiments/run_study.py smoke` | output of the smoke test; not in the repository |

## `runs.jsonl`

Each line holds the metrics returned by `hosim.simulator.simulate` and the description of the job.

| Field | Meaning |
|---|---|
| `id` | unique name of the run: block, environment, profile, `phi`, `d_c`, seed, run length, warm-up, rule and its parameters |
| `block` | experiment block: `tune`, `ref`, `prof`, `warm`, `res`, `eta`, `sweep` |
| `kind`, `policy` | `A3` (control) or `Mem` (memory rule); name of the rule |
| `hyst`, `ttt` | hysteresis [dB] and time-to-trigger [s] |
| `eta`, `res`, `key` | memory rule only: strength [dB], bin size [m] (40 if absent), kind of place (`bin` if absent, or `route`) |
| `env`, `profile`, `users`, `seed` | layout, mobility profile, number of users, seed |
| `T`, `warm` | length of the test run and of the warm-up [s] |
| `phi`, `d_corr` | shared share of the shadowing variance and decorrelation distance [m] |
| `HO`, `classified`, `unnecessary`, `failed` | counts: handovers, handovers with an outcome label, unnecessary ones, failures |
| `HO_pm`, `UHO_pm`, `fail_pm` | handovers, unnecessary handovers and mobility failures per user-minute |
| `UHR` | unnecessary share of the classified handovers |
| `satisf`, `thr_mbps`, `outage_pct`, `sinr_db` | delivered over demanded rate, mean throughput, outage, mean serving SINR |
| `n_events` | number of records in the event log (logged runs only) |
| `secs`, `dec_us` | run time [s] and decision time per user and step [microseconds]; not reproducible |

The remaining fields are further metrics of the simulator: `HOF_rate` (failed share of the
classified handovers), `RLF_pm` (radio-link failures per user-minute), `PP_rate` (ping-pong
share of the handovers), `interrupt_pct` (time lost to handover interruptions), `satisf_p5`
(5th percentile of the per-user delivered/demanded rate), `rsrp_dbm`, `sig_pm` (signalling
messages per user-minute), `dwell_s` (mean time in the target), `mean_load`, `sat_cell_pct`
(share of cell-steps with more demand than capacity), `c_pp` / `c_short` / `c_gain`
(unnecessary handovers by cause: ping-pong, short stay, no quality gain), `rescue` (handovers
that look unnecessary but whose source cell would have failed), `censored` (handovers cut by
the end of the run), `UHR_noguard` / `UHR_and` / `UHR_dwell` / `UHR_legacy` (the unnecessary
share under alternative definitions) and, per service class, `UHR_<service>`,
`HOn_<service>` and `sat_<service>`.

## `tuned_eta.json`

`eta`: the selected strength [dB]. `budget`: the failure budget, the mobility-failure rate of
A3 with 3 dB and 0.3 s on the validation runs. `candidates`: for every candidate strength the
validation means `[UHO_pm, fail_pm]`. `control`: the same pair for the control.

## `summary.json`

| Key | Content |
|---|---|
| `eta`, `kappa`, `tune` | selected strength, pseudo-observations of the skill table, validation table |
| `profiles` | per mobility profile (reference environment, six seeds): comparison and indices |
| `sweep` | per profile, `phi` and `d_c` (three seeds; the name of an entry is these three joined by a vertical bar, e.g. street, 0.5, 25.0): comparison and indices |
| `warm`, `res`, `eta_curve` | per profile and value (joined in the same way): comparison for each warm-up length, bin size / `route`, strength |
| `res_rep`, `time_rep` | per profile and value: indices for each bin size / `route`, and for a log cut at 60 to 720 s |
| `predict` | rank and linear correlation between each index and the change of the unnecessary handovers (`spearman_uho`, `pearson_uho`) and of the failures (`spearman_fail`); the best threshold on `skill` and its accuracy; the correlation of `law` with `skill`; the linear fit of the change on `skill` |

A *comparison* has, for each of `UHO_pm`, `fail_pm`, `satisf`, `HO_pm` and `UHR`: `ctrl` and
`mem` (mean, half-width `ci` of the 95 % confidence interval, number of seeds `n`), `rel`
(relative change of the mean in per cent, memory against control), `diff` (mean paired
difference), `rel_seed` (relative change per seed), `same_sign` (number of seeds on the
majority side) and `p` (Wilcoxon signed-rank test; `null` with fewer than five seeds).

The *indices* are under `rep`, each as mean, `ci` and `n` over seeds: `rho`, `n`, `skill`,
`law`, `half` (see `memstudy/repeatability.py`), `rho_un` and `rho_true` (the intraclass
correlation of the indicator "unnecessary" with the observable and with the evaluation
label), `groups`, `events`, `ev_pm`, `share_un`, `share_early`, `share_late` and `agree`.
A value that cannot be estimated is written as `NaN` (the split-half correlation of the
60 s log on the street grid).

## Event logs

`logs/<id>.npz` holds `ev` (one row per event, columns `hosim.simulator.LOG_COLUMNS`: time,
user, x, y, heading, source cell, target cell, evaluation outcome, observable outcome, dwell
time, service), `box` (xmin, xmax, ymin, ymax of the area [m]), `M` (cells), `U` (users) and
`T` (run length [s]). Outcomes: 0 useful, 1 unnecessary, 2 failed after the handover (too
early), 3 too late.

The 348 logs take about 120 MB and are not stored in the repository. `analyze.py` reads the
174 logs of the 720 s control runs; `python experiments/run_study.py logs` re-creates them
(`logs all`: also those of the 240 s control runs).
