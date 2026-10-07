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

        # ----------------------------------------------------------------------
        # SECURITY HARDENING CHECKS
        # ----------------------------------------------------------------------

        # 7. Database Manager Protection (/web/database/manager)
        if scope_cfg.get("verify_database_manager_protection", True):
            has_db_manager_block = re.search(r"location\s+.*(/web/database/manager|/web/database)", nginx_content) is not None
            has_deny_or_allow = re.search(r"(deny all|return 40|allow\s+)", nginx_content) is not None

            if not (has_db_manager_block and has_deny_or_allow):
                findings.append(Finding(
                    scope=self.name,
                    code="GATEWAY-SEC-DB-MANAGER-EXPOSED",
                    title="Database Manager Odoo Terbuka ke Publik",
                    severity=Severity.CRITICAL,
                    description="Endpoint /web/database/manager dan selector tidak dilindungi oleh restriksi IP atau deny all. Siapa pun di internet dapat menghapus, menduplikasi, atau mengunduh backup database jika master password lemah.",
                    current_value="Publicly Exposed",
                    target_value="Restricted by IP or Denied",
                    file_path=nginx_conf_path,
                    recommendation="Tambahkan proteksi IP pada Nginx: 'location /web/database/manager { allow 10.0.0.0/8; deny all; ... }' atau blokir akses eksternal."
                ))
            else:
                findings.append(Finding(
                    scope=self.name,
                    code="GATEWAY-SEC-DB-MANAGER-OK",
                    title="Database Manager Dilindungi",
                    severity=Severity.PASS,
                    description="Endpoint database manager memiliki restriksi akses.",
                    current_value="Protected",
                    target_value="Restricted"
                ))

        # 8. Login Rate Limiting Anti-Bruteforce (/web/login)
        if scope_cfg.get("verify_login_rate_limiting", True):
            has_rate_limit_zone = "limit_req_zone" in nginx_content
            has_login_limit = re.search(r"location\s+.*(/web/login)", nginx_content) is not None and "limit_req" in nginx_content

            if not (has_rate_limit_zone and has_login_limit):
                findings.append(Finding(
                    scope=self.name,
                    code="GATEWAY-SEC-LOGIN-BRUTEFORCE",
                    title="Halaman Login (/web/login) Rentan Serangan Brute-Force",
                    severity=Severity.WARNING,
                    description="Nginx belum menerapkan rate limiting pada endpoint /web/login. Server berisiko terhadap credential stuffing dan serangan brute-force password.",
                    current_value="No rate limit",
                    target_value="limit_req_zone + limit_req active",
                    file_path=nginx_conf_path,
                    recommendation="Definisikan 'limit_req_zone $binary_remote_addr zone=odoo_login:10m rate=5r/m;' dan terapkan pada 'location = /web/login'."
                ))
            else:
                findings.append(Finding(
                    scope=self.name,
                    code="GATEWAY-SEC-LOGIN-OK",
                    title="Proteksi Rate Limiting Login Aktif",
                    severity=Severity.PASS,
                    description="Endpoint login dilindungi dengan rate limiting.",
                    current_value="Active",
                    target_value="Rate limited"
                ))

        # 9. HTTP Security Headers (Clickjacking & MIME-Sniffing)
        if scope_cfg.get("verify_security_headers", True):
            has_x_frame = "X-Frame-Options" in nginx_content
            has_x_content_type = "X-Content-Type-Options" in nginx_content

            if not (has_x_frame and has_x_content_type):
                findings.append(Finding(
                    scope=self.name,
                    code="GATEWAY-SEC-HEADERS-MISSING",
                    title="HTTP Security Headers Kurang Lengkap",
                    severity=Severity.WARNING,
                    description="Nginx belum mengirimkan header X-Frame-Options (anti-clickjacking) atau X-Content-Type-Options (anti-MIME-sniffing).",
                    current_value="Missing Security Headers",
                    target_value="X-Frame-Options & X-Content-Type-Options present",
                    file_path=nginx_conf_path,
                    recommendation="Tambahkan 'add_header X-Frame-Options SAMEORIGIN;' dan 'add_header X-Content-Type-Options nosniff;'."
                ))
            else:
                findings.append(Finding(
                    scope=self.name,
                    code="GATEWAY-SEC-HEADERS-OK",
                    title="HTTP Security Headers Terpasang",
                    severity=Severity.PASS,
                    description="Header anti-clickjacking dan anti-MIME-sniffing aktif.",
                    current_value="Configured",
                    target_value="Configured"
                ))

        # 10. Information Disclosure (server_tokens off)
        if scope_cfg.get("verify_server_tokens_hidden", True):
            is_server_tokens_off = re.search(r"server_tokens\s+off", nginx_content) is not None
            if not is_server_tokens_off:
                findings.append(Finding(
                    scope=self.name,
                    code="GATEWAY-SEC-SERVER-TOKENS",
                    title="Versi Nginx Terekspos ke Publik (server_tokens on)",
                    severity=Severity.WARNING,
                    description="Nginx membocorkan nomor versinya pada header HTTP 'Server' dan halaman error default. Hal ini mempermudah penyerang menargetkan CVE spesifik.",
                    current_value="server_tokens on/unset",
                    target_value="server_tokens off;",
                    file_path=nginx_conf_path,
                    recommendation="Tambahkan 'server_tokens off;' di dalam blok http atau server Nginx."
                ))
            else:
                findings.append(Finding(
                    scope=self.name,
                    code="GATEWAY-SEC-SERVER-TOKENS-OK",
                    title="Versi Nginx Tersembunyi",
                    severity=Severity.PASS,
                    description="server_tokens off aktif.",
                    current_value="Hidden",
                    target_value="Hidden"
                ))

        # 11. Hidden Dotfiles Protection (.git, .env)
        if scope_cfg.get("verify_dotfiles_denied", True):
            has_dotfile_deny = re.search(r"location\s+~?\s*\\?/\.", nginx_content) is not None
            if not has_dotfile_deny:
                findings.append(Finding(
                    scope=self.name,
                    code="GATEWAY-SEC-DOTFILES-OPEN",
                    title="Akses File Tersembunyi (.git, .env) Belum Diblokir",
                    severity=Severity.INFO,
                    description="Nginx belum secara eksplisit memblokir request ke file atau direktori tersembunyi berawalan titik (seperti .git, .env, .htaccess).",
                    current_value="Not blocked",
                    target_value=r"location ~ /\. { deny all; }",
                    file_path=nginx_conf_path,
                    recommendation="Tambahkan blok: 'location ~ /\\. { deny all; access_log off; log_not_found off; }'."
                ))
            else:
                findings.append(Finding(
                    scope=self.name,
                    code="GATEWAY-SEC-DOTFILES-OK",
                    title="Akses File Tersembunyi Diblokir",
                    severity=Severity.PASS,
                    description="Blok deny all untuk file berawalan titik aktif.",
                    current_value="Blocked",
                    target_value="Blocked"
                ))

        return findings

