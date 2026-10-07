# 🛠️ Panduan Revisi Kode Modul Kustom (Before vs After)
Panduan ini merangkum perbaikan baris kode untuk menghilangkan N+1 query dan bottleneck transaksi database.

### Revisi Masalah #1: Computed Field Tanpa Flag store=True
**Lokasi File:** `./sample_addons\custom_sale\models\sale_order.py` (Baris: 7)

```python
# ❌ SEBELUM (Kode Bermasalah):
commission_total = fields.Float(string="Total Commission", compute="_compute_commission")

# ✅ SESUDAH (Solusi Rekomendasi):
# Pertimbangkan menambahkan 'store=True' jika nilai field sering dibaca atau tampil di list/tree view.
```

### Revisi Masalah #2: N+1 Query: Method .search() di dalam Loop for
**Lokasi File:** `./sample_addons\custom_sale\models\sale_order.py` (Baris: 12)

```python
# ❌ SEBELUM (Kode Bermasalah):
comms = self.env['sale.commission'].search([('partner_id', '=', order.user_id.partner_id.id)])

# ✅ SESUDAH (Solusi Rekomendasi):
# Kumpulkan ID terlebih dahulu lalu lakukan satu kali search dengan operator 'in' di luar loop.
```

### Revisi Masalah #3: Anti-Pattern len(search()) Terdeteksi
**Lokasi File:** `./sample_addons\custom_sale\models\sale_order.py` (Baris: 19)

```python
# ❌ SEBELUM (Kode Bermasalah):
if len(self.env['sale.order'].search([('state', '=', 'draft')])) > 0:

# ✅ SESUDAH (Solusi Rekomendasi):
# Gunakan method search_count() untuk menghitung jumlah baris langsung di PostgreSQL.
```

### Revisi Masalah #4: Unbatched Database Write: .write() di dalam Loop for
**Lokasi File:** `./sample_addons\custom_sale\models\sale_order.py` (Baris: 22)

```python
# ❌ SEBELUM (Kode Bermasalah):
order.write({'state': 'confirmed'})

# ✅ SESUDAH (Solusi Rekomendasi):
# Gunakan batching: recordset.write(...) di luar perulangan.
```
