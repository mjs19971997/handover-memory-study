"""Load-coupled system-level handover simulator for dense 5G networks.

Modules
-------
radiomap   radio map (cell positions, per-cell path-loss fit) built from a drive-test table
mobility   the five mobility profiles
services   the five 5QI service classes
simulator  the simulator, its shadowing model, its event log and its metrics
policies   interface of a decision rule (Base) and 3GPP Event A3
"""
from .radiomap import RadioMap, load_dataset
from .mobility import PROFILES, PROF_BY_KEY
from .services import SERVICES
from .simulator import (SimParams, RadioEnv, gen_traj, assign_services, simulate, area_frac,
                        OUT_USEFUL, OUT_UNNEC, OUT_FAIL, OUT_LATE, LOG_COLUMNS)
from .policies import Base, A3

__version__ = "1.0.0"
