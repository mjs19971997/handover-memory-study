# Study plan: when does a location memory of handover outcomes help an A3 rule?

Written on 8 October 2026 before any run of this study. Sizes and analyses are fixed in
the batch script and `analyze_mem.py`. Everything is reported whatever it shows.

## Question

A plain Event A3 rule decides from the signal levels of the moment. Does remembering, per
place, how earlier handovers ended reduce unnecessary handovers without adding failures, and
under which conditions (is the outcome of a handover a repeatable property of the place)?

## Rule (`--rule=mem`)

Event A3 with hysteresis h and time-to-trigger, implemented with the standard A3 report and a
per-UE cell-individual offset. Every finished handover attempt contributes a risk score
z = +1 (unnecessary or too early), 0 (useful), -1 (too late), from the label the network can
observe, to the cell (40 m location bin where it was decided, target cell); a radio link
failure with no handover pending counts as too late towards the strongest neighbour. With n
the discounted number of scores of a cell (time constant 600 s), r_bar the network-wide mean
of z and kappa = 3:

    r_hat = (sum z + kappa * r_bar) / (n + kappa)
    margin towards target j at the UE's bin = clip(h + eta * (r_hat - r_bar), 0, 9) dB

eta = 0 is the A3 rule itself (checked: identical handover events). Reference setting:
h = 4 dB, TTT 100 ms, eta = 24 dB.

## Design

| Factor | Levels |
|---|---|
| eta | 0 (control), 6, 12, 24, 36 dB |
| scenario | urban (street grid, blockage tied to place) and base (open area, shadowing independent per link) |
| cells | nominal ISD 200 and 400 m x speeds 8, 16, 30 m/s |
| seeds | 1 to 6; within a seed all eta levels see the same trajectories and random streams |
| run | 900 s, the first 60 s discarded; 20 UEs, 7 gNBs, light traffic, TR 36.839 failure parameters |

360 runs (folders `mem_urban`, `mem_base`), about 3.7 h with 24 workers on one machine.
The per-attempt and per-failure files of every run are kept.

## Endpoints and analyses

**Primary**: unnecessary handovers per UE-minute and failures per UE-minute, eta = 24 against
eta = 0, paired by (cell, seed), pooled over the six cells of a scenario (36 pairs); two-sided
exact Wilcoxon signed-rank test, mean paired difference with 95 % confidence interval. Both
endpoints and both scenarios are reported; a lower unnecessary-handover rate with a higher
failure rate is reported as a trade-off, not as a gain.

**Secondary**: the same for eta = 6, 12, 36 (dose-response), by cell, and by time window
(three equal thirds of the measured time) to show how long the memory takes to act.

**Repeatability of the control logs** (eta = 0 only, so nothing here depends on the memory
rule): per cell, from the attempts of each run and from the six seeds pooled as one log:
intraclass correlation rho of z over places (one-way ANOVA), attempts per place, prequential
skill of a shrinkage table against the running overall mean, the skill expected from rho and
the amount of evidence, and the split-half correlation between even- and odd-numbered UEs.
Formulas in the header of `analyze_mem.py`.

**Expectations stated in advance**: in the urban scenario the blockage is the same for every
UE at a place, so rho should be clearly positive and the memory should be able to help; in the
base scenario shadowing is drawn independently per link, so rho should be near zero and no
gain is expected there (a negative control). If the memory lowers unnecessary handovers where
rho is near zero, or fails to where rho is large, that is reported as it is.

## Limits known in advance

* Six seeds and 280 UE-minutes per run: small effects on failures will not be resolved.
* Light traffic: the failure detector of ns-3 sees little interference at this load.
* One reference setting of h and TTT; it was not tuned for this simulator.
