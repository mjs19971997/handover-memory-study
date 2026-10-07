# -*- coding: utf-8 -*-
"""Shared experiment harness: repository paths, the radio environment, the shadowing
split and the scenario generator used by every script of the study."""
import os, sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np

from hosim.radiomap import load_dataset, RadioMap
from hosim.mobility import PROF_BY_KEY
from hosim.simulator import SimParams, RadioEnv, gen_traj, assign_services

DATA = str(ROOT / "data")
OUT = os.environ.get("MEMSTUDY_RESULTS") or str(ROOT / "results")     # result files (override: MEMSTUDY_RESULTS)
LOGS = os.path.join(OUT, "logs")                                      # event logs of the logged control runs
FIG = str(ROOT / "figures")

# radio layouts by environment name; the study uses the 40-cell synthetic layout only
DS = {
    "UDN-40": os.path.join(DATA, "synthetic", "realistic_5G_2x.csv"),
}
SIGMA = 4.0          # total standard deviation of the slow shadowing [dB] (shared + private)
_MAP = {}


def n_procs():
    """Default number of worker processes: env var MEMSTUDY_PROCS, else all cores but one."""
    return max(1, int(os.environ.get("MEMSTUDY_PROCS") or (os.cpu_count() or 2) - 1))


def shadow(phi, d_corr=50.0):
    """SimParams overrides of one propagation setting.

    phi is the shared share of the slow-shadowing variance: the static field that all
    users see has variance phi * SIGMA^2, the private component along each user's own
    path (1 - phi) * SIGMA^2.  phi = 1 is the default of the simulator (no private
    part).  d_corr [m] is the decorrelation distance of both components."""
    return dict(shadow_sigma=SIGMA * float(np.sqrt(phi)), sigma_p=SIGMA * float(np.sqrt(1.0 - phi)),
                d_corr=float(d_corr))


def get_map(name):
    """Radio map (cell positions and path-loss fits) of an environment.  Cached per process."""
    if name not in _MAP:
        if name not in DS:
            raise KeyError(f"Unknown environment {name!r}; known: {', '.join(DS)}")
        if not os.path.exists(DS[name]):
            raise FileNotFoundError(f"Layout not found: {DS[name]}")
        _MAP[name] = RadioMap(load_dataset(DS[name]), name=name)
    return _MAP[name]


def make_env(name, P, seed):
    """Radio environment of one run.  The shadowing field, the hotspot cells and the
    blockage-prone cells are drawn anew for every seed, so the seeds of an experiment
    are independent realisations of the same kind of environment."""
    return RadioEnv(get_map(name), P, het_seed=11 + seed)


def params(T, **overrides):
    """SimParams of a run of length T [s] with the given overrides (see shadow)."""
    return replace(SimParams(T_sim=T), **overrides)


def scenario(env, profile, U, P, seed):
    """Trajectories + service assignment shared by every rule of a (scenario, seed)."""
    S = int(round(P.T_sim / P.dt))
    rng = np.random.default_rng(100003 * seed + 17)
    traj = gen_traj(env, PROF_BY_KEY[profile], U, S, P.dt, rng)
    svc = assign_services(U, np.random.default_rng(500 + seed))
    return traj, svc
