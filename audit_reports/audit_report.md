# 🛡️ DH Odoo Performance & Code Audit Engine (OPCAE) Report
**Proyek:** Odoo Production Audit | **Target:** Odoo 13.0 | **Tanggal:** 2026-10-07 20:42:05

---

## 1. Executive Summary & Health Score

| Health Score | Grade | Status | Total Checks | Critical | Warning | Info | Passed |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **0 / 100** | **Grade D** | 🔴 **CRITICAL RISK** | 23 | 6 | 12 | 5 | 0 |

## 2. Server & Database Configuration Audit

| Code | Severity | Judul Temuan | Nilai Saat Ini | Target Ideal | Rekomendasi |
| :--- | :---: | :--- | :--- | :--- | :--- |
| `HW-INFO` | ℹ️ **INFO** | Spesifikasi Hardware Terdeteksi | `16 Cores, 13.7 GB RAM` | `Informational` | Server memiliki 16 vCPU Cores dan 13.7 GB Total RAM. |
| `CONF-WORKERS-ZERO` | 🔴 **CRITICAL** | Odoo Berjalan dalam Single-Process Mode | `0` | `33` | Set 'workers = 33' pada odoo.conf. |
| `CONF-MEM-LIMIT-UNSET` | 🟡 **WARNING** | Batas Memori Odoo Belum Dikonfigurasi | `soft=0, hard=0` | `soft=2147483648 (2GB), hard=2684354560 (2.5GB)` | Tentukan 'limit_memory_soft = 2147483648' dan 'limit_memory_hard = 2684354560'. |
| `PG-RANDOM-PAGE-COST` | 🟡 **WARNING** | PostgreSQL random_page_cost Masih Nilai Default HDD | `4.0` | `1.1 (SSD/NVMe)` | Ubah 'random_page_cost = 1.1' di postgresql.conf untuk server media SSD. |
| `PG-SHARED-BUFFERS-DEFAULT` | 🟡 **WARNING** | PostgreSQL shared_buffers Masih Nilai Default Vanilla | `128MB` | `3.4GB (25% Total RAM)` | Set 'shared_buffers = 3GB' di postgresql.conf. |

## 3. Web Gateway & Nginx Alignment Audit

| Code | Severity | Judul Temuan | Target Solusi |
| :--- | :---: | :--- | :--- |
| `GATEWAY-PROXY-MODE-OFF` | 🔴 **CRITICAL** | **Odoo proxy_mode Bernilai False di Balik Nginx**<br>Odoo berjalan di balik reverse proxy tetapi 'proxy_mode = True' belum diset. Redirect HTTPS akan bermasalah (Mixed Content). | Tambahkan 'proxy_mode = True' di bagian [options] odoo.conf. |
| `GATEWAY-NGINX-HEADERS-MISSING` | 🟡 **WARNING** | **Header X-Forwarded-* Kurang Lengkap di Nginx**<br>Nginx belum meneruskan X-Forwarded-Host atau X-Forwarded-Proto $scheme ke Odoo. | Tambahkan 'proxy_set_header X-Forwarded-Host $host;' dan 'proxy_set_header X-Forwarded-Proto $scheme;'. |
| `GATEWAY-LONGPOLLING-MISSING` | 🔴 **CRITICAL** | **Rute Longpolling (Port 8072) Belum Terpisah di Nginx**<br>Nginx tidak memisahkan rute /longpolling ke port 8072. Traffic live chat dan bus notification akan membanjiri HTTP worker utama (port 8069). | Konfigurasikan upstream terpisah untuk port 8072 dan buat blok 'location /longpolling { proxy_pass http://odoochat; }'. |
| `GATEWAY-TIMEOUT-ASYMMETRY` | 🟡 **WARNING** | **Nginx proxy_read_timeout Lebih Kecil dari limit_time_real Odoo**<br>Nginx timeout (60s) < Odoo timeout (120s). User akan melihat 504 Gateway Timeout saat Odoo masih memproses laporan. | Set 'proxy_read_timeout 300s;' pada konfigurasi Nginx. |
| `GATEWAY-BUFFERS-TOO-SMALL` | 🟡 **WARNING** | **Buffer Nginx Belum Disesuaikan untuk Header Odoo**<br>Odoo memiliki cookie sesi yang besar. Buffer default Nginx rawan memicu '502 Bad Gateway: upstream sent too big header'. | Tambahkan 'proxy_buffer_size 128k;' dan 'proxy_buffers 16 64k;'. |
| `GATEWAY-BODY-SIZE-LOW` | 🟡 **INFO** | **client_max_body_size Terlalu Kecil**<br>Batas upload 1MB mungkin kurang untuk impor data besar. | >= 50M |
| `GATEWAY-GZIP-OFF` | 🟡 **WARNING** | **Gzip Compression Belum Aktif di Nginx**<br>Kompresi gzip menghemat hingga 70% bandwidth web client Odoo untuk file JS dan CSS bundle. | Aktifkan 'gzip on;' dan sertakan mime type text/css application/javascript application/json. |
| `GATEWAY-SEC-DB-MANAGER-EXPOSED` | 🔴 **CRITICAL** | **Database Manager Odoo Terbuka ke Publik**<br>Endpoint /web/database/manager dan selector tidak dilindungi oleh restriksi IP atau deny all. Siapa pun di internet dapat menghapus, menduplikasi, atau mengunduh backup database jika master password lemah. | Tambahkan proteksi IP pada Nginx: 'location /web/database/manager { allow 10.0.0.0/8; deny all; ... }' atau blokir akses eksternal. |
| `GATEWAY-SEC-LOGIN-BRUTEFORCE` | 🟡 **WARNING** | **Halaman Login (/web/login) Rentan Serangan Brute-Force**<br>Nginx belum menerapkan rate limiting pada endpoint /web/login. Server berisiko terhadap credential stuffing dan serangan brute-force password. | Definisikan 'limit_req_zone $binary_remote_addr zone=odoo_login:10m rate=5r/m;' dan terapkan pada 'location = /web/login'. |
| `GATEWAY-SEC-HEADERS-MISSING` | 🟡 **WARNING** | **HTTP Security Headers Kurang Lengkap**<br>Nginx belum mengirimkan header X-Frame-Options (anti-clickjacking) atau X-Content-Type-Options (anti-MIME-sniffing). | Tambahkan 'add_header X-Frame-Options SAMEORIGIN;' dan 'add_header X-Content-Type-Options nosniff;'. |
| `GATEWAY-SEC-SERVER-TOKENS` | 🟡 **WARNING** | **Versi Nginx Terekspos ke Publik (server_tokens on)**<br>Nginx membocorkan nomor versinya pada header HTTP 'Server' dan halaman error default. Hal ini mempermudah penyerang menargetkan CVE spesifik. | Tambahkan 'server_tokens off;' di dalam blok http atau server Nginx. |
| `GATEWAY-SEC-DOTFILES-OPEN` | 🟡 **INFO** | **Akses File Tersembunyi (.git, .env) Belum Diblokir**<br>Nginx belum secara eksplisit memblokir request ke file atau direktori tersembunyi berawalan titik (seperti .git, .env, .htaccess). | Tambahkan blok: 'location ~ /\. { deny all; access_log off; log_not_found off; }'. |

## 4. Static Code Analysis (Custom Addons)

### [AST-SEARCH-IN-LOOP] N+1 Query: Method .search() di dalam Loop for
- **Severity:** 🔴 `CRITICAL`
- **File:** `./sample_addons\custom_sale\models\sale_order.py` (Line 12)
- **Penjelasan:** Pemanggilan .search() di dalam perulangan for memicu ratusan round-trip query ke PostgreSQL.
- **Potongan Kode:**
```python
comms = self.env['sale.commission'].search([('partner_id', '=', order.user_id.partner_id.id)])
```
- **Saran Solusi:** Kumpulkan ID terlebih dahulu lalu lakukan satu kali search dengan operator 'in' di luar loop.

### [AST-LEN-SEARCH] Anti-Pattern len(search()) Terdeteksi
- **Severity:** 🟡 `WARNING`
- **File:** `./sample_addons\custom_sale\models\sale_order.py` (Line 19)
- **Penjelasan:** Menggunakan len() pada search() menarik seluruh recordset ke memori Python hanya untuk menghitung jumlah.
- **Potongan Kode:**
```python
if len(self.env['sale.order'].search([('state', '=', 'draft')])) > 0:
```
- **Saran Solusi:** Gunakan method search_count() untuk menghitung jumlah baris langsung di PostgreSQL.

### [AST-WRITE-IN-LOOP] Unbatched Database Write: .write() di dalam Loop for
- **Severity:** 🔴 `CRITICAL`
- **File:** `./sample_addons\custom_sale\models\sale_order.py` (Line 22)
- **Penjelasan:** Memanggil .write() pada setiap iterasi memicu evaluasi recompute dan row-lock berulang kali.
- **Potongan Kode:**
```python
order.write({'state': 'confirmed'})
```
- **Saran Solusi:** Gunakan batching: recordset.write(...) di luar perulangan.

## 5. OS & Infrastructure Audit

- ℹ️ **Pemeriksaan Swappiness Dilewati:** /proc/sys/vm/swappiness tidak tersedia (Lingkungan Windows/Container). *(Rekomendasi: Informational)*
- 🟡 **Kapasitas Sisa Storage Mendekati Batas:** Sisa storage tersisa 16.2% (76.9 GB). *(Rekomendasi: Sisa > 20%)*
