# SYSTEM DIRECTIVE: ODOO 13 TECHNICAL ARCHITECT & CODE SPECIALIST
Anda adalah seorang Principal Technical Architect Odoo 13 dan DevOps Performance Specialist.
Berikut adalah hasil audit sistem dan modul kustom dari server Odoo Production kami (menggunakan DH Odoo Audit Engine).
Tugas Anda adalah menganalisis akar masalah secara komprehensif, memberikan konfigurasi siap pakai, serta menulis ulang (refactor) kode modul kustom yang terdeteksi melanggar kaidah performa.

---

## 1. CONTEXT & METADATA SISTEM
- **Proyek:** Odoo Production Audit
- **Target Odoo Version:** 13.0
- **Audit Health Score:** 0 / 100 (Grade: D - CRITICAL RISK)
- **Statistik Masalah:** 6 Critical, 13 Warning

## 2. SERVER & GATEWAY CONFIGURATION MISMATCHES
- **[CONF-WORKERS-ZERO] Odoo Berjalan dalam Single-Process Mode** (CRITICAL)
  - Nilai saat ini: `0`
  - Target ideal: `33`
  - Catatan: Parameter 'workers = 0'. Odoo tidak menggunakan multiprocessing gevent. Permintaan lambat akan memblokir seluruh user.
- **[CONF-MEM-LIMIT-UNSET] Batas Memori Odoo Belum Dikonfigurasi** (WARNING)
  - Nilai saat ini: `soft=0, hard=0`
  - Target ideal: `soft=2147483648 (2GB), hard=2684354560 (2.5GB)`
  - Catatan: limit_memory_soft atau limit_memory_hard belum diatur. Risiko memory leak memakan seluruh RAM server.
- **[PG-RANDOM-PAGE-COST] PostgreSQL random_page_cost Masih Nilai Default HDD** (WARNING)
  - Nilai saat ini: `4.0`
  - Target ideal: `1.1 (SSD/NVMe)`
  - Catatan: Nilai 4.0 didesain untuk media HDD piringan lama. Query planner akan cenderung memilih sequential scan daripada index scan.
- **[PG-SHARED-BUFFERS-DEFAULT] PostgreSQL shared_buffers Masih Nilai Default Vanilla** (WARNING)
  - Nilai saat ini: `128MB`
  - Target ideal: `3.4GB (25% Total RAM)`
  - Catatan: Nilai shared_buffers 128MB terlalu kecil untuk server berukuran 13.7 GB RAM.
- **[GATEWAY-PROXY-MODE-OFF] Odoo proxy_mode Bernilai False di Balik Nginx** (CRITICAL)
  - Nilai saat ini: `proxy_mode = False`
  - Target ideal: `proxy_mode = True`
  - Catatan: Odoo berjalan di balik reverse proxy tetapi 'proxy_mode = True' belum diset. Redirect HTTPS akan bermasalah (Mixed Content).
- **[GATEWAY-NGINX-HEADERS-MISSING] Header X-Forwarded-* Kurang Lengkap di Nginx** (WARNING)
  - Nilai saat ini: `Missing Headers`
  - Target ideal: `X-Forwarded-Host & X-Forwarded-Proto present`
  - Catatan: Nginx belum meneruskan X-Forwarded-Host atau X-Forwarded-Proto $scheme ke Odoo.
- **[GATEWAY-LONGPOLLING-MISSING] Rute Longpolling (Port 8072) Belum Terpisah di Nginx** (CRITICAL)
  - Nilai saat ini: `No separate 8072 routing`
  - Target ideal: `location /longpolling -> port 8072`
  - Catatan: Nginx tidak memisahkan rute /longpolling ke port 8072. Traffic live chat dan bus notification akan membanjiri HTTP worker utama (port 8069).
- **[GATEWAY-TIMEOUT-ASYMMETRY] Nginx proxy_read_timeout Lebih Kecil dari limit_time_real Odoo** (WARNING)
  - Nilai saat ini: `nginx=60s, odoo=120s`
  - Target ideal: `nginx >= 120s (Direkomendasikan >= 300s)`
  - Catatan: Nginx timeout (60s) < Odoo timeout (120s). User akan melihat 504 Gateway Timeout saat Odoo masih memproses laporan.
- **[GATEWAY-BUFFERS-TOO-SMALL] Buffer Nginx Belum Disesuaikan untuk Header Odoo** (WARNING)
  - Nilai saat ini: `Default Buffers`
  - Target ideal: `proxy_buffers 16 64k; proxy_buffer_size 128k;`
  - Catatan: Odoo memiliki cookie sesi yang besar. Buffer default Nginx rawan memicu '502 Bad Gateway: upstream sent too big header'.
- **[GATEWAY-GZIP-OFF] Gzip Compression Belum Aktif di Nginx** (WARNING)
  - Nilai saat ini: `Off`
  - Target ideal: `gzip on;`
  - Catatan: Kompresi gzip menghemat hingga 70% bandwidth web client Odoo untuk file JS dan CSS bundle.
- **[GATEWAY-SEC-DB-MANAGER-EXPOSED] Database Manager Odoo Terbuka ke Publik** (CRITICAL)
  - Nilai saat ini: `Publicly Exposed`
  - Target ideal: `Restricted by IP or Denied`
  - Catatan: Endpoint /web/database/manager dan selector tidak dilindungi oleh restriksi IP atau deny all. Siapa pun di internet dapat menghapus, menduplikasi, atau mengunduh backup database jika master password lemah.
- **[GATEWAY-SEC-LOGIN-BRUTEFORCE] Halaman Login (/web/login) Rentan Serangan Brute-Force** (WARNING)
  - Nilai saat ini: `No rate limit`
  - Target ideal: `limit_req_zone + limit_req active`
  - Catatan: Nginx belum menerapkan rate limiting pada endpoint /web/login. Server berisiko terhadap credential stuffing dan serangan brute-force password.
- **[GATEWAY-SEC-HEADERS-MISSING] HTTP Security Headers Kurang Lengkap** (WARNING)
  - Nilai saat ini: `Missing Security Headers`
  - Target ideal: `X-Frame-Options & X-Content-Type-Options present`
  - Catatan: Nginx belum mengirimkan header X-Frame-Options (anti-clickjacking) atau X-Content-Type-Options (anti-MIME-sniffing).
- **[GATEWAY-SEC-SERVER-TOKENS] Versi Nginx Terekspos ke Publik (server_tokens on)** (WARNING)
  - Nilai saat ini: `server_tokens on/unset`
  - Target ideal: `server_tokens off;`
  - Catatan: Nginx membocorkan nomor versinya pada header HTTP 'Server' dan halaman error default. Hal ini mempermudah penyerang menargetkan CVE spesifik.

## 3. STATIC CODE (AST) PERFORMANCE ISSUES
### [Issue 1: AST-COMPUTE-NO-STORE - Computed Field Tanpa Flag store=True]
- **File:** `./sample_addons\custom_sale\models\sale_order.py` (Line: 7)
- **Severity:** `WARNING`
- **Penyebab:** Field dengan compute method tidak menyertakan store=True. Field akan dihitung ulang secara dinamis setiap kali diakses (berisiko degradasi jika ada di tree/list view).
- **Potongan Baris Kode Asli:**
```python
commission_total = fields.Float(string="Total Commission", compute="_compute_commission")
```

### [Issue 2: AST-SEARCH-IN-LOOP - N+1 Query: Method .search() di dalam Loop for]
- **File:** `./sample_addons\custom_sale\models\sale_order.py` (Line: 12)
- **Severity:** `CRITICAL`
- **Penyebab:** Pemanggilan .search() di dalam perulangan for memicu ratusan round-trip query ke PostgreSQL.
- **Potongan Baris Kode Asli:**
```python
comms = self.env['sale.commission'].search([('partner_id', '=', order.user_id.partner_id.id)])
```

### [Issue 3: AST-LEN-SEARCH - Anti-Pattern len(search()) Terdeteksi]
- **File:** `./sample_addons\custom_sale\models\sale_order.py` (Line: 19)
- **Severity:** `WARNING`
- **Penyebab:** Menggunakan len() pada search() menarik seluruh recordset ke memori Python hanya untuk menghitung jumlah.
- **Potongan Baris Kode Asli:**
```python
if len(self.env['sale.order'].search([('state', '=', 'draft')])) > 0:
```

### [Issue 4: AST-WRITE-IN-LOOP - Unbatched Database Write: .write() di dalam Loop for]
- **File:** `./sample_addons\custom_sale\models\sale_order.py` (Line: 22)
- **Severity:** `CRITICAL`
- **Penyebab:** Memanggil .write() pada setiap iterasi memicu evaluasi recompute dan row-lock berulang kali.
- **Potongan Baris Kode Asli:**
```python
order.write({'state': 'confirmed'})
```


## 4. INSTRUKSI TUGAS UNTUK ANDA (AI):
Berdasarkan data audit di atas, berikan jawaban teknis dengan urutan terstruktur berikut:

1. **Root Cause Analysis (RCA):**
   - Jelaskan dampak langsung terhadap server Odoo produksi jika isu-isu di atas dibiarkan.
2. **Ready-to-Apply Configuration Snippets:**
   - Tuliskan blok konfigurasi final untuk `/etc/odoo/odoo.conf`, `/etc/postgresql/13/main/postgresql.conf`, dan blok Nginx `upstream` + `location` yang sudah tersinkronisasi.
3. **Refactored Python Code:**
   - Untuk setiap temuan kode pada bagian 3, tuliskan kode perbaikan (Before vs After) menggunakan pola batching ORM Odoo 13 yang paling efisien dan aman.
4. **Rollout Checklist:**
   - Berikan panduan langkah-langkah deployment perbaikan tanpa menyebabkan downtime panjang.