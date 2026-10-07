"""
Health score calculation and grading module.
"""

from typing import List
from dh_odoo_audit.core.models import Finding, Severity, AuditSummary


def calculate_health_score(findings: List[Finding]) -> AuditSummary:
    total_checks = len(findings)
    passed = 0
    info_count = 0
    warning_count = 0
    critical_count = 0

    deductions = 0

    for f in findings:
        if f.severity == Severity.PASS:
            passed += 1
        elif f.severity == Severity.INFO:
            info_count += 1
            deductions += 1
        elif f.severity == Severity.WARNING:
            warning_count += 1
            deductions += 5
        elif f.severity == Severity.CRITICAL:
            critical_count += 1
            deductions += 15

    score = max(0, 100 - deductions)

    if score >= 85:
        grade = "A"
        status_label = "EXCELLENT" if critical_count == 0 else "GOOD (Minor Critical)"
    elif score >= 70:
        grade = "B"
        status_label = "CONDITIONAL PASS"
    elif score >= 50:
        grade = "C"
        status_label = "ACTION REQUIRED"
    else:
        grade = "D"
        status_label = "CRITICAL RISK"

    return AuditSummary(
        total_checks=total_checks,
        passed=passed,
        info_count=info_count,
        warning_count=warning_count,
        critical_count=critical_count,
        health_score=score,
        grade=grade,
        status_label=status_label
    )
