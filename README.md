# 🛡️ DH Odoo Performance & Code Audit Engine (`dh_odoo_audit`)

[![Python 3.7+](https://img.shields.io/badge/python-3.7+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Odoo 13.0](https://img.shields.io/badge/odoo-13.0-714B67.svg?logo=odoo&logoColor=white)](https://www.odoo.com/)
[![Impact: Zero-Production-Impact](https://img.shields.io/badge/impact-zero--production--impact-brightgreen.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**DH Odoo Audit Engine (OPCAE)** adalah mesin audit dan diagnostik otomatis untuk infrastruktur, gateway reverse proxy, konfigurasi database, serta analisis kode statis Python (AST) modul kustom Odoo 13.

> 💡 **Lebih dari Sekadar Rekomendasi Konfigurasi:**  
> Alat ini dirancang tidak hanya untuk menghasilkan cetak biru (*blueprint*) konfigurasi Odoo yang optimal, melainkan **mendiagnosis secara presisi akar masalah (*root cause analysis*) di balik tingginya latensi transaksi, bottleneck komputasi, lonjakan utilisasi CPU, konsumsi memori berlebih, hingga fenomena *worker starvation*.**

---

## 🎯 Nilai Tambah: Diagnostik Presisi Bottleneck & Degradasi Performa Sistem ERP

Banyak organisasi berasumsi bahwa kendala latensi tinggi dan ketidakresponsifan Odoo dapat diselesaikan semata-mata dengan melakukan *vertical scaling* (menambah alokasi vCPU dan RAM). Namun pada praktiknya, **sebagian besar degradasi performa bermula dari inefisiensi arsitektur kode dan miskonfigurasi konkurensi**. 

Engine ini bertindak sebagai alat inspeksi mendalam untuk mengidentifikasi dan memetakan faktor-faktor determinan tersebut:

```
                  ┌─────────────────────────────────────────────────────────┐
                  │    FAKTOR DETERMINAN BOTTLENECK & DEGRADASI PERFORMA    │
                  └────────────────────────────┬────────────────────────────┘
                                               │
     ┌──────────────────────┬──────────────────┴────────────────┬──────────────────────┐
     ▼                      ▼                                   ▼                      ▼
[ Algoritma ORM & N+1 ] [ Row-Locking & Recompute ]   [ Concurrency Starvation ] [ Gateway Bottleneck ]
Eksplosi round-trip     Eskalasi lock database &      Thread blocking pada mode  Exhaustion worker pool
query di dalam iterasi  kaskade evaluasi komputasi    single-process & cron race akibat mixed traffic
```

### 1. 🔍 Diagnostik Lapisan Logika ORM (AST Static Code Inspection)
* **Skrip Eksekutor:** [`dh_odoo_audit/checkers/ast_code.py`](./dh_odoo_audit/checkers/ast_code.py) (Kelas: `ASTCodeChecker`, `OdooASTVisitor`)
* **Eksplosi Query N+1:** Mendeteksi pemanggilan `.search()` atau `.browse()` di dalam blok iterasi `for` yang melipatgandakan beban round-trip query ke PostgreSQL secara eksponensial untuk satu aksi transaksi.
* **Eskalasi Row-Lock & Kaskade Komputasi Ulang:** Mengidentifikasi pemanggilan mutasi data (`.write()` / `.create()`) yang tidak menerapkan pola batching, memicu penguncian baris (*row lock*) beruntun dan evaluasi ulang *compute fields* yang tidak perlu.
* **Inefisiensi Alokasi Memori Recordset:** Menemukan anti-pattern `len(search())` yang memaksa pemuatan seluruh recordset ke memori Python hanya untuk mengevaluasi eksistensi atau kuantitas data alih-alih memanfaatkan `search_count()`.

### 2. ⚡ Diagnostik Manajemen Konkurensi & Worker Starvation
* **Skrip Eksekutor:** [`dh_odoo_audit/checkers/hardware_conf.py`](./dh_odoo_audit/checkers/hardware_conf.py) (Kelas: `HardwareConfChecker`)
* **Thread Blocking pada Single-Process Mode (`workers = 0`):** Mengidentifikasi instans Odoo yang berjalan tanpa multiprosesing gevent, di mana satu request komputasi intensif (misal export data atau kalkulasi laporan) akan **memblokir antrean request pengguna lain secara menyeluruh**.
* **Kontensi Sumber Daya Antara Worker HTTP & Scheduled Actions:** Memvalidasi rasio `max_cron_threads` terhadap kapasitas CPU agar proses latar belakang (*background jobs*) tidak memonopoli siklus CPU pengguna interaktif.
* **Allokasi Memori Tanpa Batas (*Unbounded Memory Bloat*):** Mendeteksi ketiadaan batas memori soft/hard yang berpotensi memicu terminasi paksa proses oleh Linux *OOM-Killer*.

### 3. 🌐 Diagnostik Web Gateway & Penanganan Trafik Reverse Proxy
* **Skrip Eksekutor:** [`dh_odoo_audit/checkers/gateway_proxy.py`](./dh_odoo_audit/checkers/gateway_proxy.py) (Kelas: `GatewayProxyChecker`)
* **Saturasi Worker Akibat Mixed Longpolling Traffic:** Memverifikasi ketiadaan isolasi port asinkron `8072`, yang menyebabkan trafik polling chat dan notifikasi real-time menyerap alokasi worker transaksi HTTP reguler (8069).
* **Asimetri Ambang Batas Timeout:** Mengidentifikasi ketidaksinkronan batas waktu respons antara Nginx dan Odoo yang memicu false *504 Gateway Timeout* sebelum transaksi selesai diproses.
* **Proteksi Akses Sensitif & Rate Limiting:** Memeriksa blokade endpoint kritis `/web/database/manager` dan rate-limiting `/web/login`.

### 4. 🐘 Diagnostik I/O Subsistem Basis Data & Kernel Paging
* **Skrip Eksekutor:** [`dh_odoo_audit/checkers/hardware_conf.py`](./dh_odoo_audit/checkers/hardware_conf.py) & [`dh_odoo_audit/checkers/os_infra.py`](./dh_odoo_audit/checkers/os_infra.py) (Kelas: `OSInfraChecker`)
* **Sub-Optimal Query Planner Heuristics:** Mengidentifikasi parameter `random_page_cost = 4.0` (default era HDD) yang menghalangi perencana query PostgreSQL memanfaatkan indeks secara optimal pada media penyimpanan modern berbasis NVMe/SSD.
* **Penurunan Throughput Akibat Agresivitas Kernel Swapping:** Memeriksa nilai `vm.swappiness` pada level OS untuk mencegah kernel Linux memindahkan segmen memori aktif ERP ke partisi swap.

---

### 🗺️ Matriks Pemetaan Fitur Diagnostik ke Modul Script

| Domain Diagnostik | Skrip / Modul Sumber | Kelas Utama | Fokus Analisis & Mitigasi Risiko |
| :--- | :--- | :--- | :--- |
| **Logika Kode ORM** | [`ast_code.py`](./dh_odoo_audit/checkers/ast_code.py) | `ASTCodeChecker` | Mencegah N+1 query, locking cascade, dan memory recordset bloat. |
| **Worker & Konkurensi** | [`hardware_conf.py`](./dh_odoo_audit/checkers/hardware_conf.py) | `HardwareConfChecker` | Mencegah thread blocking, CPU contention, dan OOM-kill. |
| **Web Gateway & Nginx** | [`gateway_proxy.py`](./dh_odoo_audit/checkers/gateway_proxy.py) | `GatewayProxyChecker` | Mencegah chat hijacking di HTTP pool, 502/504 error, dan celah brute force. |
| **Basis Data & OS** | [`os_infra.py`](./dh_odoo_audit/checkers/os_infra.py) | `OSInfraChecker` | Mencegah full table scan I/O bottleneck dan latency disk swap. |
| **Scoring & Grading** | [`scoring.py`](./dh_odoo_audit/core/scoring.py) | `calculate_health_score` | Menghitung indeks kesehatan sistem secara kuantitatif (0–100). |
| **Konfigurasi Optimal**| [`modular_bundle_gen.py`](./dh_odoo_audit/reporters/modular_bundle_gen.py) | `ModularBundleGenerator`| Meracik file revisi siap deploy per-scope (`.conf`). |


## 📑 Daftar Isi

- [Nilai Tambah: Diagnostik Presisi Bottleneck & Degradasi Performa Sistem ERP](#-nilai-tambah-diagnostik-presisi-bottleneck--degradasi-performa-sistem-erp)
- [Matriks Pemetaan Fitur Diagnostik ke Modul Script](#️-matriks-pemetaan-fitur-diagnostik-ke-modul-script)
- [Fitur Utama](#-fitur-utama)

- [Arsitektur & Scope Audit](#-arsitektur--scope-audit)
- [Struktur Output & Rekomendasi Optimal](#-struktur-output--rekomendasi-optimal)
- [Instalasi & Penggunaan Cepat](#-instalasi--penggunaan-cepat)
- [Konfigurasi (`audit_config.yaml`)](#-konfigurasi-audit_configyaml)
- [Integrasi CI/CD Pipeline](#-integrasi-cicd-pipeline)
- [Fitur AI Prompt Generator](#-fitur-ai-prompt-generator)
- [Mengabaikan Aturan AST (`audit:ignore`)](#-mengabaikan-aturan-ast-auditignore)
- [Lisensi](#-lisensi)


---

## 🌟 Fitur Utama

* 🛡️ **Zero-Production-Impact (Safe by Default):** Murni membaca file teks lokal (`.conf`, `.py`, dan log bertahap).
* ⚙️ **Kalkulasi Hardware Otomatis:** Mengkalkulasi formula `workers = (CPU * 2) + 1` dan alokasi batas memori soft/hard berdasarkan resource CPU/RAM aktual.
* 🌐 **Web Gateway & Nginx Cross-Validation:** Memverifikasi keselarasan reverse proxy Nginx terhadap Odoo (`proxy_mode`, rute pemisahan port longpolling `8072`, buffer 128k, dan timeout simetris).
* 🔒 **Nginx Security Hardening Audit:** Memeriksa proteksi endpoint sensitif `/web/database/manager`, rate limiting anti-brute-force `/web/login`, HTTP security headers (anti-clickjacking & nosniff), penyembunyian versi (`server_tokens off`), dan pemblokiran dotfiles (.git/.env).
* 🐘 **PostgreSQL 13 Tuning Audit:** Mendeteksi parameter vanilla yang menghambat performa (misal: `random_page_cost = 4.0` pada media SSD, alokasi `shared_buffers`).
* 🐍 **AST ORM Anti-Pattern Detector:** Menganalisis file Python modul kustom menggunakan AST untuk menemukan N+1 query (`search in loop`), unbatched `write()`, dan `len(search())`.
* 📦 **Modular Configuration Bundles:** Menghasilkan file konfigurasi revisi optimal siap pakai (`odoo_optimized.conf`, `postgresql_optimized.conf`, `nginx_optimized.conf`, dll).
* 🤖 **AI-Ready Prompt Payload:** Menghasilkan prompt terstruktur dan tersanitasi otomatis untuk konsultasi lanjutan ke model AI (Gemini, Claude, ChatGPT).

---

## 🔍 Arsitektur & Scope Audit

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    DH Odoo Audit Engine (OPCAE)                         │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
     ┌───────────────────────────────┼──────────────────────────────┐
     ▼                               ▼                              ▼
[ 1. System & Conf ]    [ 2. Gateway & Security ]     [ 3. AST Code Linter ]
  • CPU/RAM vs Workers    • Longpolling port 8072       • search() in loop
  • Memory limits         • DB Manager & Login Rate     • write() in loop
  • PostgreSQL tuning     • Security Headers & Buffers  • len(search())
```


---

## 📁 Struktur Output & Rekomendasi Optimal

Setiap kali audit dijalankan, sistem secara otomatis mengelompokkan hasil temuan dan **file konfigurasi revisi optimal siap pakai** ke dalam folder khusus per-scope:

```text
audit_reports/
├── 00_EXECUTIVE_SUMMARY.md               # Ringkasan Eksekutif & Health Score (0-100)
├── 01_ODOO_CONFIG_REVISION/              # [Untuk Sysadmin / ERP Admin]
│   ├── audit_findings.md                 # Analisis temuan odoo.conf
│   └── odoo_optimized.conf               # File konfigurasi Odoo hasil kalkulasi optimal
├── 02_POSTGRESQL_TUNING/                 # [Untuk Database Administrator]
│   ├── audit_findings.md                 # Analisis temuan PostgreSQL 13
│   └── postgresql_optimized.conf         # File postgresql.conf optimal untuk SSD & RAM
├── 03_GATEWAY_NGINX_ALIGNMENT/           # [Untuk DevOps / Network Engineer]
│   ├── audit_findings.md                 # Analisis sinkronisasi Nginx vs Odoo
│   └── nginx_optimized.conf              # File Nginx siap pakai (Port 8072, buffers 128k)
├── 04_OS_INFRASTRUCTURE/                 # [Untuk System Engineer]
│   ├── audit_findings.md                 # Analisis kapasitas disk & swappiness
│   └── sysctl_optimized.conf             # Konfigurasi kernel Linux (swappiness=10)
├── 05_CODE_REMEDIATION_AST/              # [Untuk Tim Programmer Odoo]
│   ├── audit_findings.md                 # Daftar temuan anti-pattern per file
│   └── code_refactoring_guide.md         # Panduan revisi Before vs After lengkap
├── 06_AI_PROMPT_PAYLOAD/                 # [Untuk AI Assistant]
│   └── ai_prompt_payload.md              # Payload siap tempel ke LLM
├── audit_report.md                       # Laporan master lengkap format Markdown
└── audit_report.json                     # Laporan master format JSON (Machine-readable)
```

---

## 🚀 Instalasi & Penggunaan Cepat

### 1. Kloning Repository
```bash
git clone https://github.com/your-org/dh_odoo_audit.git
cd dh_odoo_audit
```

### 2. Instalasi Dependensi
Alat ini dirancang sangat ringan dan minim dependensi:
```bash
pip install -r requirements.txt
```
*(Catatan: Tool ini memiliki mekanisme fallback mandiri jika pustaka `psutil` tidak tersedia).*

### 3. Menjalankan Audit
```bash
# Menjalankan audit default
python audit_cli.py

# Menjalankan dengan konfigurasi custom
python audit_cli.py -c /path/to/custom_audit_config.yaml

# Menentukan folder output khusus
python audit_cli.py -o ./my_audit_results
```

---

## ⚙️ Konfigurasi (`audit_config.yaml`)

Sesuaikan path file target pada `audit_config.yaml`:

```yaml
global_settings:
  project_name: "Odoo Production Audit"
  odoo_version: "13.0"
  odoo_custom_addons_path: "/opt/odoo/custom_addons"
  odoo_conf_path: "/etc/odoo/odoo.conf"
  nginx_conf_path: "/etc/nginx/sites-enabled/odoo.conf"
  postgres_conf_path: "/etc/postgresql/13/main/postgresql.conf"
  output_format: "all"
  output_dir: "./audit_reports"

audit_scopes:
  system_hardware_and_config:
    enabled: true
  gateway_and_odoo_alignment:
    enabled: true
  static_code_analysis:
    enabled: true
    rules:
      detect_search_in_loop: true
      detect_write_in_loop: true
      detect_len_search_anti_pattern: true
  infrastructure_and_os:
    enabled: true
```

---

## 🔄 Integrasi CI/CD Pipeline

Anda dapat menjadikan alat ini sebagai **Quality Gate** pada pipeline Git. Jika terdapat isu berkategori `CRITICAL`, proses build/merge request dapat otomatis digagalkan.

### GitHub Actions (`.github/workflows/odoo-audit.yml`)
```yaml
name: Odoo Code & Performance Audit

on: [push, pull_request]

jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.8'
      - name: Install Dependencies
        run: pip install -r requirements.txt
      - name: Run DH Odoo Audit Engine
        run: python audit_cli.py --fail-on-critical
```

---

## 🤖 Fitur AI Prompt Generator

Untuk menganalisis temuan lebih dalam menggunakan AI:
1. Jalankan audit.
2. Buka file [`audit_reports/06_AI_PROMPT_PAYLOAD/ai_prompt_payload.md`](./audit_reports/06_AI_PROMPT_PAYLOAD/ai_prompt_payload.md).
3. Salin seluruh isinya langsung ke ChatGPT, Claude, atau Gemini.

File tersebut telah dirancang khusus dengan:
- **Role Persona Terstruktur:** Menginstruksikan AI bertindak sebagai *Principal Odoo 13 Architect*.
- **Data Masking Otomatis:** Password database dan master admin otomatis disamarkan (`********`).
- **Konteks Hardware & Kode Asli:** Menyajikan potongan kode bermasalah secara presisi sehingga AI memberikan solusi tanpa halusinasi.

---

## 🛡️ Mengabaikan Aturan AST (`audit:ignore`)

Jika ada baris kode tertentu yang memang sengaja tidak di-batch dan ingin dikecualikan dari audit, tambahkan komentar `# audit:ignore`:

```python
# Akan dilewati oleh AST scanner:
orders = self.env['sale.order'].search([('state', '=', 'draft')]) # audit:ignore
```

---

## 📄 Lisensi

Didistribusikan di bawah lisensi **MIT License**. Lihat `LICENSE` untuk informasi lebih lanjut.
