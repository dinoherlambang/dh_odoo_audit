#!/usr/bin/env python3
"""
DH Odoo Performance & Code Audit Engine (OPCAE)
Main CLI Entrypoint.
"""

import sys
import os
import argparse
from datetime import datetime

# Add package directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from dh_odoo_audit.config_loader import load_config
from dh_odoo_audit.core.models import AuditReport, Severity
from dh_odoo_audit.core.scoring import calculate_health_score
from dh_odoo_audit.checkers.hardware_conf import HardwareConfChecker
from dh_odoo_audit.checkers.gateway_proxy import GatewayProxyChecker
from dh_odoo_audit.checkers.os_infra import OSInfraChecker
from dh_odoo_audit.checkers.ast_code import ASTCodeChecker
from dh_odoo_audit.reporters.markdown_report import MarkdownReporter
from dh_odoo_audit.reporters.json_report import JSONReporter
from dh_odoo_audit.reporters.ai_prompt_gen import AIPromptGenerator
from dh_odoo_audit.reporters.modular_bundle_gen import ModularBundleGenerator


BANNER = r"""
======================================================================
  ____  _   _   ___   ____   ___   ___       _   _   _ ____ ___ _____ 
 |  _ \| | | | / _ \ |  _ \ / _ \ / _ \     / \ | | | |  _ \_ _|_   _|
 | | | | |_| || | | || | | | | | | | | |   / _ \| | | | | | | |  | |  
 | |_| |  _  || |_| || |_| | |_| | |_| |  / ___ \ |_| | |_| | |  | |  
 |____/|_| |_(_)___(_)____/ \___/ \___/  /_/   \_\___/|____/___| |_|  
      Odoo 13 Performance & Code Audit Engine (Zero-Impact)
======================================================================
"""


def main():
    parser = argparse.ArgumentParser(description="DH Odoo Performance & Code Audit Engine")
    parser.add_argument("-c", "--config", default="audit_config.yaml", help="Path to audit configuration YAML")
    parser.add_argument("--format", choices=["markdown", "json", "ai_prompt", "all"], help="Override report format")
    parser.add_argument("-o", "--output-dir", help="Override output directory")
    parser.add_argument("--fail-on-critical", action="store_true", help="Exit with code 1 if critical issues found (CI/CD)")

    args = parser.parse_args()

    print(BANNER)

    # 1. Load Configuration
    config_path = os.path.abspath(args.config)
    print(f"[*] Loading configuration from: {config_path}")
    try:
        config = load_config(config_path)
    except Exception as e:
        print(f"[!] Error loading configuration: {e}")
        sys.exit(1)

    global_cfg = config.get("global_settings", {})
    output_dir = args.output_dir or global_cfg.get("output_dir", "./audit_reports")
    output_format = args.format or global_cfg.get("output_format", "all")
    os.makedirs(output_dir, exist_ok=True)

    # 2. Run Audit Checkers
    checkers = [
        HardwareConfChecker(),
        GatewayProxyChecker(),
        OSInfraChecker(),
        ASTCodeChecker()
    ]

    all_findings = []
    print("\n[*] Starting audit scopes...")
    for checker in checkers:
        print(f"    -> Running checker: {checker.name} ...")
        findings = checker.run(config)
        all_findings.extend(findings)

    # 3. Compute Summary & Health Score
    summary = calculate_health_score(all_findings)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    report = AuditReport(
        project_name=global_cfg.get("project_name", "Odoo Audit"),
        odoo_version=global_cfg.get("odoo_version", "13.0"),
        timestamp=timestamp,
        summary=summary,
        findings=all_findings
    )

    # 4. Generate Reports & Per-Scope Revision Bundles
    print(f"\n[*] Generating structured reports into: {os.path.abspath(output_dir)}")
    generated_files = []

    # Generate dedicated per-scope folder structure and optimal configurations
    ModularBundleGenerator.generate(report, output_dir)
    print(f"    [+] Scope 01: Odoo Config Revision    -> {output_dir}/01_ODOO_CONFIG_REVISION/odoo_optimized.conf")
    print(f"    [+] Scope 02: PostgreSQL Tuning       -> {output_dir}/02_POSTGRESQL_TUNING/postgresql_optimized.conf")
    print(f"    [+] Scope 03: Gateway Nginx Alignment -> {output_dir}/03_GATEWAY_NGINX_ALIGNMENT/nginx_optimized.conf")
    print(f"    [+] Scope 04: OS Infrastructure       -> {output_dir}/04_OS_INFRASTRUCTURE/sysctl_optimized.conf")
    print(f"    [+] Scope 05: Code Remediation Guide  -> {output_dir}/05_CODE_REMEDIATION_AST/code_refactoring_guide.md")

    if output_format in ("markdown", "all"):
        md_path = os.path.join(output_dir, "audit_report.md")
        MarkdownReporter.generate(report, md_path)
        generated_files.append(md_path)
        print(f"    [+] Master Markdown Report            -> {md_path}")

    if output_format in ("json", "all"):
        json_path = os.path.join(output_dir, "audit_report.json")
        JSONReporter.generate(report, json_path)
        generated_files.append(json_path)
        print(f"    [+] Master JSON Report                -> {json_path}")

    if output_format in ("ai_prompt", "all"):
        ai_dir = os.path.join(output_dir, "06_AI_PROMPT_PAYLOAD")
        os.makedirs(ai_dir, exist_ok=True)
        ai_path = os.path.join(ai_dir, "ai_prompt_payload.md")
        AIPromptGenerator.generate(report, ai_path)
        AIPromptGenerator.generate(report, os.path.join(output_dir, "ai_prompt_payload.md"))
        print(f"    [+] AI Prompt Ready                   -> {ai_path}")


    # 5. Display Console Summary Card
    print("\n" + "=" * 70)
    print(f"  AUDIT RESULT: Health Score {summary.health_score} / 100  (Grade {summary.grade} - {summary.status_label})")
    print("=" * 70)
    print(f"  Total Checks : {summary.total_checks}")
    print(f"  Passed       : {summary.passed}")
    print(f"  Critical     : {summary.critical_count} (Immediate Action Required)")
    print(f"  Warning      : {summary.warning_count}")
    print(f"  Info         : {summary.info_count}")
    print("=" * 70)

    # CI/CD Fail Condition
    if args.fail_on_critical or config.get("audit_scopes", {}).get("integrations", {}).get("ci_cd_exit_code", False):
        if summary.critical_count > 0:
            print(f"\n[!] CI/CD Check FAILED: {summary.critical_count} critical issue(s) detected.")
            sys.exit(1)

    print("\n[✓] Audit successfully completed with Zero-Production-Impact.\n")


if __name__ == "__main__":
    main()
