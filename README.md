# When Is Handover History Worth Remembering?

Code and results of the paper *"When Is Handover History Worth Remembering? Repeatability of
Handover Outcomes in Dense 5G Networks"* by Mostafa Jalili Sanjarani, Yasser Elmi Sola,
Hesam Hasanpour and Ali Akbar Neghabi (Islamic Azad University, Sabzevar).

## What the study asks

Many handover schemes keep a memory of what earlier handovers led to and adjust the next
decision with it. They all assume that the outcome of a handover at a place says something
about the next handover at that place. The study measures when this holds:

- in which environments does a per-place memory of handover outcomes help an Event-A3 rule,
  and in which does it hurt;
- can this be told in advance, from the logs of ordinary A3 operation, before any memory is
  deployed.

The repository contains

- a **load-coupled system-level simulator** (`hosim/`) whose shadowing has a controllable
  share that is common to all users;
- a **minimal memory rule** (`memstudy/rule.py`): Event A3 whose hysteresis is shifted per
  place and per target cell by past outcomes, and whose control is the identical A3 rule;
- a **repeatability index** computed from an event log (`memstudy/repeatability.py`);
- the experiment, analysis and figure scripts, the results of all 710 runs and the figures.

## Shadowing model

The slow shadowing between a user and a cell is the sum of three parts:

| Part | Standard deviation | Behaviour |
|---|---|---|
| shared | `sigma_s` | a static, spatially correlated field per cell: every user at the same place sees the same value |
| private | `sigma_p` | a first-order process along each user's own path (correlation `exp(-distance / d_c)`), independent between users |
| fast | 1.5 dB | temporal component with a correlation time of 1 s |

The total slow variance is fixed, `sigma_s^2 + sigma_p^2 = (4 dB)^2`, and split by the
**shared share**

```
phi = sigma_s^2 / (sigma_s^2 + sigma_p^2)
```

With `phi = 1` everything is shared: what happened to one user at a place will happen to the
next. With `phi = 0` nothing is shared. Both parts use the same decorrelation distance `d_c`
and the same inter-site correlation (0.5); blockage-prone cells scale all three parts by 1.5.
The propagation sweep covers `phi` = 1, 0.75, 0.5, 0.25, 0 and `d_c` = 12.5, 25, 50, 100,
200 m; `phi = 1`, `d_c = 50 m` is the *reference environment*. In the code the split is
`shadow(phi, d_corr)` in `experiments/common.py`; the two standard deviations are
`SimParams.shadow_sigma` and `SimParams.sigma_p` in `hosim/simulator.py`.

## The memory rule and its control

`MemA3` is 3GPP Event A3 with one extra term in the hysteresis:

```
margin(place, target) = h + eta * (risk(place, target) - mean risk),   clipped to [0, 9] dB
risk = P(unnecessary) + P(early failure) - P(too late)
```

- A *place* is a 40 m location bin (other bin sizes and "one place per serving cell" are
  part of the experiments); the memory is a table of outcome counts per (place, target cell).
- The four outcomes are the ones a network can observe: useful, unnecessary, failed shortly
  after the handover (too early), link lost before a handover completed (too late).
- The probabilities are estimated from the counts, shrunk towards the network-wide shares
  with 3 pseudo-observations, so a place without history gets the plain hysteresis `h`.
  Counts are forgotten with a time constant of 600 s.
- `mean risk` is the same expression for the network-wide shares; subtracting it makes the
  shift zero on average, so the rule does not simply raise or lower the hysteresis everywhere.

**Control.** With `eta = 0` the rule is exactly A3 with hysteresis `h` and the same
time-to-trigger. Every comparison is between `MemA3` and A3 with `h` = 4 dB and
time-to-trigger 0.1 s (an A3 setting tuned for this layout in preliminary runs) on the same
trajectories, services and shadowing. The memory rule is warmed up for 240 s on independent
traces of the same environment before each test run. The strength `eta` is chosen once, on
validation seeds: among the candidates 2, 4, 8, 12, 16, 24 dB whose mobility-failure rate
does not exceed that of A3 with 3 dB and 0.3 s, the one with the fewest unnecessary
handovers (`results/tuned_eta.json`: 24 dB).

## The repeatability index

A long control run (A3, 720 s) writes an event log: one record per classified handover and
per too-late failure, with the position where it was decided. Each event gets a risk score
`z` (+1 unnecessary or too early, 0 useful, -1 too late) and is assigned to its place.
From the log alone, `memstudy/repeatability.py` computes

| Name | Meaning |
|---|---|
| `rho` | intraclass correlation of `z` over places: the share of the outcome variance that belongs to the place |
| `n` | events per visited place: how much evidence a place collects |
| `skill` | prequential skill of an outcome table: every event is predicted from the earlier events of its place; 1 - MSE(table) / MSE(running overall mean) |
| `half` | split-half correlation: mean `z` per place seen by the even-numbered users against the odd-numbered users |
| `law` | `rho` times the mean of `m / (m + (1 - rho) / rho)`, with `m` the earlier events in the place: the skill expected from `rho` and `n` alone |

No memory rule is involved in these numbers.

## Repository layout

```
hosim/                      the system-level simulator
  simulator.py              SimParams, RadioEnv, gen_traj, assign_services, simulate
  policies.py               Base (interface of a decision rule) and A3
  radiomap.py               RadioMap: cell positions and path-loss fits from a drive-test table
  mobility.py               the five mobility profiles
  services.py               the five 5QI service classes
memstudy/                   the memory rule and the index
  rule.py                   MemA3: Event A3 with a per-place outcome memory
  repeatability.py          repeatability indices from an event log
experiments/
  common.py                 paths, radio environment, shadowing split, scenario()
  run_study.py              job list and resumable runner       -> results/runs.jsonl, tuned_eta.json, logs/
  analyze.py                statistics and indices              -> results/summary.json
  make_figures.py           the figures of the paper            -> figures/fig_*.pdf (also .png)
  plotstyle.py              matplotlib style
examples/quickstart.py      small A3-versus-memory demo with the parameters at the top of the file
data/synthetic/             the 40-cell synthetic layout (UDN-40)
results/                    result files (see results/README.md)
figures/                    figures
docs/                       additional documentation
run_all.sh                  the full pipeline
```

A Persian guide for readers with little programming experience is in docs/ (`docs/CODE_GUIDE.md`,
and the same content as a single page in `docs/code_guide.html`).

## Installation

Python 3.10 or newer.

```
git clone https://github.com/mjs19971997/handover-memory-study.git
cd handover-memory-study
pip install -r requirements.txt
```

`requirements.txt` pins the versions the experiments were run with (Python 3.12). The scripts
are run from a checkout; nothing needs to be installed as a package.

## Smoke test and quick start

```
python experiments/run_study.py smoke
```

runs four jobs of 30 s through the whole chain (simulator, both rules, private shadowing,
event log, index) and ends with `smoke test passed`. It takes about a minute and writes only
to `results/smoke/`. One of its checks is that the memory rule with `eta = 0` gives the same
numbers as the control.

```
python examples/quickstart.py
```

compares A3 and the memory rule on one small scenario and prints the index of the control
run. The scenario (mobility profile, users, `phi`, `d_c`, `eta`, ...) is set by constants at
the top of the file.

## Reproducing the paper

```
python experiments/run_study.py            # results/runs.jsonl, tuned_eta.json, logs/*.npz
python experiments/analyze.py              # results/summary.json
python experiments/make_figures.py         # figures/fig_*.pdf (also .png)
```

`bash run_all.sh` runs these steps in a row (and re-creates missing event logs before the analysis).

- **Resumable.** Every finished run is appended to `results/runs.jsonl` at once; a repeated
  call runs only what is missing. With the result files of this repository in place,
  `run_study.py` therefore has nothing to do. To repeat the study from scratch, set
  `MEMSTUDY_RESULTS` to an empty directory (or remove `results/runs.jsonl`).
  `python experiments/run_study.py status` shows what is done.
- **Run time.** The study has 710 runs (32 validation, 678 test) of 300 users each; a 240 s
  run takes one to two minutes of CPU time. All runs together took 15.4 CPU-hours, about
  2.6 hours with 6 worker processes on an 8-core machine. The analysis takes about 3 minutes,
  the figures a few seconds.
- **Event logs.** The analysis reads the event logs of the 174 long control runs
  (`results/logs/`, about 90 MB; 120 MB with the logs of the short control runs). They are
  too large for the repository and are not included. `results/summary.json` is included, so
  the figures can be drawn without them. To run the analysis, re-create the logs with

  ```
  python experiments/run_study.py logs
  ```

  This repeats the 174 long control runs (5.6 CPU-hours, about an hour with 6 worker
  processes), writes their logs and checks every repeated run against its row in
  `runs.jsonl`. Without the logs `analyze.py` stops with a message that says so.
- **Workers**: all cores but one by default; set `MEMSTUDY_PROCS` to change it.
- **Output directory**: `results/`, or the directory named by `MEMSTUDY_RESULTS`.
- **Determinism**: all random streams are seeded, and both rules of a (scenario, seed) pair
  see the same trajectories, services and shadowing. For a given set of library versions the
  results are reproducible exactly; the only non-deterministic columns are `secs` (run time)
  and `dec_us` (decision time). The shadowing field, the hotspot cells and the
  blockage-prone cells are drawn anew for every seed.

## Main results

Reference environment (`phi = 1`, `d_c = 50 m`), 40-cell layout, 300 users, test seeds 1–6.
Rates are per user-minute; `n`, `rho` and `skill` come from the control logs. Produced by
`experiments/analyze.py` (`results/summary.json`, key `profiles`).

| Mobility | Unnecessary HO, A3 | Unnecessary HO, memory | Change | Failures, A3 | Failures, memory | Change | `n` | `rho` | `skill` |
|---|---|---|---|---|---|---|---|---|---|
| Pedestrian | 0.39 | 0.51 | +29% | 0.035 | 0.038 | +8% | 1.7 | 0.25 | 0.01 |
| Vehicular, open area | 1.44 | 1.44 | 0% | 0.32 | 0.34 | +6% | 3.4 | 0.38 | 0.06 |
| Vehicular, street grid | 1.54 | 1.21 | -21% | 0.37 | 0.37 | +1% | 5.0 | 0.39 | 0.13 |
| Highway | 3.92 | 1.39 | -65% | 0.67 | 0.65 | -3% | 33.0 | 0.43 | 0.37 |
| High-speed train | 8.01 | 5.93 | -26% | 1.05 | 1.43 | +37% | 145.6 | 0.41 | 0.38 |

Over the propagation sweep (key `sweep`) the change of the unnecessary handovers goes from
-38% to +49% on the street grid and from -66% to -6% on the highway. Across the 53
environments (25 propagation settings on the street grid, 25 on the highway, and the three
other profiles) the Spearman rank correlation between an index of the control log and the
change of the unnecessary handovers is -0.10 for `rho`, -0.95 for `n`, -0.92 for `skill` and
-0.93 for `half`; a threshold of 0.03 on `skill` separates gain from loss in 91% of the
environments (key `predict`). The paper discusses these results and their limits.

The figures, in the order of the paper:

| File | Content |
|---|---|
| `figures/fig_profiles.pdf` | the five mobility profiles: unnecessary handovers, failures, and the indices of the control runs |
| `figures/fig_sweep.pdf` | change of unnecessary handovers and of failures over the propagation sweep |
| `figures/fig_index.pdf` | `rho`, events per place and `skill` over the propagation sweep |
| `figures/fig_predict.pdf` | change of unnecessary handovers against `rho`, `n` and `skill`, one point per environment |
| `figures/fig_curves.pdf` | length of the warm-up, length of the log, bin size and strength `eta` |

## Experiment blocks

All runs use the 40-cell layout with 300 users. A *triple* is a control run (240 s, logged),
a memory-rule run (240 s after a 240 s warm-up) and a long logged control run (720 s).

| Block | Runs | Content |
|---|---|---|
| `tune` | 32 | Validation (seeds 101, 102; street grid and highway): the control, A3 with 3 dB / 0.3 s (the failure budget) and the six candidate strengths. |
| `ref` | 36 | Reference environment: triples on the street grid and the highway, six seeds. |
| `prof` | 54 | Triples for the pedestrian, open-area vehicular and train profiles, six seeds. |
| `warm` | 36 | Memory rule with a warm-up of 0, 60 and 960 s (street grid, highway; six seeds). |
| `res` | 60 | Memory rule with bins of 10, 20, 80 and 160 m and with one place per serving cell. |
| `eta` | 60 | Memory rule with the other five strengths. |
| `sweep` | 432 | Triples for the 24 other propagation settings (`phi` x `d_c`), street grid and highway, three seeds. |

Each line of `results/runs.jsonl` is one run: the metrics returned by `simulate` and the job
description (`id`, `block`, `profile`, `seed`, `phi`, `d_corr`, `kind`, `eta`, ...).
`results/README.md` describes the result files field by field.

## Simulator model

All values are the defaults of `SimParams` in `hosim/simulator.py`.

- **Time**: all users advance together in 100 ms steps; default run length 240 s.
- **Radio map**: cell positions and a per-cell log-distance path-loss fit estimated from the
  samples of a drive-test table (`hosim/radiomap.py`); each cell has its 6 nearest cells as
  neighbours.
- **Shadowing**: as described above. The shared field has a 5 m grid; a quarter of the cells
  are blockage-prone (1.5 times the standard deviation).
- **Measurements**: L3-filtered RSRP with filter weight 0.30 per 100 ms sample.
- **SINR and load**: thermal noise -122 dBm per resource element; inter-cell interference is
  proportional to the load of the interfering cells (coupling 0.20). A quarter of the cells
  are hotspots with background load 0.55 to 0.85, the others 0.05 to 0.25. Carrier: 106 PRB
  (38.16 MHz), spectral efficiency capped at 7.4 bit/s/Hz. GBR demands are served first, the
  remainder is shared by the non-GBR users; cell load feeds back into interference.
- **Failures**: radio-link failure when the serving SINR stays below Qout = -8 dB for
  T310 = 1 s; a handover commanded while the serving SINR is below Qout fails (too late).
  Either event causes a 1 s re-establishment outage. A successful handover interrupts the
  user for 50 ms.
- **Mobility profiles** (`hosim/mobility.py`): pedestrian (0.8 to 2 m/s, random waypoint),
  urban vehicular (8 to 16 m/s, random waypoint in the open area), urban street grid (8 to
  16 m/s, 150 m blocks), highway (22 to 33 m/s, three lanes, both directions), high-speed
  train (40 to 60 m/s, all users on one track at a common speed).
- **Service classes** (`hosim/services.py`), with rate demand, T_min and theta_Q:

  | Service | 5QI | Resource type | Rate [Mbit/s] | T_min [s] | theta_Q [dB] | Share |
  |---|---|---|---|---|---|---|
  | Conversational voice | 1 | GBR | 0.1 | 4 | 0.7 | 0.20 |
  | Conversational video | 2 | GBR | 2 | 6 | 1.0 | 0.20 |
  | Real-time gaming | 3 | Delay-critical GBR | 1 | 7 | 1.2 | 0.15 |
  | Buffered streaming | 6 | Non-GBR | 5 | 3 | 1.5 | 0.30 |
  | Web / background | 9 | Non-GBR | 1 | 2 | 0.4 | 0.15 |

- **Outcome of a handover** (evaluation): observed for T_min of the user's service or until
  the user leaves the target. The handover is *failed* if the link is lost in the target
  within the window; otherwise it is *unnecessary* if the stay was shorter than T_min or the
  mean SINR gain over the source cell was below theta_Q, unless the source cell itself would
  have gone into radio-link failure. Handovers whose window is cut by the end of the run are
  not classified. The label fed back to a rule, and written to the event log as the
  observable outcome, uses only what the network can observe (dwell time, L3 measurements,
  failure events).
- **Main metrics** returned by `simulate`: `HO_pm`, `UHO_pm` (handovers and unnecessary
  handovers per user-minute), `UHR` (unnecessary share of the classified handovers),
  `fail_pm` (radio-link failures plus too-late handovers per user-minute), `outage_pct`,
  `satisf` (delivered over demanded rate), `thr_mbps`, `sinr_db`, and per-service variants.

A decision rule is a subclass of `hosim.policies.Base` that implements `decide(ctx)` and
returns, per user, the target cell or -1 to stay; the hooks `on_outcome`, `on_late` and
`after_step` report the observable outcomes back to it. `memstudy/rule.py` is a complete
example of about a hundred lines.

## Licence

- **Code and result files**: MIT licence, see `LICENSE`.
- **`data/synthetic/realistic_5G_2x.csv`**: synthetic drive-test table created by the authors,
  distributed under the same licence.

## How to cite

> M. Jalili Sanjarani, Y. Elmi Sola, H. Hasanpour, A. A. Neghabi, "When Is Handover History
> Worth Remembering? Repeatability of Handover Outcomes in Dense 5G Networks," 2026.

`CITATION.cff` holds the same entry in machine-readable form.

## Contact

Yasser Elmi Sola (corresponding author), Yasser.Elmi@iau.ac.ir
