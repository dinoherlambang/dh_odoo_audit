"""
OS & Infrastructure audit checker (Swappiness, Filestore Disk Space).
"""

import os
import shutil
from typing import List, Dict, Any
from dh_odoo_audit.checkers.base import BaseChecker
from dh_odoo_audit.core.models import Finding, Severity


class OSInfraChecker(BaseChecker):
    """Audits OS swappiness and filestore disk space."""

    def __init__(self):
        super().__init__("infrastructure_and_os")

    def run(self, config: Dict[str, Any]) -> List[Finding]:
        findings: List[Finding] = []
        scope_cfg = config.get("audit_scopes", {}).get("infrastructure_and_os", {})

        if not scope_cfg.get("enabled", True):
            return findings

        # 1. Swappiness Check
        swappiness_path = "/proc/sys/vm/swappiness"
        if os.path.exists(swappiness_path):
            try:
                with open(swappiness_path, "r", encoding="utf-8") as f:
                    val = int(f.read().strip())
                if val > 20:
                    findings.append(Finding(
                        scope=self.name,
                        code="OS-SWAPPINESS-HIGH",
                        title="Nilai Swappiness Linux Terlalu Agresif",
                        severity=Severity.WARNING,
                        description=f"vm.swappiness bernilai {val} (Default OS). Linux akan memindahkan memori aktif ke disk swap, memicu latency pada Odoo dan Postgres.",
                        current_value=str(val),
                        target_value="1 s/d 10",
                        file_path=swappiness_path,
                        recommendation="Set 'sysctl vm.swappiness=10' dan simpan di /etc/sysctl.conf."
                    ))
                else:
                    findings.append(Finding(
                        scope=self.name,
                        code="OS-SWAPPINESS-OK",
                        title="Nilai Swappiness Linux Optimal",
                        severity=Severity.PASS,
                        description=f"vm.swappiness = {val} sudah tepat untuk server database/ERP.",
                        current_value=str(val),
                        target_value="1 s/d 10"
                    ))
            except Exception as e:
                pass
        else:
            findings.append(Finding(
                scope=self.name,
                code="OS-SWAPPINESS-NA",
                title="Pemeriksaan Swappiness Dilewati",
                severity=Severity.INFO,
                description="/proc/sys/vm/swappiness tidak tersedia (Lingkungan Windows/Container).",
                current_value="N/A",
                target_value="Informational"
            ))

        # 2. Disk Space Check
        scan_path = config.get("global_settings", {}).get("output_dir", ".")
        try:
            usage = shutil.disk_usage(scan_path)
            total_gb = round(usage.total / (1024 ** 3), 1)
            free_gb = round(usage.free / (1024 ** 3), 1)
            free_pct = round((usage.free / usage.total) * 100, 1)

            if free_pct < 10.0 or free_gb < 5.0:
                findings.append(Finding(
                    scope=self.name,
                    code="INFRA-DISK-CRITICAL",
                    title="Kapasitas Sisa Storage Sangat Kritis",
                    severity=Severity.CRITICAL,
                    description=f"Sisa partisi storage hanya {free_pct}% ({free_gb} GB bebas dari total {total_gb} GB).",
                    current_value=f"{free_pct}% Free ({free_gb} GB)",
                    target_value="Sisa > 20%",
                    recommendation="Bersihkan log lama atau tambah kapasitas disk penyimpanan segera."
                ))
            elif free_pct < 20.0:
                findings.append(Finding(
                    scope=self.name,
                    code="INFRA-DISK-WARN",
                    title="Kapasitas Sisa Storage Mendekati Batas",
                    severity=Severity.WARNING,
                    description=f"Sisa storage tersisa {free_pct}% ({free_gb} GB).",
                    current_value=f"{free_pct}% Free",
                    target_value="Sisa > 20%"
                ))
            else:
                findings.append(Finding(
                    scope=self.name,
                    code="INFRA-DISK-OK",
                    title="Kapasitas Storage Aman",
                    severity=Severity.PASS,
                    description=f"Partisi memiliki {free_pct}% ({free_gb} GB) ruang kosong.",
                    current_value=f"{free_pct}% Free",
                    target_value="Sisa > 20%"
                ))
        except Exception:
            pass

        return findings
