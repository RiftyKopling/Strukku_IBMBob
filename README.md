# 🧾 StrukKu — Pencatat Pengeluaran Pribadi Berbasis AI

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-1.35+-FF4B4B?logo=streamlit&logoColor=white)
![Google Gemini](https://img.shields.io/badge/Google%20Gemini-API-4285F4?logo=google&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-lokal-003B57?logo=sqlite&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

> Ubah foto struk belanjamu menjadi data pengeluaran yang rapi — tanpa ketik manual.

**StrukKu** adalah aplikasi web berbasis [Streamlit](https://streamlit.io) yang memanfaatkan **Google Gemini Vision** untuk mengekstrak data dari foto struk belanja (JPEG/PNG) atau teks, menyimpannya ke database SQLite lokal, dan menampilkan dashboard pengeluaran interaktif.

---

## ✨ Fitur Utama

| Fitur | Detail |
|-------|--------|
| 🤖 **Ekstraksi AI** | Upload foto struk atau ketik teks — Gemini mengekstrak semua field secara otomatis |
| ✅ **Validasi Matematis** | Aplikasi memeriksa kecocokan subtotal, diskon, pajak, dan total secara independen dari AI |
| ✏️ **Edit Sebelum Simpan** | Koreksi hasil ekstraksi di tabel interaktif sebelum masuk database |
| 🔍 **Deteksi Duplikat** | Peringatan otomatis jika struk yang sama sudah pernah disimpan |
| 📋 **Riwayat & Filter** | Filter transaksi berdasarkan tanggal dan status validasi |
| 📊 **Dashboard Visual** | Pie chart per kategori, bar chart per bulan, metric cards total pengeluaran |
| 🔄 **Retry Otomatis** | Exponential backoff jika API Gemini sedang sibuk (high demand) |
| 💾 **100% Lokal** | Data tersimpan di SQLite di perangkatmu — tidak ada data yang dikirim ke cloud selain foto struk |

---

## 🖥️ Tampilan Aplikasi

| Halaman | Deskripsi |
|---------|-----------|
| 🏠 Beranda | Status API key, panduan penggunaan |
| 📤 Upload Struk | Upload foto / input teks, edit hasil, preview JSON & SQL, simpan |
| 📋 Riwayat | Tabel transaksi dengan filter, detail item, hapus transaksi |
| 📊 Dashboard | Ringkasan, pie chart kategori, bar chart bulanan, top 5 struk |

---

## 🚀 Instalasi & Menjalankan

### Prasyarat

- Python **3.11+**
- Google Gemini API key — [dapatkan gratis di Google AI Studio](https://aistudio.google.com/)

### Langkah Instalasi

```bash
# 1. Clone repository
git clone https://github.com/USERNAME/strukku.git
cd strukku

# 2. Buat virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux

# 3. Install dependensi
pip install -r requirements.txt

# 4. Salin dan isi file konfigurasi
copy .env.example .env        # Windows
# cp .env.example .env        # macOS / Linux
```

Edit file `.env` yang baru dibuat:

```env
GEMINI_API_KEY=AIza...          # ganti dengan API key kamu
GEMINI_MODEL=gemini-3.5-flash-lite
```

### Menjalankan Aplikasi

```bash
streamlit run app/main.py
```

Buka browser di **http://localhost:8501**.

---

## 🧪 Menjalankan Tes

```bash
pytest tests/ -v
```

Expected output: **17 passed**.

---

## 🗂️ Struktur Project

```
strukku/
├── app/
│   ├── main.py                  # Halaman utama & routing
│   ├── pages/
│   │   ├── 1_Upload_Struk.py    # Upload foto/teks, ekstraksi, simpan
│   │   ├── 2_Riwayat.py         # Riwayat & filter transaksi
│   │   └── 3_Dashboard.py       # Dashboard & visualisasi
│   ├── agent/
│   │   ├── gemini_client.py     # Klien Google Gemini (SDK google-genai)
│   │   └── prompt.py            # System prompt 3-layer
│   ├── db/
│   │   ├── database.py          # Koneksi SQLite & inisialisasi tabel
│   │   └── queries.py           # Query CRUD & agregat
│   └── utils/
│       └── validator.py         # Validasi matematis & format rupiah
├── tests/
│   ├── test_validator.py        # 17 pytest cases untuk validator
│   └── sample_receipt.json      # Data struk sampel
├── .env.example                 # Template konfigurasi (aman di-commit)
├── .gitattributes               # Normalisasi line ending
├── requirements.txt             # Dependensi Python
└── README.md
```

---

## ⚙️ Variabel Lingkungan

File `.env` (jangan di-commit, sudah ada di `.gitignore`):

| Variabel | Keterangan | Contoh |
|----------|------------|--------|
| `GEMINI_API_KEY` | API key Google Gemini | `AIza...` |
| `GEMINI_MODEL` | Nama model Gemini yang dipakai | `gemini-3.5-flash-lite` |

> Ganti `GEMINI_MODEL` jika model yang kamu pakai sudah tidak tersedia. Aplikasi akan menampilkan pesan petunjuk yang jelas di UI.

---

## 🗄️ Skema Database

```sql
transactions (
  id, store_name, store_address, transaction_date, transaction_time,
  receipt_number, subtotal, discount, tax, total, payment_method,
  validation_status, needs_review_fields, created_at
)

transaction_items (
  id, transaction_id → transactions(id) CASCADE,
  item_name, quantity, unit_price, line_total, category
)
```

Nilai rupiah disimpan sebagai **integer** (misal: `15000` bukan `"Rp 15.000"`).  
Kategori item: `makanan`, `minuman`, `kebutuhan_rumah`, `perawatan_diri`, `transportasi`, `lainnya`.

---

## 🛠️ Tech Stack

| Komponen | Library |
|----------|---------|
| UI | [Streamlit](https://streamlit.io) ≥ 1.35 |
| AI | [google-genai](https://pypi.org/project/google-genai/) SDK (bukan `google-generativeai`) |
| Database | SQLite3 (bawaan Python) |
| Visualisasi | [Plotly](https://plotly.com/python/) |
| Image Processing | [Pillow](https://python-pillow.org/) |
| Testing | [pytest](https://pytest.org/) |
| Config | [python-dotenv](https://pypi.org/project/python-dotenv/) |

---

## 📝 Catatan Pengembangan

- Data disimpan **lokal** di `strukku.db` — file ini tidak di-commit ke Git.
- Validasi matematis (subtotal ± diskon ± pajak = total) dilakukan di **sisi aplikasi**, bukan oleh model AI, sehingga hasilnya lebih akurat.
- Jika API Gemini mengembalikan error *"high demand"*, aplikasi akan **retry otomatis** hingga 3 kali dengan jeda 5s → 10s → 20s.
- Foto dikirim ke Gemini setelah diperkecil ke ≤ 1024px untuk menghemat kuota API.

---

## 🤝 Kontribusi

Pull request dan issue sangat disambut! Beberapa ide pengembangan:

- [ ] Export data ke CSV / Excel
- [ ] Notifikasi jika pengeluaran bulanan melampaui batas
- [ ] Dukungan multi-pengguna
- [ ] Mode offline dengan OCR lokal (Tesseract)

---

## 📄 Lisensi

MIT License — bebas digunakan dan dimodifikasi dengan mencantumkan atribusi.
