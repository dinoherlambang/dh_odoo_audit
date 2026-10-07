"""
Hardware and configuration audit checker for Odoo and PostgreSQL.
"""

import os
import sys
import re
from typing import List, Dict, Any, Optional
from dh_odoo_audit.checkers.base import BaseChecker
from dh_odoo_audit.core.models import Finding, Severity


def get_system_specs():
    """Detect CPU and RAM using psutil if available, with standard library fallback."""
    cpu_cores = os.cpu_count() or 4
    ram_bytes = 16 * (1024 ** 3)  # Fallback default: 16 GB

    try:
        import psutil
        cpu_cores = psutil.cpu_count(logical=True) or cpu_cores
        ram_bytes = psutil.virtual_memory().total
        return cpu_cores, ram_bytes
    except ImportError:
        pass

    # Linux /proc/meminfo fallback
    if os.path.exists("/proc/meminfo"):
        try:
            with open("/proc/meminfo", "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        kb = int(line.split()[1])
                        ram_bytes = kb * 1024
                        return cpu_cores, ram_bytes
        except Exception:
            pass

    # Windows GlobalMemoryStatusEx fallback
    if sys.platform == "win32":
        try:
            import ctypes
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]
            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                ram_bytes = stat.ullTotalPhys
        except Exception:
            pass

    return cpu_cores, ram_bytes



def parse_ini_file(file_path: str) -> Dict[str, str]:
    """Parse standard INI/conf file into key-value pairs."""
    params = {}
    if not os.path.exists(file_path):
        return params

    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith(";"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                # Remove inline comments
                val = val.split("#")[0].split(";")[0].strip()
                params[key.strip()] = val.strip().strip("'\"")
    return params


class HardwareConfChecker(BaseChecker):
    """Audits system CPU/RAM against odoo.conf and postgresql.conf settings."""

    def __init__(self):
        super().__init__("system_hardware_and_config")

    def run(self, config: Dict[str, Any]) -> List[Finding]:
        findings: List[Finding] = []
        global_cfg = config.get("global_settings", {})
        scope_cfg = config.get("audit_scopes", {}).get("system_hardware_and_config", {})

        if not scope_cfg.get("enabled", True):
            return findings

        # 1. Detect System Specs
        cpu_cores, ram_bytes = get_system_specs()
        ram_gb = round(ram_bytes / (1024 ** 3), 1)

        findings.append(Finding(
            scope=self.name,
            code="HW-INFO",
            title="Spesifikasi Hardware Terdeteksi",
            severity=Severity.INFO,
            description=f"Server memiliki {cpu_cores} vCPU Cores dan {ram_gb} GB Total RAM.",
            current_value=f"{cpu_cores} Cores, {ram_gb} GB RAM",
            target_value="Informational"
        ))

        # 2. Check Odoo Configuration
        odoo_conf_path = global_cfg.get("odoo_conf_path", "")
        if odoo_conf_path and os.path.exists(odoo_conf_path):
            odoo_params = parse_ini_file(odoo_conf_path)
            self._audit_odoo_conf(odoo_params, cpu_cores, ram_bytes, findings, odoo_conf_path)
        else:
            findings.append(Finding(
                scope=self.name,
                code="CONF-FILE-MISSING",
                title="File odoo.conf Tidak Ditemukan",
                severity=Severity.WARNING,
                description=f"Path file odoo.conf di '{odoo_conf_path}' tidak ditemukan.",
                current_value="Not Found",
                target_value="File must exist"
            ))

        # 3. Check PostgreSQL Configuration
        pg_conf_path = global_cfg.get("postgres_conf_path", "")
        if pg_conf_path and os.path.exists(pg_conf_path):
            pg_params = parse_ini_file(pg_conf_path)
            self._audit_postgres_conf(pg_params, ram_gb, findings, pg_conf_path)
        else:
            findings.append(Finding(
                scope=self.name,
                code="PG-CONF-MISSING",
                title="File postgresql.conf Tidak Ditemukan",
                severity=Severity.WARNING,
                description=f"Path file postgresql.conf di '{pg_conf_path}' tidak ditemukan.",
                current_value="Not Found",
                target_value="File must exist"
            ))

        return findings

    def _audit_odoo_conf(self, params: Dict[str, str], cpu_cores: int, ram_bytes: int,
                         findings: List[Finding], file_path: str):
        # A. Workers
        workers_val = int(params.get("workers", 0))
        target_workers = (cpu_cores * 2) + 1

        if workers_val == 0:
            findings.append(Finding(
                scope=self.name,
                code="CONF-WORKERS-ZERO",
                title="Odoo Berjalan dalam Single-Process Mode",
                severity=Severity.CRITICAL,
                description="Parameter 'workers = 0'. Odoo tidak menggunakan multiprocessing gevent. Permintaan lambat akan memblokir seluruh user.",
                current_value="0",
                target_value=str(target_workers),
                file_path=file_path,
                recommendation=f"Set 'workers = {target_workers}' pada odoo.conf."
            ))
        elif abs(workers_val - target_workers) > 3:
            findings.append(Finding(
                scope=self.name,
                code="CONF-WORKERS-MISMATCH",
                title="Jumlah Workers Odoo Kurang Optimal",
                severity=Severity.WARNING,
                description=f"Jumlah workers ({workers_val}) menyimpang dari target ideal ({target_workers}) berdasarkan {cpu_cores} Core CPU.",
                current_value=str(workers_val),
                target_value=str(target_workers),
                file_path=file_path,
                recommendation=f"Sesuaikan 'workers = {target_workers}'."
            ))
        else:
            findings.append(Finding(
                scope=self.name,
                code="CONF-WORKERS-OK",
                title="Jumlah Workers Odoo Sesuai",
                severity=Severity.PASS,
                description=f"Workers = {workers_val} sudah proporsional dengan {cpu_cores} CPU Cores.",
                current_value=str(workers_val),
                target_value=str(target_workers)
            ))

        # B. Cron Threads
        cron_threads = int(params.get("max_cron_threads", 2))
        if workers_val > 0 and cron_threads == 0:
            findings.append(Finding(
                scope=self.name,
                code="CONF-CRON-ZERO",
                title="Cron Threads Bernilai 0 saat Multiprocessing Aktif",
                severity=Severity.CRITICAL,
                description="max_cron_threads = 0 menyebabkan seluruh scheduled actions Odoo (cron) macet.",
                current_value="0",
                target_value="1 atau 2",
                file_path=file_path,
                recommendation="Set 'max_cron_threads = 2'."
            ))

        # C. Memory Limits
        soft_limit = int(params.get("limit_memory_soft", 0))
        hard_limit = int(params.get("limit_memory_hard", 0))

        if soft_limit == 0 or hard_limit == 0:
            findings.append(Finding(
                scope=self.name,
                code="CONF-MEM-LIMIT-UNSET",
                title="Batas Memori Odoo Belum Dikonfigurasi",
                severity=Severity.WARNING,
                description="limit_memory_soft atau limit_memory_hard belum diatur. Risiko memory leak memakan seluruh RAM server.",
                current_value=f"soft={soft_limit}, hard={hard_limit}",
                target_value="soft=2147483648 (2GB), hard=2684354560 (2.5GB)",
                file_path=file_path,
                recommendation="Tentukan 'limit_memory_soft = 2147483648' dan 'limit_memory_hard = 2684354560'."
            ))
        elif hard_limit < soft_limit:
            findings.append(Finding(
                scope=self.name,
                code="CONF-MEM-HARD-LESS-SOFT",
                title="Nilai limit_memory_hard Lebih Kecil dari limit_memory_soft",
                severity=Severity.CRITICAL,
                description="Konfigurasi memori terbalik. Hard limit harus lebih besar dari soft limit.",
                current_value=f"soft={soft_limit}, hard={hard_limit}",
                target_value="hard > soft",
                file_path=file_path,
                recommendation="Pastikan hard limit lebih besar dari soft limit."
            ))

        # D. Timeouts
        cpu_time = int(params.get("limit_time_cpu", 60))
        real_time = int(params.get("limit_time_real", 120))
        if cpu_time == 0 or real_time == 0:
            findings.append(Finding(
                scope=self.name,
                code="CONF-TIMEOUT-ZERO",
                title="Batas Waktu Eksekusi (Timeout) Tidak Terbatas",
                severity=Severity.WARNING,
                description="limit_time_cpu atau limit_time_real = 0 dapat menyebabkan hanging worker tidak pernah di-kill.",
                current_value=f"cpu={cpu_time}, real={real_time}",
                target_value="cpu=60..120, real=120..180",
                file_path=file_path,
                recommendation="Set 'limit_time_cpu = 60' dan 'limit_time_real = 120'."
            ))

    def _audit_postgres_conf(self, params: Dict[str, str], ram_gb: float,
                            findings: List[Finding], file_path: str):
        # A. random_page_cost
        page_cost = float(params.get("random_page_cost", "4.0"))
        if page_cost >= 3.5:
            findings.append(Finding(
                scope=self.name,
                code="PG-RANDOM-PAGE-COST",
                title="PostgreSQL random_page_cost Masih Nilai Default HDD",
                severity=Severity.WARNING,
                description=f"Nilai {page_cost} didesain untuk media HDD piringan lama. Query planner akan cenderung memilih sequential scan daripada index scan.",
                current_value=str(page_cost),
                target_value="1.1 (SSD/NVMe)",
                file_path=file_path,
                recommendation="Ubah 'random_page_cost = 1.1' di postgresql.conf untuk server media SSD."
            ))
        else:
            findings.append(Finding(
                scope=self.name,
                code="PG-RANDOM-PAGE-COST-OK",
                title="PostgreSQL random_page_cost Sesuai SSD",
                severity=Severity.PASS,
                description=f"random_page_cost = {page_cost} sudah optimal untuk SSD.",
                current_value=str(page_cost),
                target_value="1.1"
            ))

        # B. shared_buffers
        shared_buff = params.get("shared_buffers", "128MB")
        if "128MB" in shared_buff and ram_gb >= 4.0:
            target_buff_gb = round(ram_gb * 0.25, 1)
            findings.append(Finding(
                scope=self.name,
                code="PG-SHARED-BUFFERS-DEFAULT",
                title="PostgreSQL shared_buffers Masih Nilai Default Vanilla",
                severity=Severity.WARNING,
                description=f"Nilai shared_buffers {shared_buff} terlalu kecil untuk server berukuran {ram_gb} GB RAM.",
                current_value=shared_buff,
                target_value=f"{target_buff_gb}GB (25% Total RAM)",
                file_path=file_path,
                recommendation=f"Set 'shared_buffers = {int(target_buff_gb)}GB' di postgresql.conf."
            ))
