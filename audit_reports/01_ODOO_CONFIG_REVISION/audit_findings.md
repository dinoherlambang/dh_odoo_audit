# 📋 Audit Konfigurasi Odoo (odoo.conf)
Spesifikasi Server: **16 vCPU Cores**, **13.7 GB RAM**

## Temuan Parameter:
| Code | Severity | Parameter | Nilai Saat Ini | Target Revisi | Rekomendasi |
| :--- | :---: | :--- | :--- | :--- | :--- |
| `CONF-WORKERS-ZERO` | **CRITICAL** | Odoo Berjalan dalam Single-Process Mode | `0` | `33` | Set 'workers = 33' pada odoo.conf. |
| `CONF-MEM-LIMIT-UNSET` | **WARNING** | Batas Memori Odoo Belum Dikonfigurasi | `soft=0, hard=0` | `soft=2147483648 (2GB), hard=2684354560 (2.5GB)` | Tentukan 'limit_memory_soft = 2147483648' dan 'limit_memory_hard = 2684354560'. |