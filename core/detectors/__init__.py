"""检测器模块"""

from .base import BaseDetector
from .chat import ChatDetector
from .duplicate import DuplicateDetector
from .poke import PokeDetector
from .curfew import CurfewManager

__all__ = [
    "BaseDetector",
    "ChatDetector",
    "DuplicateDetector",
    "PokeDetector",
    "CurfewManager",
]
