# 📋 Audit Kode Python Modul Kustom (AST)
## Daftar Pelanggaran Performa Terdeteksi:

### [1] `AST-SEARCH-IN-LOOP` - N+1 Query: Method .search() di dalam Loop for
- **File:** `./sample_addons\custom_sale\models\sale_order.py` (Baris: 12)
- **Tingkat Bahaya:** `CRITICAL`
- **Penyebab:** Pemanggilan .search() di dalam perulangan for memicu ratusan round-trip query ke PostgreSQL.
```python
comms = self.env['sale.commission'].search([('partner_id', '=', order.user_id.partner_id.id)])
```

### [2] `AST-LEN-SEARCH` - Anti-Pattern len(search()) Terdeteksi
- **File:** `./sample_addons\custom_sale\models\sale_order.py` (Baris: 19)
- **Tingkat Bahaya:** `WARNING`
- **Penyebab:** Menggunakan len() pada search() menarik seluruh recordset ke memori Python hanya untuk menghitung jumlah.
```python
if len(self.env['sale.order'].search([('state', '=', 'draft')])) > 0:
```

### [3] `AST-WRITE-IN-LOOP` - Unbatched Database Write: .write() di dalam Loop for
- **File:** `./sample_addons\custom_sale\models\sale_order.py` (Baris: 22)
- **Tingkat Bahaya:** `CRITICAL`
- **Penyebab:** Memanggil .write() pada setiap iterasi memicu evaluasi recompute dan row-lock berulang kali.
```python
order.write({'state': 'confirmed'})
```
