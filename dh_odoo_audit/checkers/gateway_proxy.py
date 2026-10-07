"""
Dedicated Web Gateway & Odoo Configuration Alignment Checker.
Audits cross-configuration synchronization between Nginx and odoo.conf.
"""

import os
import re
from typing import List, Dict, Any
from dh_odoo_audit.checkers.base import BaseChecker
from dh_odoo_audit.core.models import Finding, Severity


def read_file_content(path: str) -> str:
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


class GatewayProxyChecker(BaseChecker):
    """Cross-validates Nginx reverse proxy configuration with odoo.conf."""

    def __init__(self):
        super().__init__("gateway_and_odoo_alignment")

    def run(self, config: Dict[str, Any]) -> List[Finding]:
        findings: List[Finding] = []
        global_cfg = config.get("global_settings", {})
        scope_cfg = config.get("audit_scopes", {}).get("gateway_and_odoo_alignment", {})

        if not scope_cfg.get("enabled", True):
            return findings

        odoo_conf_path = global_cfg.get("odoo_conf_path", "")
        nginx_conf_path = global_cfg.get("nginx_conf_path", "")

        odoo_content = read_file_content(odoo_conf_path)
        nginx_content = read_file_content(nginx_conf_path)

        if not nginx_content:
            findings.append(Finding(
                scope=self.name,
                code="NGINX-CONF-MISSING",
                title="File Konfigurasi Nginx Tidak Ditemukan",
                severity=Severity.WARNING,
                description=f"File Nginx di '{nginx_conf_path}' tidak ditemukan.",
                current_value="Not Found",
                target_value="File must exist"
            ))
            return findings

        # 1. proxy_mode vs Nginx Headers
        is_proxy_mode = re.search(r"^\s*proxy_mode\s*=\s*(True|1|true)", odoo_content, re.M) is not None
        has_forwarded_host = "X-Forwarded-Host" in nginx_content
        has_forwarded_proto = "X-Forwarded-Proto" in nginx_content

        if not is_proxy_mode:
            findings.append(Finding(
                scope=self.name,
                code="GATEWAY-PROXY-MODE-OFF",
                title="Odoo proxy_mode Bernilai False di Balik Nginx",
                severity=Severity.CRITICAL,
                description="Odoo berjalan di balik reverse proxy tetapi 'proxy_mode = True' belum diset. Redirect HTTPS akan bermasalah (Mixed Content).",
                current_value="proxy_mode = False",
                target_value="proxy_mode = True",
                file_path=odoo_conf_path,
                recommendation="Tambahkan 'proxy_mode = True' di bagian [options] odoo.conf."
            ))
        else:
            findings.append(Finding(
                scope=self.name,
                code="GATEWAY-PROXY-MODE-OK",
                title="Odoo proxy_mode Aktif",
                severity=Severity.PASS,
                description="proxy_mode = True aktif di odoo.conf.",
                current_value="True",
                target_value="True"
            ))

        if not has_forwarded_host or not has_forwarded_proto:
            findings.append(Finding(
                scope=self.name,
                code="GATEWAY-NGINX-HEADERS-MISSING",
                title="Header X-Forwarded-* Kurang Lengkap di Nginx",
                severity=Severity.WARNING,
                description="Nginx belum meneruskan X-Forwarded-Host atau X-Forwarded-Proto $scheme ke Odoo.",
                current_value="Missing Headers",
                target_value="X-Forwarded-Host & X-Forwarded-Proto present",
                file_path=nginx_conf_path,
                recommendation="Tambahkan 'proxy_set_header X-Forwarded-Host $host;' dan 'proxy_set_header X-Forwarded-Proto $scheme;'."
            ))

        # 2. Longpolling Route to Port 8072
        has_longpolling_route = re.search(r"location\s+/(longpolling|websocket)", nginx_content) is not None
        has_8072_target = "8072" in nginx_content

        if not (has_longpolling_route and has_8072_target):
            findings.append(Finding(
                scope=self.name,
                code="GATEWAY-LONGPOLLING-MISSING",
                title="Rute Longpolling (Port 8072) Belum Terpisah di Nginx",
                severity=Severity.CRITICAL,
                description="Nginx tidak memisahkan rute /longpolling ke port 8072. Traffic live chat dan bus notification akan membanjiri HTTP worker utama (port 8069).",
                current_value="No separate 8072 routing",
                target_value="location /longpolling -> port 8072",
                file_path=nginx_conf_path,
                recommendation="Konfigurasikan upstream terpisah untuk port 8072 dan buat blok 'location /longpolling { proxy_pass http://odoochat; }'."
            ))
        else:
            findings.append(Finding(
                scope=self.name,
                code="GATEWAY-LONGPOLLING-OK",
                title="Rute Longpolling Port 8072 Terkonfigurasi",
                severity=Severity.PASS,
                description="Rute /longpolling diarahkan ke port 8072.",
                current_value="Configured",
                target_value="Port 8072"
            ))

        # 3. Timeout Symmetry
        real_time_match = re.search(r"^\s*limit_time_real\s*=\s*(\d+)", odoo_content, re.M)
        odoo_real_time = int(real_time_match.group(1)) if real_time_match else 120

        nginx_timeout_match = re.search(r"proxy_read_timeout\s+(\d+)", nginx_content)
        nginx_read_timeout = int(nginx_timeout_match.group(1)) if nginx_timeout_match else 60

        if nginx_read_timeout < odoo_real_time:
            findings.append(Finding(
                scope=self.name,
                code="GATEWAY-TIMEOUT-ASYMMETRY",
                title="Nginx proxy_read_timeout Lebih Kecil dari limit_time_real Odoo",
                severity=Severity.WARNING,
                description=f"Nginx timeout ({nginx_read_timeout}s) < Odoo timeout ({odoo_real_time}s). User akan melihat 504 Gateway Timeout saat Odoo masih memproses laporan.",
                current_value=f"nginx={nginx_read_timeout}s, odoo={odoo_real_time}s",
                target_value=f"nginx >= {odoo_real_time}s (Direkomendasikan >= 300s)",
                file_path=nginx_conf_path,
                recommendation=f"Set 'proxy_read_timeout 300s;' pada konfigurasi Nginx."
            ))

        # 4. Buffers Size (Anti-502)
        has_buffer_128k = re.search(r"proxy_buffers?\s+.*(64k|128k)", nginx_content) is not None
        if not has_buffer_128k:
            findings.append(Finding(
                scope=self.name,
                code="GATEWAY-BUFFERS-TOO-SMALL",
                title="Buffer Nginx Belum Disesuaikan untuk Header Odoo",
                severity=Severity.WARNING,
                description="Odoo memiliki cookie sesi yang besar. Buffer default Nginx rawan memicu '502 Bad Gateway: upstream sent too big header'.",
                current_value="Default Buffers",
                target_value="proxy_buffers 16 64k; proxy_buffer_size 128k;",
                file_path=nginx_conf_path,
                recommendation="Tambahkan 'proxy_buffer_size 128k;' dan 'proxy_buffers 16 64k;'."
            ))

        # 5. Upload Body Size
        body_size_match = re.search(r"client_max_body_size\s+(\d+)([mMkK]?)", nginx_content)
        if not body_size_match:
            findings.append(Finding(
                scope=self.name,
                code="GATEWAY-BODY-SIZE-DEFAULT",
                title="client_max_body_size Nginx Belum Didefinisikan",
                severity=Severity.WARNING,
                description="Nilai default Nginx adalah 1MB. Pengguna tidak akan bisa mengunggah lampiran PDF faktur atau Excel impor > 1MB (Error 413).",
                current_value="1M (Default)",
                target_value="client_max_body_size 50M;",
                file_path=nginx_conf_path,
                recommendation="Tambahkan 'client_max_body_size 50M;' di blok server/http Nginx."
            ))
        else:
            size_num = int(body_size_match.group(1))
            unit = body_size_match.group(2).upper()
            if unit == "M" and size_num < 25:
                findings.append(Finding(
                    scope=self.name,
                    code="GATEWAY-BODY-SIZE-LOW",
                    title="client_max_body_size Terlalu Kecil",
                    severity=Severity.INFO,
                    description=f"Batas upload {size_num}MB mungkin kurang untuk impor data besar.",
                    current_value=f"{size_num}M",
                    target_value=">= 50M",
                    file_path=nginx_conf_path
                ))

        # 6. Gzip Compression
        if "gzip on" not in nginx_content:
            findings.append(Finding(
                scope=self.name,
                code="GATEWAY-GZIP-OFF",
                title="Gzip Compression Belum Aktif di Nginx",
                severity=Severity.WARNING,
                description="Kompresi gzip menghemat hingga 70% bandwidth web client Odoo untuk file JS dan CSS bundle.",
                current_value="Off",
                target_value="gzip on;",
                file_path=nginx_conf_path,
                recommendation="Aktifkan 'gzip on;' dan sertakan mime type text/css application/javascript application/json."
            ))

        return findings
