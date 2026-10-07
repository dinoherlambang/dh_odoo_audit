"""
Static AST Code Checker for Odoo Custom Addons.
Scans Python files for ORM performance anti-patterns without runtime execution.
"""

import os
import ast
from typing import List, Dict, Any, Optional
from dh_odoo_audit.checkers.base import BaseChecker
from dh_odoo_audit.core.models import Finding, Severity


class OdooASTVisitor(ast.NodeVisitor):
    def __init__(self, file_path: str, lines: List[str], active_rules: Dict[str, bool]):
        self.file_path = file_path
        self.lines = lines
        self.active_rules = active_rules
        self.findings: List[Finding] = []
        self.loop_stack: List[ast.For] = []

    def _is_ignored(self, lineno: int, rule_code: str) -> bool:
        if 1 <= lineno <= len(self.lines):
            line_text = self.lines[lineno - 1]
            if "# audit:ignore" in line_text:
                if f"# audit:ignore:{rule_code}" in line_text or "# audit:ignore" in line_text:
                    return True
        return False

    def visit_For(self, node: ast.For):
        self.loop_stack.append(node)
        self.generic_visit(node)
        self.loop_stack.pop()

    def visit_Call(self, node: ast.Call):
        # 1. Detect len(search())
        if self.active_rules.get("detect_len_search_anti_pattern", True):
            if isinstance(node.func, ast.Name) and node.func.id == "len" and node.args:
                arg = node.args[0]
                if isinstance(arg, ast.Call) and isinstance(arg.func, ast.Attribute) and arg.func.attr == "search":
                    if not self._is_ignored(node.lineno, "AST-LEN-SEARCH"):
                        line_content = self.lines[node.lineno - 1].strip() if 1 <= node.lineno <= len(self.lines) else ""
                        self.findings.append(Finding(
                            scope="static_code_analysis",
                            code="AST-LEN-SEARCH",
                            title="Anti-Pattern len(search()) Terdeteksi",
                            severity=Severity.WARNING,
                            description="Menggunakan len() pada search() menarik seluruh recordset ke memori Python hanya untuk menghitung jumlah.",
                            file_path=self.file_path,
                            line_number=node.lineno,
                            current_value="len(env[...].search(...))",
                            target_value="env[...].search_count(...)",
                            snippet_before=line_content,
                            snippet_after=line_content.replace(".search(", ".search_count(").replace("len(", ""),
                            recommendation="Gunakan method search_count() untuk menghitung jumlah baris langsung di PostgreSQL."
                        ))

        # Check operations inside loop
        if self.loop_stack:
            # 2. Detect search() / browse() inside for-loop
            if self.active_rules.get("detect_search_in_loop", True):
                if isinstance(node.func, ast.Attribute) and node.func.attr in ("search", "browse"):
                    if not self._is_ignored(node.lineno, "AST-SEARCH-IN-LOOP"):
                        line_content = self.lines[node.lineno - 1].strip() if 1 <= node.lineno <= len(self.lines) else ""
                        self.findings.append(Finding(
                            scope="static_code_analysis",
                            code="AST-SEARCH-IN-LOOP",
                            title=f"N+1 Query: Method .{node.func.attr}() di dalam Loop for",
                            severity=Severity.CRITICAL,
                            description=f"Pemanggilan .{node.func.attr}() di dalam perulangan for memicu ratusan round-trip query ke PostgreSQL.",
                            file_path=self.file_path,
                            line_number=node.lineno,
                            current_value=f".{node.func.attr}() inside loop",
                            target_value="Batch search dengan operator 'in' di luar loop",
                            snippet_before=line_content,
                            recommendation="Kumpulkan ID terlebih dahulu lalu lakukan satu kali search dengan operator 'in' di luar loop."
                        ))

            # 3. Detect write() / create() inside for-loop
            if self.active_rules.get("detect_write_in_loop", True):
                if isinstance(node.func, ast.Attribute) and node.func.attr in ("write", "create"):
                    if not self._is_ignored(node.lineno, "AST-WRITE-IN-LOOP"):
                        line_content = self.lines[node.lineno - 1].strip() if 1 <= node.lineno <= len(self.lines) else ""
                        self.findings.append(Finding(
                            scope="static_code_analysis",
                            code="AST-WRITE-IN-LOOP",
                            title=f"Unbatched Database Write: .{node.func.attr}() di dalam Loop for",
                            severity=Severity.CRITICAL,
                            description=f"Memanggil .{node.func.attr}() pada setiap iterasi memicu evaluasi recompute dan row-lock berulang kali.",
                            file_path=self.file_path,
                            line_number=node.lineno,
                            current_value=f".{node.func.attr}() inside loop",
                            target_value="records.write(...) sekali di luar loop",
                            snippet_before=line_content,
                            recommendation=f"Gunakan batching: recordset.{node.func.attr}(...) di luar perulangan."
                        ))

        self.generic_visit(node)


class ASTCodeChecker(BaseChecker):
    """Recursively parses and audits custom Odoo Python addons using AST."""

    def __init__(self):
        super().__init__("static_code_analysis")

    def run(self, config: Dict[str, Any]) -> List[Finding]:
        findings: List[Finding] = []
        global_cfg = config.get("global_settings", {})
        scope_cfg = config.get("audit_scopes", {}).get("static_code_analysis", {})

        if not scope_cfg.get("enabled", True):
            return findings

        addons_path = global_cfg.get("odoo_custom_addons_path", "")
        if not addons_path or not os.path.exists(addons_path):
            findings.append(Finding(
                scope=self.name,
                code="AST-PATH-NOT-FOUND",
                title="Folder Custom Addons Tidak Ditemukan",
                severity=Severity.WARNING,
                description=f"Path folder custom addons di '{addons_path}' tidak ditemukan.",
                current_value="Not Found",
                target_value="Valid Directory"
            ))
            return findings

        active_rules = scope_cfg.get("rules", {})
        total_py_scanned = 0

        for root, _, files in os.walk(addons_path):
            for file in files:
                if file.endswith(".py"):
                    total_py_scanned += 1
                    file_path = os.path.join(root, file)
                    self._audit_file(file_path, active_rules, findings)

        findings.append(Finding(
            scope=self.name,
            code="AST-SUMMARY",
            title="Ringkasan Pemindaian AST",
            severity=Severity.INFO,
            description=f"Berhasil memindai {total_py_scanned} file Python pada custom addons.",
            current_value=f"{total_py_scanned} files",
            target_value="Informational"
        ))

        return findings

    def _audit_file(self, file_path: str, active_rules: Dict[str, bool], findings: List[Finding]):
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                lines = content.splitlines()

            tree = ast.parse(content, filename=file_path)
            visitor = OdooASTVisitor(file_path, lines, active_rules)
            visitor.visit(tree)
            findings.extend(visitor.findings)
        except SyntaxError as e:
            findings.append(Finding(
                scope=self.name,
                code="AST-SYNTAX-ERROR",
                title=f"Syntax Error pada {os.path.basename(file_path)}",
                severity=Severity.WARNING,
                description=str(e),
                file_path=file_path,
                line_number=e.lineno
            ))
        except Exception:
            pass
