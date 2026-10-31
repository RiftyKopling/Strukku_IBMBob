# StrukKu — Pencatat Pengeluaran Pribadi Berbasis AI

Aplikasi Streamlit yang mengubah foto struk belanja menjadi data pengeluaran terstruktur menggunakan Google Gemini.

---

## Prasyarat

- Python 3.11+
- Google Gemini API key ([dapatkan di Google AI Studio](https://aistudio.google.com/))

---

## Instalasi

```bash
# 1. Clone / unduh project ini
cd StrukKu

# 2. Buat virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

# 3. Install dependensi
pip install -r requirements.txt

# 4. Buat file .env
copy .env.example .env        # Windows
# cp .env.example .env        # macOS/Linux
# Lalu edit .env dan isi GEMINI_API_KEY
```

---

## Menjalankan Aplikasi

```bash
streamlit run app/main.py
```

Buka browser di `http://localhost:8501`.

---

## Menjalankan Tes

```bash
pytest tests/ -v
```

---

## Struktur Project

```
.
├── app/
│   ├── main.py                  # Halaman utama
│   ├── pages/
│   │   ├── 1_Upload_Struk.py    # Upload & ekstraksi struk
│   │   ├── 2_Riwayat.py         # Riwayat transaksi
│   │   └── 3_Dashboard.py       # Grafik & statistik
│   ├── agent/
│   │   ├── gemini_client.py     # Klien Google Gemini
│   │   └── prompt.py            # System prompt
│   ├── db/
│   │   ├── database.py          # Koneksi & inisialisasi SQLite
│   │   └── queries.py           # Query CRUD
│   └── utils/
│       └── validator.py         # Validasi matematis struk
├── tests/
│   ├── test_validator.py        # Pytest untuk validator
│   └── sample_receipt.json      # Data struk sampel
├── .env.example                 # Template konfigurasi
├── requirements.txt
└── README.md
```

---

## Variabel Lingkungan (`.env`)

| Variabel | Keterangan | Contoh |
|----------|------------|--------|
| `GEMINI_API_KEY` | API key Google Gemini | `AIza...` |
| `GEMINI_MODEL` | Nama model yang digunakan | `gemini-3.5-flash-lite` |

---

## Catatan

- Data disimpan lokal di `strukku.db` (tidak di-commit ke Git).
- Rupiah disimpan sebagai integer (tanpa titik/koma).
- Validasi matematis dilakukan di sisi aplikasi, bukan oleh model AI.
