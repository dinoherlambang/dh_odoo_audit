"""
Modular Scope Reporter and Optimal Configuration Bundle Generator.
Creates dedicated folders per scope containing specific findings and ready-to-deploy optimized configs.
"""

import os
from typing import List, Dict, Any
from dh_odoo_audit.core.models import AuditReport, Severity, Finding
from dh_odoo_audit.checkers.hardware_conf import get_system_specs


class ModularBundleGenerator:
    """Generates organized, dedicated folders per scope with actionable revision files."""

    @classmethod
    def generate(cls, report: AuditReport, base_output_dir: str):
        os.makedirs(base_output_dir, exist_ok=True)

        cpu_cores, ram_bytes = get_system_specs()
        ram_gb = round(ram_bytes / (1024 ** 3), 1)

        cls._generate_executive_summary(report, base_output_dir)
        cls._generate_odoo_scope(report, base_output_dir, cpu_cores, ram_gb)
        cls._generate_postgres_scope(report, base_output_dir, ram_gb)
        cls._generate_gateway_scope(report, base_output_dir)
        cls._generate_os_infra_scope(report, base_output_dir)
        cls._generate_code_remediation_scope(report, base_output_dir)

    @classmethod
    def _generate_executive_summary(cls, report: AuditReport, base_dir: str):
        summary = report.summary
        content = f"""# 🛡️ Executive Summary & Master Audit Report
**Proyek:** {report.project_name} | **Target:** Odoo {report.odoo_version} | **Tanggal:** {report.timestamp}

---

## 1. Kartu Skor Kesehatan Sistem (Health Score)

| Metrik | Nilai | Status |
| :--- | :---: | :--- |
| **Health Score** | **{summary.health_score} / 100** | **Grade {summary.grade} - {summary.status_label}** |
| **Total Pemeriksaan** | **{summary.total_checks}** | Parameter diperiksa |
| **Isu Kritis (CRITICAL)** | **{summary.critical_count}** | Membutuhkan revisi segera |
| **Peringatan (WARNING)** | **{summary.warning_count}** | Potensi degradasi performa |
| **Informasi (INFO)** | **{summary.info_count}** | Catatan sistem |
| **Lulus (PASSED)** | **{summary.passed}** | Parameter optimal |

---

## 2. Navigasi Folder Hasil Audit & Rekomendasi Optimal

Setiap folder di bawah ini telah disiapkan khusus untuk tim terkait dengan file konfigurasi revisi siap pakai:

1. **[`01_ODOO_CONFIG_REVISION/`](./01_ODOO_CONFIG_REVISION/)**: Konfigurasi `odoo_optimized.conf` hasil kalkulasi RAM dan CPU.
2. **[`02_POSTGRESQL_TUNING/`](./02_POSTGRESQL_TUNING/)**: File `postgresql_optimized.conf` disesuaikan untuk media penyimpanan modern dan alokasi memori.
3. **[`03_GATEWAY_NGINX_ALIGNMENT/`](./03_GATEWAY_NGINX_ALIGNMENT/)**: File `nginx_optimized.conf` dengan perutean port longpolling 8072, header proxy HTTPS, dan buffer 128k.
4. **[`04_OS_INFRASTRUCTURE/`](./04_OS_INFRASTRUCTURE/)**: Konfigurasi `sysctl_optimized.conf` (swappiness optimal).
5. **[`05_CODE_REMEDIATION_AST/`](./05_CODE_REMEDIATION_AST/)**: Panduan refactoring Before vs After untuk modul kustom Python.
6. **[`06_AI_PROMPT_PAYLOAD/`](./06_AI_PROMPT_PAYLOAD/)**: Prompt tersanitasi siap pakai untuk konsultasi AI lanjutan.
"""
        with open(os.path.join(base_dir, "00_EXECUTIVE_SUMMARY.md"), "w", encoding="utf-8") as f:
            f.write(content)

    @classmethod
    def _generate_odoo_scope(cls, report: AuditReport, base_dir: str, cpu_cores: int, ram_gb: float):
        scope_dir = os.path.join(base_dir, "01_ODOO_CONFIG_REVISION")
        os.makedirs(scope_dir, exist_ok=True)

        target_workers = (cpu_cores * 2) + 1
        soft_limit = 2147483648  # 2 GB
        hard_limit = 2684354560  # 2.5 GB

        # 1. Audit Findings
        findings = [f for f in report.findings if f.scope == "system_hardware_and_config" and "CONF" in f.code]
        findings_md = [
            "# 📋 Audit Konfigurasi Odoo (odoo.conf)",
            f"Spesifikasi Server: **{cpu_cores} vCPU Cores**, **{ram_gb} GB RAM**\n",
            "## Temuan Parameter:",
            "| Code | Severity | Parameter | Nilai Saat Ini | Target Revisi | Rekomendasi |",
            "| :--- | :---: | :--- | :--- | :--- | :--- |"
        ]
        for f in findings:
            findings_md.append(f"| `{f.code}` | **{f.severity.value}** | {f.title} | `{f.current_value or '-'}` | `{f.target_value or '-'}` | {f.recommendation or f.description} |")

        with open(os.path.join(scope_dir, "audit_findings.md"), "w", encoding="utf-8") as f:
            f.write("\n".join(findings_md))

        # 2. Optimized Config File
        conf_content = f"""; ==============================================================================
; DH Odoo Audit Engine: REVISED & OPTIMIZED odoo.conf
; Target Server: {cpu_cores} vCPU Cores | {ram_gb} GB Total RAM
; ==============================================================================

[options]
; Multiprocessing Workers: Formula (CPU * 2) + 1
workers = {target_workers}

; Memory Limits per Worker (Mencegah memory leak & OOM-Killer)
limit_memory_soft = {soft_limit}
limit_memory_hard = {hard_limit}

; Timeouts (Mencegah hanging worker & 504 Timeout)
limit_time_cpu = 60
limit_time_real = 120

; Scheduled Actions / Cron Workers
max_cron_threads = 2

; Reverse Proxy Mode (Wajib True jika menggunakan Nginx)
proxy_mode = True

; Port Binding Default
xmlrpc_port = 8069
longpolling_port = 8072
"""
        with open(os.path.join(scope_dir, "odoo_optimized.conf"), "w", encoding="utf-8") as f:
            f.write(conf_content)

    @classmethod
    def _generate_postgres_scope(cls, report: AuditReport, base_dir: str, ram_gb: float):
        scope_dir = os.path.join(base_dir, "02_POSTGRESQL_TUNING")
        os.makedirs(scope_dir, exist_ok=True)

        shared_buffers_gb = max(1, int(ram_gb * 0.25))
        effective_cache_gb = max(2, int(ram_gb * 0.75))
        work_mem_mb = 32 if ram_gb >= 16 else 16
        maint_work_mem_mb = min(2048, int(ram_gb * 1024 * 0.1))

        # 1. Audit Findings
        findings = [f for f in report.findings if f.scope == "system_hardware_and_config" and "PG" in f.code]
        findings_md = [
            "# 📋 Audit Konfigurasi PostgreSQL (postgresql.conf)",
            f"Alokasi Memori Server: **{ram_gb} GB RAM**\n",
            "## Temuan Parameter:",
            "| Code | Severity | Judul Temuan | Nilai Saat Ini | Target Revisi | Rekomendasi |",
            "| :--- | :---: | :--- | :--- | :--- | :--- |"
        ]
        for f in findings:
            findings_md.append(f"| `{f.code}` | **{f.severity.value}** | {f.title} | `{f.current_value or '-'}` | `{f.target_value or '-'}` | {f.recommendation or f.description} |")

        with open(os.path.join(scope_dir, "audit_findings.md"), "w", encoding="utf-8") as f:
            f.write("\n".join(findings_md))

        # 2. Optimized Config File
        conf_content = f"""# ==============================================================================
# DH Odoo Audit Engine: REVISED & OPTIMIZED postgresql.conf
# Target Spesifikasi: {ram_gb} GB RAM | Media Penyimpanan: SSD/NVMe
# ==============================================================================

# Memory Optimization
shared_buffers = {shared_buffers_gb}GB
effective_cache_size = {effective_cache_gb}GB
maintenance_work_mem = {maint_work_mem_mb}MB
work_mem = {work_mem_mb}MB

# Query Planner & Storage Tuning (Penting untuk SSD)
random_page_cost = 1.1
effective_io_concurrency = 200

# Write-Ahead Logging & Checkpoints
wal_buffers = 16MB
min_wal_size = 1GB
max_wal_size = 4GB
checkpoint_completion_target = 0.9
"""
        with open(os.path.join(scope_dir, "postgresql_optimized.conf"), "w", encoding="utf-8") as f:
            f.write(conf_content)

    @classmethod
    def _generate_gateway_scope(cls, report: AuditReport, base_dir: str):
        scope_dir = os.path.join(base_dir, "03_GATEWAY_NGINX_ALIGNMENT")
        os.makedirs(scope_dir, exist_ok=True)

        findings = [f for f in report.findings if f.scope == "gateway_and_odoo_alignment"]
        findings_md = [
            "# 📋 Audit Web Gateway & Nginx Reverse Proxy",
            "## Temuan Sinkronisasi Nginx vs Odoo:",
            "| Code | Severity | Temuan Masalah | Solusi Revisi |",
            "| :--- | :---: | :--- | :--- |"
        ]
        for f in findings:
            findings_md.append(f"| `{f.code}` | **{f.severity.value}** | **{f.title}**<br>{f.description} | {f.recommendation or f.target_value} |")

        with open(os.path.join(scope_dir, "audit_findings.md"), "w", encoding="utf-8") as f:
            f.write("\n".join(findings_md))

        # 2. Optimized Nginx Config File (Performance + Security Hardening)
        nginx_conf = r"""# ==============================================================================
# DH Odoo Audit Engine: REVISED & OPTIMIZED nginx.conf
# Gateway Alignment + Security Hardening (Port 8072, SSL, DB Protection, Rate Limiting)
# ==============================================================================

# Definisi Rate Limiting untuk Halaman Login (Anti-Brute Force)
limit_req_zone $binary_remote_addr zone=odoo_login:10m rate=5r/m;

upstream odoo_server {
    server 127.0.0.1:8069;
}

upstream odoo_chat {
    server 127.0.0.1:8072;
}

server {
    listen 80;
    server_name erp.yourdomain.com;

    # 1. Information Disclosure Protection
    server_tokens off;

    # 2. HTTP Security Headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    # Aktifkan HSTS jika sudah menggunakan sertifikat HTTPS:
    # add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # 3. Batas upload file attachment & Excel import
    client_max_body_size 100M;

    # 4. Timeout simetris (mencegah error 504 pada transaksi laporan)
    proxy_read_timeout 300s;
    proxy_connect_timeout 300s;
    proxy_send_timeout 300s;

    # 5. Buffer anti-502 untuk cookie sesi Odoo yang besar
    proxy_buffer_size 128k;
    proxy_buffers 16 64k;
    proxy_busy_buffers_size 128k;

    # 6. Kompresi Gzip untuk bundle JS/CSS
    gzip on;
    gzip_types text/css application/javascript application/json text/xml image/svg+xml;

    # --------------------------------------------------------------------------
    # SECURITY RESTRICTIONS
    # --------------------------------------------------------------------------

    # Proteksi Database Manager (Hanya izinkan akses lokal / VPN admin)
    location ~* /web/database/(manager|selector) {
        allow 127.0.0.1;
        allow 10.0.0.0/8;
        allow 192.168.0.0/16;
        deny all;

        proxy_pass http://odoo_server;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # Proteksi Anti-Brute Force pada Halaman Login
    location = /web/login {
        limit_req zone=odoo_login burst=10 nodelay;

        proxy_pass http://odoo_server;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # Blokir Akses ke File Tersembunyi (.git, .env, .htaccess)
    location ~ /\. {
        deny all;
        access_log off;
        log_not_found off;
    }

    # --------------------------------------------------------------------------
    # ROUTING & TRAFFIC DELIVERY
    # --------------------------------------------------------------------------

    # 1. Routing Longpolling / Chat ke Port 8072 (Multiprocessing)
    location /longpolling {
        proxy_pass http://odoo_chat;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # 2. Routing Utama Web Client ke Port 8069
    location / {
        proxy_pass http://odoo_server;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # 3. Cache Asset Statis
    location ~* /web/static/ {
        proxy_cache_valid 200 60m;
        proxy_buffering on;
        expires 30d;
        proxy_pass http://odoo_server;
    }
}
"""
        with open(os.path.join(scope_dir, "nginx_optimized.conf"), "w", encoding="utf-8") as f:
            f.write(nginx_conf)


    @classmethod
    def _generate_os_infra_scope(cls, report: AuditReport, base_dir: str):
        scope_dir = os.path.join(base_dir, "04_OS_INFRASTRUCTURE")
        os.makedirs(scope_dir, exist_ok=True)

        findings = [f for f in report.findings if f.scope == "infrastructure_and_os"]
        findings_md = [
            "# 📋 Audit Sistem Operasi & Infrastruktur",
            "## Temuan Kondisi OS & Penyimpanan:",
            "| Code | Severity | Parameter | Deskripsi | Rekomendasi |",
            "| :--- | :---: | :--- | :--- | :--- |"
        ]
        for f in findings:
            findings_md.append(f"| `{f.code}` | **{f.severity.value}** | {f.title} | {f.description} | {f.recommendation or '-'} |")

        with open(os.path.join(scope_dir, "audit_findings.md"), "w", encoding="utf-8") as f:
            f.write("\n".join(findings_md))

        # sysctl recommended
        sysctl_conf = """# ==============================================================================
# DH Odoo Audit Engine: REVISED Linux Kernel sysctl.conf
# Mencegah OS memindahkan RAM aktif Odoo/PostgreSQL ke swap disk
# ==============================================================================

# Turunkan kecenderungan swap dari default 60 menjadi 10
vm.swappiness = 10

# Batas file descriptors untuk banyak koneksi worker Odoo
fs.file-max = 2097152
"""
        with open(os.path.join(scope_dir, "sysctl_optimized.conf"), "w", encoding="utf-8") as f:
            f.write(sysctl_conf)

    @classmethod
    def _generate_code_remediation_scope(cls, report: AuditReport, base_dir: str):
        scope_dir = os.path.join(base_dir, "05_CODE_REMEDIATION_AST")
        os.makedirs(scope_dir, exist_ok=True)

        findings = [f for f in report.findings if f.scope == "static_code_analysis" and f.severity != Severity.INFO]

        findings_md = [
            "# 📋 Audit Kode Python Modul Kustom (AST)",
            "## Daftar Pelanggaran Performa Terdeteksi:\n"
        ]

        guide_md = [
            "# 🛠️ Panduan Revisi Kode Modul Kustom (Before vs After)",
            "Panduan ini merangkum perbaikan baris kode untuk menghilangkan N+1 query dan bottleneck transaksi database.\n"
        ]

        if not findings:
            findings_md.append("✅ *Tidak ditemukan pelanggaran performa pada modul kustom.*")
            guide_md.append("✅ *Seluruh kode modul kustom telah memenuhi standar performa ORM.*")
        else:
            for idx, f in enumerate(findings, 1):
                findings_md.append(f"### [{idx}] `{f.code}` - {f.title}")
                findings_md.append(f"- **File:** `{f.file_path}` (Baris: {f.line_number or 'N/A'})")
                findings_md.append(f"- **Tingkat Bahaya:** `{f.severity.value}`")
                findings_md.append(f"- **Penyebab:** {f.description}")
                if f.snippet_before:
                    findings_md.append("```python\n" + f.snippet_before + "\n```")
                findings_md.append("")

                guide_md.append(f"### Revisi Masalah #{idx}: {f.title}")
                guide_md.append(f"**Lokasi File:** `{f.file_path}` (Baris: {f.line_number or 'N/A'})\n")
                if f.snippet_before:
                    guide_md.append("```python\n# ❌ SEBELUM (Kode Bermasalah):")
                    guide_md.append(f.snippet_before + "\n")
                    guide_md.append("# ✅ SESUDAH (Solusi Rekomendasi):")
                    guide_md.append(f"# {f.recommendation}\n```\n")

        with open(os.path.join(scope_dir, "audit_findings.md"), "w", encoding="utf-8") as f:
            f.write("\n".join(findings_md))

        with open(os.path.join(scope_dir, "code_refactoring_guide.md"), "w", encoding="utf-8") as f:
            f.write("\n".join(guide_md))
