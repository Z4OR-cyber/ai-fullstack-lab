"""
Bounty platform adapters.

支持的平台适配器:
    - :class:`HackerOneAdapter`: HackerOne (Basic Auth)
    - :class:`BugcrowdAdapter`: Bugcrowd (Token Header)
    - :class:`IntigritiAdapter`: Intigriti (Bearer Token)
    - :class:`YesWeHackAdapter`: YesWeHack (Bearer Token)
"""

from .hackerone import HackerOneAdapter
from .bugcrowd import BugcrowdAdapter
from .intigriti import IntigritiAdapter
from .yeswehack import YesWeHackAdapter

__all__ = [
    "HackerOneAdapter",
    "BugcrowdAdapter",
    "IntigritiAdapter",
    "YesWeHackAdapter",
]
