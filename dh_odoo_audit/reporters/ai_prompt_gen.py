"""
AI Prompt Generator for dh_odoo_audit.
Formats audit results into structured, privacy-safe prompts for LLMs (Gemini, ChatGPT, Claude).
"""

import os
import re
from typing import List
from dh_odoo_audit.core.models import AuditReport, Severity, Finding


def mask_sensitive_data(text: str) -> str:
    """Mask common sensitive patterns such as passwords and keys."""
    text = re.sub(r'(admin_passwd\s*=\s*)([^\s]+)', r'\1********', text)
    text = re.sub(r'(db_password\s*=\s*)([^\s]+)', r'\1********', text)
    text = re.sub(r'(password\s*=\s*)([^\s]+)', r'\1********', text)
    return text


class AIPromptGenerator:
    @staticmethod
    def generate(report: AuditReport, output_file: str):
        os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)

        lines: List[str] = []

        # System Directive / Role
        lines.append("# SYSTEM DIRECTIVE: ODOO 13 TECHNICAL ARCHITECT & CODE SPECIALIST")
        lines.append("Anda adalah seorang Principal Technical Architect Odoo 13 dan DevOps Performance Specialist.")
        lines.append("Berikut adalah hasil audit sistem dan modul kustom dari server Odoo Production kami (menggunakan DH Odoo Audit Engine).")
        lines.append("Tugas Anda adalah menganalisis akar masalah secara komprehensif, memberikan konfigurasi siap pakai, serta menulis ulang (refactor) kode modul kustom yang terdeteksi melanggar kaidah performa.")
        lines.append("")
        lines.append("---")
        lines.append("")

        # 1. System Metadata & Health Score
        lines.append("## 1. CONTEXT & METADATA SISTEM")
        lines.append(f"- **Proyek:** {report.project_name}")
        lines.append(f"- **Target Odoo Version:** {report.odoo_version}")
        lines.append(f"- **Audit Health Score:** {report.summary.health_score} / 100 (Grade: {report.summary.grade} - {report.summary.status_label})")
        lines.append(f"- **Statistik Masalah:** {report.summary.critical_count} Critical, {report.summary.warning_count} Warning")
        lines.append("")

        # 2. Critical Configuration Findings
        lines.append("## 2. SERVER & GATEWAY CONFIGURATION MISMATCHES")
        conf_findings = [f for f in report.findings if f.scope in ("system_hardware_and_config", "gateway_and_odoo_alignment") and f.severity in (Severity.CRITICAL, Severity.WARNING)]
        if conf_findings:
            for f in conf_findings:
                lines.append(f"- **[{f.code}] {f.title}** ({f.severity.value})")
                lines.append(f"  - Nilai saat ini: `{f.current_value or '-'}`")
                lines.append(f"  - Target ideal: `{f.target_value or '-'}`")
                lines.append(f"  - Catatan: {f.description}")
        else:
            lines.append("*(Tidak ada masalah konfigurasi kritis)*")
        lines.append("")

        # 3. Static Code (AST) Findings with Code Snippets
        lines.append("## 3. STATIC CODE (AST) PERFORMANCE ISSUES")
        ast_findings = [f for f in report.findings if f.scope == "static_code_analysis" and f.severity in (Severity.CRITICAL, Severity.WARNING)]
        if ast_findings:
            for idx, f in enumerate(ast_findings, 1):
                lines.append(f"### [Issue {idx}: {f.code} - {f.title}]")
                lines.append(f"- **File:** `{f.file_path}` (Line: {f.line_number or 'N/A'})")
                lines.append(f"- **Severity:** `{f.severity.value}`")
                lines.append(f"- **Penyebab:** {f.description}")
                if f.snippet_before:
                    lines.append("- **Potongan Baris Kode Asli:**")
                    lines.append("```python")
                    lines.append(f.snippet_before)
                    lines.append("```")
                lines.append("")
        else:
            lines.append("*(Tidak ada pelanggaran kode kritis)*")
        lines.append("")

        # 4. Clear Call-to-Action for AI
        lines.append("## 4. INSTRUKSI TUGAS UNTUK ANDA (AI):")
        lines.append("Berdasarkan data audit di atas, berikan jawaban teknis dengan urutan terstruktur berikut:")
        lines.append("")
        lines.append("1. **Root Cause Analysis (RCA):**")
        lines.append("   - Jelaskan dampak langsung terhadap server Odoo produksi jika isu-isu di atas dibiarkan.")
        lines.append("2. **Ready-to-Apply Configuration Snippets:**")
        lines.append("   - Tuliskan blok konfigurasi final untuk `/etc/odoo/odoo.conf`, `/etc/postgresql/13/main/postgresql.conf`, dan blok Nginx `upstream` + `location` yang sudah tersinkronisasi.")
        lines.append("3. **Refactored Python Code:**")
        lines.append("   - Untuk setiap temuan kode pada bagian 3, tuliskan kode perbaikan (Before vs After) menggunakan pola batching ORM Odoo 13 yang paling efisien dan aman.")
        lines.append("4. **Rollout Checklist:**")
        lines.append("   - Berikan panduan langkah-langkah deployment perbaikan tanpa menyebabkan downtime panjang.")

        prompt_content = "\n".join(lines)
        prompt_content = mask_sensitive_data(prompt_content)

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(prompt_content)
