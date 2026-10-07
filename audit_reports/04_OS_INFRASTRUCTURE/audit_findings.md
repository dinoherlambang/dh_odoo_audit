# 📋 Audit Sistem Operasi & Infrastruktur
## Temuan Kondisi OS & Penyimpanan:
| Code | Severity | Parameter | Deskripsi | Rekomendasi |
| :--- | :---: | :--- | :--- | :--- |
| `OS-SWAPPINESS-NA` | **INFO** | Pemeriksaan Swappiness Dilewati | /proc/sys/vm/swappiness tidak tersedia (Lingkungan Windows/Container). | - |
| `INFRA-DISK-WARN` | **WARNING** | Kapasitas Sisa Storage Mendekati Batas | Sisa storage tersisa 16.2% (76.9 GB). | - |