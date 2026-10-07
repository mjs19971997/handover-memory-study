# -*- coding: utf-8 -*-
"""The memory rule of the study: Event A3 with a per-place memory of handover outcomes.

The rule is deliberately minimal.  It is 3GPP Event A3 with one extra term: the
hysteresis towards a target cell is raised where earlier handovers to that target
turned out unnecessary or failed early, and lowered where the link used to be lost
before a handover completed.  With eta = 0 the extra term vanishes and the rule is
exactly A3 with the same hysteresis and time-to-trigger; that is the control of
every comparison in the study.
"""
import numpy as np

from hosim.policies import Base
from hosim.simulator import OUT_LATE


class MemA3(Base):
    """Event A3 whose hysteresis is shifted, per place and per target cell, by what
    earlier handovers there led to.

        margin = hyst + eta * (risk - mean risk),   clipped to [m_lo, m_hi]
        risk   = P(unnecessary) + P(early failure) - P(too late)

    A "place" is a square location bin of side `res` (key="bin") or the serving cell
    (key="route").  The probabilities of a (place, target) pair come from discounted
    counts of the four observable outcomes, shrunk towards the network-wide shares
    with `kappa` pseudo-observations, so a place without history gets the plain
    hysteresis.  "mean risk" is the same expression for the network-wide shares;
    subtracting it makes the offset zero on average.

    hyst, ttt   A3 hysteresis [dB] and time-to-trigger [s]
    eta         strength of the reaction [dB]; 0 switches the memory off
    key, res    kind of place and bin size [m]
    kappa       number of pseudo-observations of the shrinkage
    tau_f       forgetting time constant of the counts [s]; None or 0 = no forgetting
    m_lo, m_hi  limits of the margin [dB]

    Attributes set from outside: `persist` keeps the counts across runs (used for
    the warm-up), `freeze` stops them from changing.
    """

    def __init__(self, hyst=4.0, ttt=0.1, eta=8.0, key="bin", res=40.0, kappa=3.0, tau_f=600.0,
                 m_lo=0.0, m_hi=9.0, name="Mem-A3"):
        self.hyst, self.ttt, self.eta, self.key, self.res = hyst, ttt, eta, key, res
        self.kappa, self.tau_f, self.m_lo, self.m_hi, self.name = kappa, tau_f, m_lo, m_hi, name
        self.N = None                     # counts per (place, target, outcome)
        self.persist = False
        self.freeze = False

    def reset_run(self, U, env, P, traj=None):
        super().reset_run(U, env, P, traj)
        if self.N is None or not self.persist:
            # location bins cover the area with a 50 m border
            self.x0, self.y0 = env.xmin - 50.0, env.ymin - 50.0
            self.nx = int((env.xmax - env.xmin + 100.0) / self.res) + 1
            self.ny = int((env.ymax - env.ymin + 100.0) / self.res) + 1
            n_places = self.nx * self.ny if self.key == "bin" else env.M
            self.N = np.zeros((n_places, env.M, 4), dtype=np.float32)
            self.G = np.zeros(4)          # network-wide counts of the four outcomes
        self.k_now = np.zeros(U, dtype=int)       # place of every user in the current step
        self.k_ev = np.zeros(U, dtype=int)        # place where the user's last handover was decided
        self._off = None
        self._acc = 0.0

    def _places(self, ctx):
        """Index of the place every user is in."""
        if self.key != "bin":
            return ctx["serv"].copy()
        ix = np.clip(((ctx["x"] - self.x0) / self.res).astype(int), 0, self.nx - 1)
        iy = np.clip(((ctx["y"] - self.y0) / self.res).astype(int), 0, self.ny - 1)
        return iy * self.nx + ix

    def decide(self, ctx):
        self.k_now = self._places(ctx)
        if ctx["k"] % 3 == 0 or self._off is None:          # the offset is refreshed every 300 ms
            g = self.G + 1.0
            pbar = g / g.sum()                               # network-wide outcome shares
            n = self.N[self.k_now] + self.kappa * pbar       # (U, M, 4) counts + pseudo-observations
            p = n / n.sum(2, keepdims=True)
            self._off = self.eta * ((p[..., 1] + p[..., 2] - p[..., 3]) - (pbar[1] + pbar[2] - pbar[3]))
        margin = np.clip(self.hyst + self._off, self.m_lo, self.m_hi)
        return self._a3(ctx, self._gap(ctx), margin, self.ttt, by_score=True)

    def on_outcome(self, src, tgt, out, uidx, dwell, t):
        if not self.freeze:
            np.add.at(self.N, (self.k_ev[uidx], tgt, out), 1.0)
            np.add.at(self.G, out, 1.0)

    def on_late(self, src, tgt, uidx, t):
        if not self.freeze:
            np.add.at(self.N, (self.k_now[uidx], tgt, OUT_LATE), 1.0)
            self.G[OUT_LATE] += len(uidx)

    def after_step(self, ctx, sinr_s, hoflag):
        self.k_ev = np.where(hoflag, self.k_now, self.k_ev)
        if self.tau_f and not self.freeze:                   # forgetting, applied once per second
            self._acc += self.P.dt
            if self._acc >= 1.0 - 1e-9:
                f = np.exp(-self._acc / self.tau_f)
                self.N *= f; self.G *= f
                self._acc = 0.0
