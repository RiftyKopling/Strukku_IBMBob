"""
app/main.py — Halaman utama StrukKu.

Dijalankan dari root project:
    streamlit run app/main.py
"""

import sys
import os

# Pastikan root project ada di sys.path agar semua import relatif berfungsi.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import streamlit as st
from dotenv import load_dotenv

# Muat variabel lingkungan dari .env (jika ada)
load_dotenv()

# ── Konfigurasi halaman ────────────────────────────────────────────────────────
st.set_page_config(
    page_title="StrukKu",
    page_icon="🧾",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS tambahan (aksen oranye untuk tombol utama) ────────────────────────────
st.markdown(
    """
    <style>
        /* Tombol primer → oranye aksen */
        div.stButton > button[kind="primary"] {
            background-color: #F97316;
            color: white;
            border: none;
        }
        div.stButton > button[kind="primary"]:hover {
            background-color: #EA6C10;
            color: white;
        }
        /* Sidebar title */
        .sidebar-title {
            font-size: 1.3rem;
            font-weight: 700;
            color: #1E40AF;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Konten halaman utama ───────────────────────────────────────────────────────
st.title("🧾 StrukKu")
st.subheader("Pencatat Pengeluaran Pribadi untuk Mahasiswa")

st.markdown(
    """
    Selamat datang di **StrukKu** — aplikasi yang mengubah foto struk belanjamu  
    menjadi data pengeluaran yang rapi dan mudah dianalisis.

    ---

    ### Cara Penggunaan

    | Langkah | Halaman | Keterangan |
    |---------|---------|------------|
    | 1 | **📤 Upload Struk** | Unggah foto struk (JPEG/PNG) atau ketik teks struk secara manual |
    | 2 | **📋 Riwayat** | Lihat, filter, dan hapus riwayat transaksi |
    | 3 | **📊 Dashboard** | Pantau pengeluaran lewat grafik dan ringkasan |

    ---

    ### Fitur Utama

    - 🤖 **Ekstraksi otomatis** dengan Google Gemini — tidak perlu ketik ulang
    - ✅ **Validasi matematis** — aplikasi memeriksa kecocokan subtotal, diskon, pajak, dan total
    - 💾 **Penyimpanan lokal** — data tersimpan di SQLite di perangkatmu sendiri, tanpa cloud
    - 📈 **Dashboard visual** — grafik pengeluaran per kategori dan per bulan

    ---

    > Pilih halaman di **sidebar kiri** untuk mulai.
    """,
    unsafe_allow_html=False,
)

# ── Sidebar: informasi versi / status API ─────────────────────────────────────
with st.sidebar:
    st.markdown('<p class="sidebar-title">🧾 StrukKu</p>', unsafe_allow_html=True)
    st.caption("v0.1.0 — Proyek Pembelajaran")
    st.divider()

    api_key = os.getenv("GEMINI_API_KEY", "")
    if api_key and api_key != "your_gemini_api_key_here":
        st.success("✅ API Key terdeteksi")
    else:
        st.warning(
            "⚠️ GEMINI_API_KEY belum diset.  \n"
            "Salin `.env.example` → `.env` dan isi API key-mu."
        )

    model_name = os.getenv("GEMINI_MODEL", "—")
    st.caption(f"Model: `{model_name}`")
