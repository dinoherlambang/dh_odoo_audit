"""
Core models and definitions for DH Odoo Audit Engine.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


class Severity(str, Enum):
    PASS = "PASS"
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass
class Finding:
    scope: str
    code: str                     # e.g., "AST-01", "CONF-02", "NGINX-01"
    title: str
    severity: Severity
    description: str
    current_value: Optional[str] = None
    target_value: Optional[str] = None
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    snippet_before: Optional[str] = None
    snippet_after: Optional[str] = None
    recommendation: Optional[str] = None


@dataclass
class AuditSummary:
    total_checks: int = 0
    passed: int = 0
    info_count: int = 0
    warning_count: int = 0
    critical_count: int = 0
    health_score: int = 100
    grade: str = "A"
    status_label: str = "PASS"


@dataclass
class AuditReport:
    project_name: str
    odoo_version: str
    timestamp: str
    summary: AuditSummary
    findings: List[Finding] = field(default_factory=list)
    system_specs: Dict[str, Any] = field(default_factory=dict)
    raw_configs: Dict[str, str] = field(default_factory=dict)
