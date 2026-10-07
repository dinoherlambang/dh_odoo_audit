"""
Configuration loader and validator for dh_odoo_audit.
"""

import os
import yaml
from typing import Dict, Any


DEFAULT_CONFIG: Dict[str, Any] = {
    "global_settings": {
        "project_name": "Odoo Production Audit",
        "odoo_version": "13.0",
        "odoo_custom_addons_path": "./custom_addons",
        "odoo_conf_path": "/etc/odoo/odoo.conf",
        "nginx_conf_path": "/etc/nginx/sites-enabled/odoo.conf",
        "postgres_conf_path": "/etc/postgresql/13/main/postgresql.conf",
        "postgres_log_path": "/var/log/postgresql/postgresql-13-main.log",
        "odoo_log_path": "/var/log/odoo/odoo-server.log",
        "output_format": "all",
        "output_dir": "./audit_reports",
        "ai_prompt_settings": {
            "mask_passwords": True,
            "include_code_snippets": True,
            "target_ai_task": "deep_remediation"
        }
    },
    "audit_scopes": {
        "system_hardware_and_config": {"enabled": True},
        "gateway_and_odoo_alignment": {"enabled": True},
        "static_code_analysis": {"enabled": True},
        "infrastructure_and_os": {"enabled": True},
        "log_stream_analysis": {"enabled": False},
        "db_metadata_inspection": {"enabled": False},
        "auto_generator": {"enabled": False},
        "integrations": {"enabled": False}
    }
}


def load_config(config_path: str) -> Dict[str, Any]:
    """Load and validate the audit configuration YAML."""
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found at: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        user_config = yaml.safe_load(f) or {}

    merged = DEFAULT_CONFIG.copy()

    if "global_settings" in user_config:
        merged["global_settings"].update(user_config["global_settings"])

    if "audit_scopes" in user_config:
        for scope, settings in user_config["audit_scopes"].items():
            if scope in merged["audit_scopes"] and isinstance(settings, dict):
                merged["audit_scopes"][scope].update(settings)
            else:
                merged["audit_scopes"][scope] = settings

    return merged
