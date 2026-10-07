"""Code of the study "When is handover history worth remembering?".

Modules
-------
rule           MemA3: Event A3 with a per-place outcome memory (eta = 0 is plain A3)
repeatability  repeatability indices of handover outcomes, computed from an event log
"""
from .rule import MemA3
from .repeatability import load_log, icc, place_groups, repeatability

__version__ = "1.0.0"
