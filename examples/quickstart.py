# -*- coding: utf-8 -*-
"""Quick start: plain A3 against A3 with an outcome memory on one small scenario
(well under a minute on a laptop).

The scenario is set by the constants below; change one and run the script again.
The numbers of such a short single run are noisy; the results of the paper come
from experiments/run_study.py.

usage: python examples/quickstart.py
"""
import sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "experiments"))

import numpy as np

from common import make_env, params, scenario, shadow
from hosim.simulator import simulate
from hosim.policies import A3
from memstudy.rule import MemA3
from memstudy.repeatability import repeatability

PROFILE = "highway"     # pedestrian | vehicular | street | highway | train
USERS = 100             # number of users
T = 60.0                # length of the test run [s]
WARM = 60.0             # length of the warm-up of the memory rule [s]
SEED = 1                # seed of the environment, the trajectories and the shadowing
PHI = 1.0               # shared share of the shadowing variance: 1 = everyone sees the same field, 0 = nothing shared
D_CORR = 50.0           # decorrelation distance of the shadowing [m]
HYST, TTT = 4.0, 0.1    # A3 hysteresis [dB] and time-to-trigger [s] of both rules
ETA = 24.0              # strength of the memory [dB]; 0 turns the memory rule into plain A3

if __name__ == "__main__":
    t0 = time.time()
    P = params(T, **shadow(PHI, D_CORR))
    env = make_env("UDN-40", P, SEED)                   # radio map + shadowing field + hotspots + blockage
    a3 = A3(hyst=HYST, ttt=TTT)
    mem = MemA3(hyst=HYST, ttt=TTT, eta=ETA)

    # the memory rule learns from observed outcomes: fill its table on an independent warm-up scenario first
    if WARM:
        Pw = params(WARM, **shadow(PHI, D_CORR))
        traj_w, svc_w = scenario(env, PROFILE, USERS, Pw, 5000 + SEED)
        mem.persist = True                              # keep the table for the next run
        simulate(env, mem, traj_w, svc_w, Pw, seed=5000 + SEED)

    # both rules see the same trajectories, services and shadowing; the control run is logged
    traj, svc = scenario(env, PROFILE, USERS, P, SEED)
    log = []
    res = [simulate(env, a3, traj, svc, P, seed=SEED, log=log), simulate(env, mem, traj, svc, P, seed=SEED)]

    rows = [("handovers per user-minute", "HO_pm"), ("unnecessary HOs per user-minute", "UHO_pm"),
            ("unnecessary-handover ratio", "UHR"), ("mobility failures per user-minute", "fail_pm"),
            ("outage [%]", "outage_pct"), ("delivered / demanded rate", "satisf")]
    print(f"{env.name}, {PROFILE}, {USERS} users, {T:.0f} s, phi = {PHI}, d_corr = {D_CORR:.0f} m\n")
    print(f"{'metric':<36}{'A3':>10}{'memory':>10}{'change':>10}")
    for label, key in rows:
        a, b = res[0][key], res[1][key]
        ch = 100 * (b / a - 1) if a else float("nan")
        print(f"{label:<36}{a:>10.3f}{b:>10.3f}{'0%' if abs(ch) < 0.5 else f'{ch:+.0f}%':>10}")

    # repeatability of the outcomes, from the log of the control run alone
    ev = np.asarray(log, dtype=np.float32)
    rep = repeatability(ev, np.array([env.xmin, env.xmax, env.ymin, env.ymax]), env.M, USERS, T)
    print(f"\ncontrol run: {rep['events']} logged events in {rep['groups']} places ({rep['n']:.1f} per place)")
    print(f"repeatability rho = {rep['rho']:.2f}, prequential skill = {rep['skill']:.2f}, "
          f"split-half correlation = {rep['half']:.2f}")
    print(f"\ndone in {time.time() - t0:.0f} s")
