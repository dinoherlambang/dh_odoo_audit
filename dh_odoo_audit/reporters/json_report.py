"""
JSON Report Generator for dh_odoo_audit.
Produces machine-readable JSON for CI/CD integration.
"""

import os
import json
from dataclasses import asdict
from dh_odoo_audit.core.models import AuditReport


class JSONReporter:
    @staticmethod
    def generate(report: AuditReport, output_file: str):
        os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
        data = asdict(report)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
