# Validation in ns-3

The system-level simulator of this repository (`hosim/`) was written for the study, and its
shadowing model was built to have a shared part. This folder holds a check of the central
comparison in a simulator we did not write: the memory rule against the identical A3 rule in
ns-3 with the 5G-LENA NR module, where measurement reports, the Event-A3 trigger, the handover
procedure and the radio-link-failure timers run as protocol events.

| File | Content |
|---|---|
| `PLAN_MEM.md` | the plan: question, rule, design, endpoints, analyses and the expected result, written before the runs |
| `analyze_mem.py` | the analysis (Python standard library only) |
| `report_mem.txt`, `report_mem.json` | its output: repeatability of the control runs, effect against the strength `eta`, effect by time window |
| `mem_urban/results.csv`, `mem_base/results.csv` | one row per run, 180 runs each |
| `make_figure.py` | draws `figures/fig_ns3.pdf` from `report_mem.json` |
| `scenario/a3-scenario.cc` | the ns-3 scenario program (C++, built against ns-3.48 and nr v5.1): both environments, the rules `a3` and `mem`, the outcome classification |
| `scenario/run_sweep.py` | the script that starts the 360 runs |
| `scenario/build_scenario.sh`, `scenario/fix_srs.sh`, `scenario/setup/` | build of the program, the one change to the NR module, and the installation of the tool chain (see "Building and running the scenario") |

`PLAN_MEM.md` is the plan as it was written before the runs, apart from two references to the
local batch environment that were reworded. In `report_mem.txt` the local path in the second
line was replaced by a dot.

## Set-up

**Software.** ns-3 release 3.48 with the NR module of 5G-LENA, version 5.1, built with CMake
and g++. Four commits of the ns-3 development branch were added on top of release 3.48: three
that the release notes of the NR module recommend, and one that is needed to run under Windows.

**One local change to the NR module.** In the function that starts the reception of a sounding
reference signal at a gNB (`NrSpectrumPhy::StartRxSrs`), five `NS_FATAL_ERROR` calls were
turned into warnings, so that the signal is dropped and the run continues. Without this change
some runs abort after a handover, when an uplink sounding signal reaches a gNB whose receiver
is not idle. A run that had finished before the change gave identical metrics when it was
repeated with it. No other library code was changed.

**Network.** Seven gNBs, one in the centre and six around it, 40 dBm, omnidirectional, one
10 MHz carrier at 3.5 GHz, numerology 0, ideal RRC, no fast fading. Twenty users at constant
speed. Every user receives 10 downlink UDP packets of 200 bytes per second (light traffic).

**Measurements and failures.** The user measures every 200 ms; layer-3 filter coefficient 4.
Radio-link failure and handover failure follow the model of 3GPP TR 36.839: Qout −8 dB,
Qin −6 dB, N310 = N311 = 1, T310 = 1 s, handover preparation delay 50 ms; a handover command
that arrives while T310 is running is a handover failure.

**Two environments.**

| | open area (`base`) | street grid with buildings (`urban`) |
|---|---|---|
| Path loss | 3GPP TR 38.901 urban macro, no line of sight | 3GPP TR 38.901 urban micro, street canyon |
| Site height | 25 m | 10 m, on the streets |
| Line of sight | none | from geometry: a link is blocked if the straight line between site and user crosses a building |
| Shadowing | drawn by ns-3 independently for every link | the same ns-3 model, redrawn when the line-of-sight state of the link changes |
| Roads and buildings | none | road grid of 3GPP TR 37.885 (blocks of 433 m × 250 m, streets 20 m wide), 2 × 2 blocks, buildings 20 m high filling the blocks |
| Mobility | straight legs inside a disc of radius 1.3 × inter-site distance | along the street centre lines; at an intersection straight 0.5, left 0.25, right 0.25 |
| Sites | hexagonal ring at the inter-site distance | the same plan, each site moved to the nearest street, so the inter-site distance is nominal |

In the street grid blockage is a property of the place and the same for every user who passes
there. In the open area nothing but the path loss belongs to a place. The two environments
also differ in propagation model, site height and mobility, so a difference between them
cannot be attributed to blockage alone.

**Rule.** As in `memstudy/rule.py` and with the same parameters: Event A3 with hysteresis
`h` = 4 dB and time-to-trigger 100 ms; per (40 m location bin, target cell) a discounted sum
of risk scores (+1 unnecessary or too early, 0 useful, −1 too late; time constant 600 s);
3 pseudo-observations at the network-wide mean; margin = clip(`h` + `eta` × (risk of the place
− mean risk), 0, 9) dB. In ns-3 the rule uses the standard A3 measurement report and a
cell-individual offset per user and neighbour that is rewritten every measurement period; the
gNB hands over to the neighbour with the largest excess over its margin. With `eta` = 0 the
handover events of a test run were identical to those of the A3 algorithm of ns-3 with 4 dB and
100 ms. The table starts empty in every run; there is no separate warm-up run.

Three differences from the system-level simulator: the event is evaluated once per 200 ms, so
a time-to-trigger of 100 ms is a single evaluation; ns-3 gives no trace of the
signal-to-interference ratio a user would have in another cell, so the label used for
evaluation is computed from the RSRP of all seven cells, assuming that all of them transmit
(the table learns from the label a network can observe, computed from the filtered RSRP); and
neither `h`, nor the time-to-trigger, nor `eta` was tuned for ns-3.

**Design.**

| Factor | Levels |
|---|---|
| strength `eta` | 0 (control), 6, 12, 24, 36 dB; 24 dB, the value selected in the system-level study, is the primary comparison |
| environment | open area, street grid with buildings |
| configuration | nominal inter-site distance 200, 400 m × speed 8, 16, 30 m/s |
| seeds | 1 to 6; within a seed all values of `eta` see the same trajectories and random streams |
| run | 900 s, the first 60 s discarded: 280 user-minutes per run |

2 × 6 × 5 × 6 = 360 runs. All of them completed; they took about 42 hours of single-core
computing time, a little over four hours with ten runs in parallel on one desktop
machine.

## How the runs were made

One scenario program, built against the libraries above, takes the environment, the rule and
its parameters, the inter-site distance, the speed, the seed and the run length as
command-line arguments and writes one summary row, one file with every handover attempt
(time, user, source, target, position, outcome labels, margin) and one file with every
radio-link failure. A batch script started the 360 runs, a fixed number at a time, and
collected the summary rows into `results.csv`. `analyze_mem.py` then computed the report from
`results.csv` and the per-attempt files.

The scenario program and the batch script are in `scenario/` (next section). The per-attempt
files of the 360 runs (79 MB) are not in the repository; the scenario program writes them
again when the runs are repeated. Without them `analyze_mem.py` stops with a message and
leaves the reports untouched: part 2 of the report (effect against `eta`) can be recomputed
from `results.csv` alone, parts 1 and 3 cannot.

## Building and running the scenario

The folder `scenario/` holds everything needed to repeat the runs on Windows with MSYS2
(UCRT64 environment):

| File | Purpose |
|---|---|
| `a3-scenario.cc` | the scenario program: two environments (`--scen`: `base` or `urban`), rules (`--rule`: `a3` or `mem`, with `--memEta`, `--memKappa`, `--memCap`), outcome classification, one JSON line of metrics per run and the per-attempt files (`--PrintHelp` lists the options) |
| `setup/1_tools.sh` | compiler and build tools (pacman packages) |
| `setup/2_ns3.sh` | ns-3.48, the four upstream commits in `setup/patches/`, nr v5.1, the SRS change, the full build and this program |
| `fix_srs.sh` | the one local change to nr v5.1: the five aborts in `NrSpectrumPhy::StartRxSrs` become "drop this SRS" |
| `build_scenario.sh` | copies the source into `scratch/` of the ns-3 tree and builds that one program |
| `run_sweep.py` | the sweep: `eta` 0 / 6 / 12 / 24 / 36 dB x two environments x six configurations x six seeds, 900 s per run; resumable; `--status`, `--smoke` |

    cd scenario
    bash setup/1_tools.sh               # in the "MSYS2 UCRT64" shell
    bash setup/2_ns3.sh                 # long: downloads and builds ns-3 and nr
    NS3_WORKERS=24 python run_sweep.py  # 360 runs; python run_sweep.py --smoke for a short test
    python ../analyze_mem.py --root .   # report on the new runs

The scripts expect ns-3 in `C:\cl\tools\ns3\ns-3-dev` and MSYS2 in `C:\cl\tools\msys64`
(`2_ns3.sh` creates the first). For other locations set `NS3_DIR_WIN` or change `NS3` and
`DLL_PATH` at the top of `run_sweep.py`, and change the paths in the shell scripts
(`build_scenario.sh` also reads `NS3_DIR`).

New runs are written to `scenario/mem_urban/` and `scenario/mem_base/` (`results.csv`,
per-attempt and per-failure files in `res/`); the runs of the paper in `mem_urban/` and
`mem_base/` of this folder are not touched. Runs of 900 s with `eta` = 0 and 24 dB, repeated in
both environments on a second machine, gave the stored rows in every field of `results.csv` except the run time.

## Results

Rates are per user-minute; changes are against the control (`eta` = 0), paired by seed;
p-values from the exact Wilcoxon signed-rank test.

Control runs (`eta` = 0), mean of the six runs of a configuration:

| Environment | intraclass correlation | events per place | prequential skill | skill predicted from the two |
|---|---|---|---|---|
| street grid | 0.23 to 0.43 | 7.6 to 15.5 | 0.107 to 0.328 | 0.133 to 0.349 |
| open area | 0.19 to 0.28 | 1.5 to 6.6 | −0.014 to 0.063 | 0.024 to 0.170 |

Memory rule with `eta` = 24 dB, pooled over the six configurations (36 pairs):

| Environment | unnecessary handovers | change | failures |
|---|---|---|---|
| street grid | 3.909 → 2.678 | −31.5 % (p < 0.001), −7.7 % to −49.7 % by configuration | 0.009 → 0.016 (p < 0.001) |
| open area | 1.523 → 1.638 | +7.6 % (p < 0.001), −1.7 % to +38.9 % by configuration | 0.001 → 0.001 |

- The sign of the effect follows the skill of the control runs. All six street-grid
  configurations (skill 0.107 or more) have fewer unnecessary handovers in every seed. Of the
  five open-area configurations with a skill of 0.021 or less, three have more in every seed
  and two show changes that cannot be told from zero (+1.8 %, +8.3 %); the one with a skill of
  0.063 shows no change (−1.7 %).
- The table needs time to fill: on the street grid the reduction at 24 dB is 21 % in the first
  third of the measured time, 35 % in the second and 38 % in the third.
- With `eta` = 36 dB the open area gets 17.9 % more unnecessary handovers.

What does not fit, and the limits:

- Failures rise on the street grid, from 0.009 to 0.016 per user-minute at 24 dB (86 against
  165 events) and to 0.019 at 36 dB. Nearly all are handover commands that arrive too late.
- The relation between intraclass correlation, events per place and skill overestimates the
  skill in the open area (for example 0.170 predicted, 0.063 measured). The plan expected an
  intraclass correlation near zero there; it is 0.19 to 0.28.
- Six seeds per configuration: no p-value of a single configuration can be below 0.031, and
  changes of the failure rate in single configurations are not resolved.
- Light traffic: the failure detector sees little interference, so failure rates are lower
  than in a loaded network; at least 99.2 % of the packets were delivered in every run, so the
  cost of the memory in delivered rate could not be examined.
- The A3 setting was not tuned for ns-3. In the control, 47 % of the handovers on the street
  grid and 25 % in the open area are unnecessary; a control tuned for this simulator would
  leave the memory less to remove.
- Scale: 7 gNBs and 20 users. The magnitudes are not comparable with those of the system-level
  study; what carries over is the ordering by skill.

## Columns of `results.csv`

`results.csv` holds the columns of the summary rows that belong to this study.

| Columns | Meaning |
|---|---|
| `job_id`, `label`, `config`, `tag`, `phase`, `rule` | name of the run; `label` is `mem_e<eta>` |
| `scen`, `isd`, `speed`, `rngRun`, `nUe`, `simTime`, `discard`, `fading`, `traffic` | environment (`urban`, `base`), nominal inter-site distance [m], speed [m/s], seed, users, run length and discarded start [s], fast fading (0 = off), traffic mode |
| `hyst`, `ttt_ms`, `memEta` | hysteresis [dB], time-to-trigger [ms], strength `eta` [dB] |
| `prepDelay_ms`, `t310_ms`, `n310` | failure model |
| `ue_min` | measured user-minutes |
| `attempts`, `executed`, `useful`, `unnecessary`, `early`, `late`, `censored`, `unresolved`, `sum_outcomes` | handover commands and their outcomes by the evaluation label; `censored`: cut by the end of the run |
| `obs_useful`, `obs_unnecessary`, `obs_early`, `obs_late` | outcomes by the label a network can observe (the one the table learns from) |
| `pp_un`, `un_short`, `un_gain`, `pp`, `rescue` | the unnecessary handovers split into ping-pongs, short stays and small gains; all ping-pongs (back to the previous cell within 1 s); short or low-gain handovers that are not counted as unnecessary because the source link would have failed |
| `failures`, `rlf_t310`, `rlf_late_cmd`, `rlf_during_ho`, `rlf_rlc`, `rlf_no_pending`, `rlf_other`, `late_cmd`, `late_exec`, `late_other` | mobility failures and their causes |
| `ho_pm`, `uho_pm`, `fail_pm` | handovers, unnecessary handovers and failures per user-minute |
| `uhr`, `hof_rate`, `pp_ratio`, `dwell_s` | unnecessary share, failed share, ping-pong share, mean time in the target cell [s] |
| `mean_margin` | mean A3 margin at the decisions [dB] (4 for the control) |
| `tx_pkts`, `rx_pkts`, `delivery`, `sinr_db`, `los_serving`, `outage_s_pm`, `occ_slots`, `occ_prb` | packets, delivery ratio, mean serving SINR [dB], share of samples with line of sight to the serving site (−1 in the open area), outage, resource use |
| `n_<service>`, `un_<service>`, `ues_<service>`, `deliv_<service>`, `delay_ms_<service>`, `delay95_ms_<service>`, `stall100_pm_<service>`, `stall500_pm_<service>`, `ul_deliv_<service>` | per service class (voice, vcall, gaming, stream, web): handovers, unnecessary ones, users, and packet statistics; the classes enter only through the thresholds of the outcome label, the traffic is the same for all |
| `all_attempts`, `all_rlf` | counts including the discarded first 60 s |
| `wall_s`, `sim_per_wall` | run time [s] and simulated seconds per second; not reproducible |
