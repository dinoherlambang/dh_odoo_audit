"""
Markdown Report Generator for dh_odoo_audit.
Produces rich, actionable audit report formatted in GitHub Flavored Markdown.
"""

import os
from typing import List
from dh_odoo_audit.core.models import AuditReport, Severity, Finding


class MarkdownReporter:
    @staticmethod
    def generate(report: AuditReport, output_file: str):
        os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)

        lines: List[str] = []
        summary = report.summary

        # Header
        lines.append("# 🛡️ DH Odoo Performance & Code Audit Engine (OPCAE) Report")
        lines.append(f"**Proyek:** {report.project_name} | **Target:** Odoo {report.odoo_version} | **Tanggal:** {report.timestamp}")
        lines.append("")
        lines.append("---")
        lines.append("")

        # 1. Executive Summary & Health Score
        badge = "🟢" if summary.health_score >= 85 else ("🟡" if summary.health_score >= 70 else "🔴")
        lines.append("## 1. Executive Summary & Health Score")
        lines.append("")
        lines.append("| Health Score | Grade | Status | Total Checks | Critical | Warning | Info | Passed |")
        lines.append("| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |")
        lines.append(f"| **{summary.health_score} / 100** | **Grade {summary.grade}** | {badge} **{summary.status_label}** | {summary.total_checks} | {summary.critical_count} | {summary.warning_count} | {summary.info_count} | {summary.passed} |")
        lines.append("")

        # 2. Server & Database Configuration Findings
        lines.append("## 2. Server & Database Configuration Audit")
        lines.append("")
        hw_findings = [f for f in report.findings if f.scope == "system_hardware_and_config" and f.severity != Severity.PASS]
        if hw_findings:
            lines.append("| Code | Severity | Judul Temuan | Nilai Saat Ini | Target Ideal | Rekomendasi |")
            lines.append("| :--- | :---: | :--- | :--- | :--- | :--- |")
            for f in hw_findings:
                sev_icon = "🔴" if f.severity == Severity.CRITICAL else ("🟡" if f.severity == Severity.WARNING else "ℹ️")
                lines.append(f"| `{f.code}` | {sev_icon} **{f.severity.value}** | {f.title} | `{f.current_value or '-'}` | `{f.target_value or '-'}` | {f.recommendation or f.description} |")
            lines.append("")
        else:
            lines.append("✅ *Semua parameter hardware dan konfigurasi server dalam kondisi optimal.*")
            lines.append("")

        # 3. Gateway & Nginx Proxy Alignment Findings
        lines.append("## 3. Web Gateway & Nginx Alignment Audit")
        lines.append("")
        gateway_findings = [f for f in report.findings if f.scope == "gateway_and_odoo_alignment" and f.severity != Severity.PASS]
        if gateway_findings:
            lines.append("| Code | Severity | Judul Temuan | Target Solusi |")
            lines.append("| :--- | :---: | :--- | :--- |")
            for f in gateway_findings:
                sev_icon = "🔴" if f.severity == Severity.CRITICAL else "🟡"
                lines.append(f"| `{f.code}` | {sev_icon} **{f.severity.value}** | **{f.title}**<br>{f.description} | {f.recommendation or f.target_value} |")
            lines.append("")
        else:
            lines.append("✅ *Konfigurasi Nginx reverse proxy dan odoo.conf telah tersinkronisasi dengan sempurna.*")
            lines.append("")

        # 4. Static Code (AST) Findings
        lines.append("## 4. Static Code Analysis (Custom Addons)")
        lines.append("")
        ast_findings = [f for f in report.findings if f.scope == "static_code_analysis" and f.severity not in (Severity.PASS, Severity.INFO)]
        if ast_findings:
            for idx, f in enumerate(ast_findings, 1):
                sev_icon = "🔴" if f.severity == Severity.CRITICAL else "🟡"
                lines.append(f"### [{f.code}] {f.title}")
                lines.append(f"- **Severity:** {sev_icon} `{f.severity.value}`")
                lines.append(f"- **File:** `{f.file_path}` (Line {f.line_number or 'N/A'})")
                lines.append(f"- **Penjelasan:** {f.description}")
                if f.snippet_before:
                    lines.append("- **Potongan Kode:**")
                    lines.append("```python")
                    lines.append(f.snippet_before)
                    lines.append("```")
                if f.recommendation:
                    lines.append(f"- **Saran Solusi:** {f.recommendation}")
                lines.append("")
        else:
            lines.append("✅ *Tidak ditemukan pelanggaran performa kritis pada modul kustom.*")
            lines.append("")

        # 5. OS & Infrastructure
        lines.append("## 5. OS & Infrastructure Audit")
        lines.append("")
        infra_findings = [f for f in report.findings if f.scope == "infrastructure_and_os" and f.severity != Severity.PASS]
        if infra_findings:
            for f in infra_findings:
                sev_icon = "🔴" if f.severity == Severity.CRITICAL else ("🟡" if f.severity == Severity.WARNING else "ℹ️")
                lines.append(f"- {sev_icon} **{f.title}:** {f.description} *(Rekomendasi: {f.recommendation or f.target_value})*")
            lines.append("")
        else:
            lines.append("✅ *Kondisi OS, swappiness, dan penyimpanan dalam keadaan sehat.*")
            lines.append("")

        # Write output file
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
