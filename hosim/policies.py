# -*- coding: utf-8 -*-
"""Interface between the simulator and a handover decision rule, and 3GPP Event A3.

Every rule sees the same information: L3-filtered RSRP of the serving cell and its
neighbours, the UE position/velocity estimate, the service class, and the outcome
events the network can observe.  A rule acts through the Event-A3 machinery of
`Base` (entering condition + time-to-trigger timer per neighbour), so rules differ
only in the margin they ask for.
"""
import numpy as np

NEG = -1e9


class Base:
    """Interface between the simulator and a decision rule.

    A rule implements decide(ctx) and may override the hooks below.  ctx is a dict
    with the keys t [s], k (step index), meas (U,M) L3-filtered RSRP [dBm],
    serv (U,) serving cell, x, y [m], v [m/s], th [rad] (motion estimate),
    last_ho (U,) time of the last handover, svc (U,) service index, rng (the
    run's random generator) and active (U,) False while a user re-establishes.
    decide returns an integer array (U,): the target cell, or -1 to stay.
    """
    name = "base"

    def reset_run(self, U, env, P, traj=None):
        """Called once before a run; allocates the per-user, per-neighbour TTT timers."""
        self.U, self.env, self.P = U, env, P
        self.ar = np.arange(U)
        self.timer = np.zeros((U, env.M))
        self.last_serv = np.full(U, -1)

    def decide(self, ctx):
        """Target cell per user, or -1 to stay."""
        raise NotImplementedError

    def on_outcome(self, src, tgt, out, uidx, dwell, t):
        """Observable outcome (OUT_USEFUL / OUT_UNNEC / OUT_FAIL) of executed handovers
        src -> tgt of users uidx, with their dwell time in the target."""

    def on_late(self, src, tgt, uidx, t):
        """Too-late events: the link of users uidx was lost in src (tgt = intended or
        strongest neighbour)."""

    def on_reset(self, idx):
        """Users idx went through a radio-link failure: clear their timers."""
        self.timer[idx] = 0

    def after_step(self, ctx, sinr_s, hoflag):
        """Called at the end of every step with the serving SINR and the flags of the
        users that executed a handover in this step."""

    def _gap(self, ctx):
        """Measured RSRP of every cell minus that of the serving cell -> (U, M)."""
        meas, serv = ctx["meas"], ctx["serv"]
        return meas - meas[self.ar, serv][:, None]

    def _a3(self, ctx, gap, margin, ttt, by_score=False):
        """Entering condition gap > margin held for ttt; returns target or -1.

        margin is a number or an array (U, M).  Among the neighbours whose timer has
        expired the one with the largest gap is taken, or, with by_score, the one
        with the largest gap above its own margin."""
        serv = ctx["serv"]
        ch = serv != self.last_serv
        if ch.any():
            self.timer[ch] = 0
        self.last_serv = serv.copy()
        cond = self.env.nbmask[serv] & (gap > margin)
        self.timer = np.where(cond, self.timer + self.P.dt, 0.0)
        ready = self.timer >= ttt - 1e-9
        self.ready = ready
        score = np.where(ready, (gap - margin) if by_score else gap, NEG)
        tgt = np.argmax(score, axis=1)
        tgt[~ready.any(axis=1)] = -1
        return tgt


class A3(Base):
    """3GPP Event A3: neighbour better than serving by a hysteresis for TTT."""

    def __init__(self, hyst=3.0, ttt=0.3, name="A3"):
        self.hyst, self.ttt, self.name = hyst, ttt, name

    def decide(self, ctx):
        return self._a3(ctx, self._gap(ctx), self.hyst, self.ttt)
