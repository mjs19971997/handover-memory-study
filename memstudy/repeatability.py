# -*- coding: utf-8 -*-
"""Repeatability of handover outcomes, computed from an event log.

The log comes from ordinary operation of a rule without memory (here: A3); nothing
in this module looks at a memory rule.  Every logged event gets a risk score

    z = +1  unnecessary handover, or failure shortly after the handover (too early)
    z =  0  useful handover
    z = -1  link lost before a handover completed (too late)

from its network-observable label.  Events are grouped by place: a (location bin,
target cell) pair, or a (serving cell, target cell) pair.  The indices answer one
question from different sides: does the place tell what the next outcome will be?

    rho    intraclass correlation of z over places (one-way ANOVA estimator): the
           share of the variance of z that belongs to the place
    n      events per visited place in the log: how much evidence a place collects
    skill  prequential skill of a shrinkage table that predicts each event from the
           earlier events of its place: 1 - MSE(table) / MSE(running overall mean)
    law    rho * mean of m / (m + k*), with m the number of earlier events in the
           place of an event and k* = (1 - rho) / rho: the skill expected from rho
           and the amount of evidence alone
    half   split-half correlation: mean z per place from the even-numbered users
           against that from the odd-numbered users
"""
import numpy as np

from hosim.simulator import LOG_COLUMNS, OUT_UNNEC, OUT_FAIL, OUT_LATE

C_T, C_USER, C_X, C_Y = (LOG_COLUMNS.index(c) for c in ("t", "user", "x", "y"))
C_SRC, C_TGT, C_TRUE, C_OBS = (LOG_COLUMNS.index(c) for c in ("source", "target", "outcome", "observed"))


def load_log(path):
    """Read an event log written by experiments/run_study.py.

    Returns (ev, box, M, U, T): the event array (one row per event, columns as in
    hosim.simulator.LOG_COLUMNS), the bounding box of the area (xmin, xmax, ymin,
    ymax) [m], the number of cells, the number of users and the run length [s]."""
    d = np.load(path)
    return d["ev"], d["box"], int(d["M"]), int(d["U"]), float(d["T"])


def icc(z, g):
    """One-way ANOVA intraclass correlation of the values z over the groups g
    (unbalanced design).  NaN if it cannot be estimated."""
    _, inv, n = np.unique(g, return_inverse=True, return_counts=True)
    k, N = len(n), len(z)
    if k < 2 or N <= k:
        return float("nan")
    s = np.bincount(inv, weights=z); mean = s / n; grand = z.mean()
    ssb = float((n * (mean - grand) ** 2).sum())          # between groups
    ssw = float(((z - mean[inv]) ** 2).sum())             # within groups
    msb, msw = ssb / (k - 1), ssw / (N - k)
    n0 = (N - (n ** 2).sum() / N) / (k - 1)               # effective group size
    return float((msb - msw) / (msb + (n0 - 1) * msw)) if msb + (n0 - 1) * msw > 0 else float("nan")


def place_groups(ev, box, M, res=40.0, key="bin"):
    """Group label of every event: (location bin of side `res`, target cell) for
    key="bin", (serving cell, target cell) for key="route".  The bins are those of
    memstudy.rule.MemA3."""
    tgt = ev[:, C_TGT].astype(np.int64)
    if key == "route":
        return ev[:, C_SRC].astype(np.int64) * M + tgt
    nx = int((box[1] - box[0] + 100.0) / res) + 1; ny = int((box[3] - box[2] + 100.0) / res) + 1
    ix = np.clip(((ev[:, C_X] - (box[0] - 50.0)) / res).astype(np.int64), 0, nx - 1)
    iy = np.clip(((ev[:, C_Y] - (box[2] - 50.0)) / res).astype(np.int64), 0, ny - 1)
    return (iy * nx + ix) * M + tgt


def repeatability(ev, box, M, U, T, res=40.0, key="bin", t_max=None, kappa=3.0):
    """Repeatability indices of one event log.

    ev, box, M, U, T  as returned by load_log
    res, key          definition of a place (see place_groups)
    t_max             if given, only the events before t_max [s] are used
    kappa             pseudo-observations of the shrinkage table behind `skill`

    Returns a dict with rho, n, skill, law and half (see the module docstring) and
        rho_un, rho_true         the same intraclass correlation for the indicator
                                 "unnecessary", from the observable and from the
                                 evaluation label
        groups, events           number of visited places and of events
        ev_pm                    events per user-minute of the whole run (T is not
                                 shortened by t_max)
        share_un, share_early, share_late   outcome shares (observable label)
        agree                    share of events whose observable label equals the
                                 evaluation label
    """
    ev = ev[np.argsort(ev[:, C_T], kind="stable")]
    if t_max:
        ev = ev[ev[:, C_T] < t_max]
    obs = ev[:, C_OBS].astype(int)
    true = ev[:, C_TRUE].astype(int)
    z = np.where((obs == OUT_UNNEC) | (obs == OUT_FAIL), 1.0, np.where(obs == OUT_LATE, -1.0, 0.0))
    g = place_groups(ev, box, M, res, key)
    rho = icc(z, g)

    # prequential prediction of z: every event is predicted from the events before it,
    # once by the shrinkage table of its place and once by the running overall mean
    gid = np.unique(g, return_inverse=True)[1]
    cnt = np.zeros(gid.max() + 1); sm = np.zeros(gid.max() + 1)
    tot = 0.0; e_tab = e_glb = 0.0; w_sum = 0.0
    r = max(rho, 1e-6) if rho == rho else 1e-6
    kstar = (1 - r) / r
    burn = len(z) // 10                                   # the first tenth only fills the table
    for i in range(len(z)):
        gm = tot / i if i else 0.0
        m = cnt[gid[i]]
        pred = (sm[gid[i]] + kappa * gm) / (m + kappa)
        if i >= burn:
            e_tab += (z[i] - pred) ** 2; e_glb += (z[i] - gm) ** 2; w_sum += m / (m + kstar)
        cnt[gid[i]] += 1; sm[gid[i]] += z[i]; tot += z[i]
    nev = len(z) - burn

    # split-half: the same places seen by two disjoint halves of the users
    even = ev[:, C_USER].astype(int) % 2 == 0
    a = np.bincount(gid[even], minlength=len(cnt)); b = np.bincount(gid[~even], minlength=len(cnt))
    za = np.bincount(gid[even], weights=z[even], minlength=len(cnt))
    zb = np.bincount(gid[~even], weights=z[~even], minlength=len(cnt))
    both = (a >= 3) & (b >= 3)                            # places with at least three events in each half
    half = float(np.corrcoef(za[both] / a[both], zb[both] / b[both])[0, 1]) if both.sum() >= 10 else float("nan")

    return dict(rho=rho,
                rho_un=icc((obs == OUT_UNNEC).astype(float), g),
                rho_true=icc((true == OUT_UNNEC).astype(float), g),
                n=float(len(z) / len(cnt)), groups=int(len(cnt)), events=int(len(z)),
                ev_pm=float(len(z) / (U * T / 60.0)),
                skill=float(1 - e_tab / e_glb) if e_glb > 0 else float("nan"),
                law=float(max(rho, 0.0) * w_sum / nev) if rho == rho and nev else float("nan"),
                half=half,
                share_un=float((obs == OUT_UNNEC).mean()), share_early=float((obs == OUT_FAIL).mean()),
                share_late=float((obs == OUT_LATE).mean()),
                agree=float((true == obs).mean()))
