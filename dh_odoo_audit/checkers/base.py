"""
Base Checker class for dh_odoo_audit.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any
from dh_odoo_audit.core.models import Finding


class BaseChecker(ABC):
    """Abstract base class for all audit checkers."""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def run(self, config: Dict[str, Any]) -> List[Finding]:
        """Execute the checker and return a list of findings."""
        pass
