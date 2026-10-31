"""
app/pages/1_Upload_Struk.py — Halaman upload dan ekstraksi struk belanja.

Alur:
  1. Pengguna upload foto (JPEG/PNG ≤ 5 MB) atau ketik teks struk manual.
  2. Klik "Ekstrak" → panggil Gemini sekali, simpan ke st.session_state
     (rerun tidak memanggil API ulang).
  3. Hasil ditampilkan sebagai tabel item yang bisa diedit (st.data_editor).
  4. Preview JSON dan preview SQL INSERT (collapsible).
  5. Klik "Simpan" → validasi matematis → cek duplikat → simpan ke DB.
"""

import sys
import os
import io
import json

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import streamlit as st
from PIL import Image
from dotenv import load_dotenv

load_dotenv()

from app.agent.gemini_client import extract_from_image, extract_from_text, GeminiError
from app.db.database import init_db
from app.db.queries import insert_transaction, check_duplicate
from app.utils.validator import validate_receipt, format_rupiah

# Inisialisasi DB saat halaman pertama kali dibuka
init_db()

# ── Konstanta ──────────────────────────────────────────────────────────────────
_MAX_IMAGE_BYTES = 5 * 1024 * 1024          # 5 MB
_MAX_IMAGE_DIMENSION = 1024                 # piksel — perkecil sebelum kirim
_VALID_CATEGORIES = [
    "makanan", "minuman", "kebutuhan_rumah",
    "perawatan_diri", "transportasi", "lainnya",
]

# ── Helpers ────────────────────────────────────────────────────────────────────

def _resize_image(image_bytes: bytes, mime_type: str) -> tuple[bytes, str]:
    """Perkecil gambar jika dimensi > _MAX_IMAGE_DIMENSION.

    Args:
        image_bytes: Bytes gambar asli.
        mime_type:   "image/jpeg" atau "image/png".

    Returns:
        Tuple (bytes baru, mime_type baru). Selalu dikembalikan sebagai JPEG
        setelah resize untuk menghemat ukuran.
    """
    img = Image.open(io.BytesIO(image_bytes))
    w, h = img.size
    if max(w, h) > _MAX_IMAGE_DIMENSION:
        ratio = _MAX_IMAGE_DIMENSION / max(w, h)
        new_size = (int(w * ratio), int(h * ratio))
        img = img.resize(new_size, Image.LANCZOS)

    # Konversi ke RGB jika RGBA (PNG transparan)
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue(), "image/jpeg"


def _build_insert_preview(transaction: dict, items: list[dict]) -> str:
    """Hasilkan string SQL INSERT (untuk preview, tidak dieksekusi langsung)."""
    t = transaction
    needs = json.dumps(t.get("needs_review_fields", []), ensure_ascii=False)
    sql = (
        f"INSERT INTO transactions\n"
        f"  (store_name, store_address, transaction_date, transaction_time,\n"
        f"   receipt_number, subtotal, discount, tax, total, payment_method,\n"
        f"   validation_status, needs_review_fields)\n"
        f"VALUES\n"
        f"  ({_q(t.get('store_name'))}, {_q(t.get('store_address'))},\n"
        f"   {_q(t.get('transaction_date'))}, {_q(t.get('transaction_time'))},\n"
        f"   {_q(t.get('receipt_number'))}, {t.get('subtotal')},\n"
        f"   {t.get('discount', 0) or 0}, {t.get('tax', 0) or 0}, {t.get('total')},\n"
        f"   {_q(t.get('payment_method'))}, {_q(t.get('validation_status'))},\n"
        f"   {_q(needs)});\n"
    )
    for item in items:
        sql += (
            f"\nINSERT INTO transaction_items\n"
            f"  (transaction_id, item_name, quantity, unit_price, line_total, category)\n"
            f"VALUES\n"
            f"  (LAST_INSERT_ROWID(), {_q(item.get('item_name'))}, "
            f"{item.get('quantity', 1)}, {item.get('unit_price')}, "
            f"{item.get('line_total')}, {_q(item.get('category'))});\n"
        )
    return sql


def _q(val) -> str:
    """Quote nilai untuk preview SQL (bukan untuk eksekusi)."""
    if val is None:
        return "NULL"
    return f"'{str(val).replace(chr(39), chr(39)*2)}'"


def _normalize_result(raw: dict) -> tuple[dict, list[dict]]:
    """Normalisasi output Gemini menjadi (transaction_dict, items_list)."""
    transaction = raw.get("transaction", {}) or {}
    items = raw.get("items", []) or []
    # Bawa validation_status & needs_review_fields ke dalam transaction
    transaction["validation_status"] = raw.get("validation_status", "ok")
    transaction["needs_review_fields"] = raw.get("needs_review_fields") or []
    return transaction, items


# ── State helpers ──────────────────────────────────────────────────────────────

def _clear_extraction_state():
    """Hapus hasil ekstraksi dari session_state."""
    for key in ("extracted_transaction", "extracted_items", "extraction_error"):
        st.session_state.pop(key, None)


def _do_save(transaction: dict, items: list[dict]) -> None:
    """Simpan transaksi ke database dan tampilkan hasil."""
    try:
        tx_id = insert_transaction(transaction, items)
        st.success(
            f"✅ Struk berhasil disimpan! ID Transaksi: **{tx_id}**  \n"
            "Lihat riwayat di halaman **📋 Riwayat**."
        )
        # Hapus session_state agar form bersih untuk struk berikutnya
        for key in ("extracted_transaction", "extracted_items"):
            st.session_state.pop(key, None)
    except Exception as e:
        st.error(f"❌ Gagal menyimpan ke database: {e}")

# ── UI Utama ───────────────────────────────────────────────────────────────────

st.title("📤 Upload Struk")
st.caption("Unggah foto struk belanja atau ketik teks struk, lalu klik Ekstrak.")

# ── Tab: Foto vs Teks ─────────────────────────────────────────────────────────
tab_foto, tab_teks = st.tabs(["📷 Unggah Foto", "⌨️ Input Teks Manual"])

# ─── Tab Foto ─────────────────────────────────────────────────────────────────
with tab_foto:
    uploaded_file = st.file_uploader(
        "Pilih gambar struk (JPEG / PNG, maks. 5 MB)",
        type=["jpg", "jpeg", "png"],
        on_change=_clear_extraction_state,   # reset jika ganti file
    )

    if uploaded_file is not None:
        raw_bytes = uploaded_file.read()

        # Validasi ukuran
        if len(raw_bytes) > _MAX_IMAGE_BYTES:
            st.error(
                f"Ukuran file ({len(raw_bytes)//1024} KB) melebihi batas 5 MB. "
                "Kompres gambar terlebih dahulu."
            )
        else:
            col_img, col_btn = st.columns([2, 1])
            with col_img:
                st.image(raw_bytes, caption="Preview struk", use_container_width=True)
            with col_btn:
                st.write("")  # spacer
                if st.button("🔍 Ekstrak dari Foto", type="primary", key="btn_extract_foto"):
                    _clear_extraction_state()
                    with st.spinner("Mengirim gambar ke Gemini..."):
                        try:
                            mime = (
                                "image/png"
                                if uploaded_file.name.lower().endswith(".png")
                                else "image/jpeg"
                            )
                            resized_bytes, mime = _resize_image(raw_bytes, mime)
                            raw_result = extract_from_image(resized_bytes, mime)
                            transaction, items = _normalize_result(raw_result)
                            st.session_state["extracted_transaction"] = transaction
                            st.session_state["extracted_items"] = items
                        except GeminiError as e:
                            st.session_state["extraction_error"] = str(e)

# ─── Tab Teks ─────────────────────────────────────────────────────────────────
with tab_teks:
    st.caption("Ketik atau tempel teks dari struk belanja di bawah ini.")
    receipt_text = st.text_area(
        "Teks struk",
        height=200,
        placeholder=(
            "Contoh:\n"
            "Indomaret Merdeka\n"
            "15-03-2024  14:32\n"
            "Indomie Goreng  3x  Rp3.500  = Rp10.500\n"
            "Aqua 600ml      2x  Rp4.000  = Rp8.000\n"
            "Subtotal: Rp18.500\n"
            "Total: Rp18.500"
        ),
        on_change=_clear_extraction_state,
    )
    if st.button("🔍 Ekstrak dari Teks", type="primary", key="btn_extract_teks"):
        _clear_extraction_state()
        with st.spinner("Mengirim teks ke Gemini..."):
            try:
                raw_result = extract_from_text(receipt_text)
                transaction, items = _normalize_result(raw_result)
                st.session_state["extracted_transaction"] = transaction
                st.session_state["extracted_items"] = items
            except GeminiError as e:
                st.session_state["extraction_error"] = str(e)

# ── Tampilkan error ekstraksi ─────────────────────────────────────────────────
if "extraction_error" in st.session_state:
    st.error(f"❌ {st.session_state['extraction_error']}")

# ── Tampilkan hasil ekstraksi ─────────────────────────────────────────────────
if "extracted_transaction" in st.session_state:
    transaction: dict = st.session_state["extracted_transaction"]
    items: list[dict] = st.session_state["extracted_items"]

    st.divider()
    st.subheader("📋 Hasil Ekstraksi")

    # ── Status validasi ───────────────────────────────────────────────────────
    validation_status = transaction.get("validation_status", "ok")
    needs_review = transaction.get("needs_review_fields") or []

    if validation_status == "mismatch":
        st.error(
            "⚠️ **Validasi gagal**: Jumlah item, subtotal, diskon, pajak, "
            "atau total tidak cocok. Periksa dan koreksi data di bawah sebelum menyimpan."
        )
    if needs_review:
        st.warning(
            f"🔍 **Perlu diperiksa**: field `{', '.join(needs_review)}` "
            "tidak terbaca dengan jelas dari struk."
        )

    # ── Info transaksi ────────────────────────────────────────────────────────
    st.markdown("**Informasi Transaksi**")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.text_input(
            "Nama Toko",
            value=transaction.get("store_name") or "",
            key="edit_store_name",
        )
        st.text_input(
            "Alamat",
            value=transaction.get("store_address") or "",
            key="edit_store_address",
        )
        st.text_input(
            "Nomor Struk",
            value=transaction.get("receipt_number") or "",
            key="edit_receipt_number",
        )
    with col2:
        st.text_input(
            "Tanggal (YYYY-MM-DD)",
            value=transaction.get("transaction_date") or "",
            key="edit_transaction_date",
        )
        st.text_input(
            "Jam (HH:MM)",
            value=transaction.get("transaction_time") or "",
            key="edit_transaction_time",
        )
        st.text_input(
            "Metode Pembayaran",
            value=transaction.get("payment_method") or "",
            key="edit_payment_method",
        )
    with col3:
        st.number_input(
            "Subtotal (Rp)",
            value=int(transaction.get("subtotal") or 0),
            min_value=0,
            step=500,
            key="edit_subtotal",
        )
        st.number_input(
            "Diskon (Rp)",
            value=int(transaction.get("discount") or 0),
            min_value=0,
            step=500,
            key="edit_discount",
        )
        st.number_input(
            "Pajak (Rp)",
            value=int(transaction.get("tax") or 0),
            min_value=0,
            step=500,
            key="edit_tax",
        )
        st.number_input(
            "Total (Rp)",
            value=int(transaction.get("total") or 0),
            min_value=0,
            step=500,
            key="edit_total",
        )

    # ── Tabel item (editable) ─────────────────────────────────────────────────
    st.markdown("**Daftar Item**")
    st.caption(
        "Kamu bisa mengedit langsung di tabel. "
        "Kolom **category** hanya boleh diisi salah satu dari: "
        + ", ".join(f"`{c}`" for c in _VALID_CATEGORIES)
    )

    import pandas as pd

    items_df = pd.DataFrame(
        items if items else [{"item_name": "", "quantity": 1, "unit_price": 0,
                              "line_total": 0, "category": "lainnya"}]
    )
    # Pastikan kolom ada semua
    for col in ["item_name", "quantity", "unit_price", "line_total", "category"]:
        if col not in items_df.columns:
            items_df[col] = None

    edited_df = st.data_editor(
        items_df[["item_name", "quantity", "unit_price", "line_total", "category"]],
        use_container_width=True,
        num_rows="dynamic",
        column_config={
            "item_name":  st.column_config.TextColumn("Nama Item"),
            "quantity":   st.column_config.NumberColumn("Qty", min_value=0, step=1, format="%d"),
            "unit_price": st.column_config.NumberColumn("Harga Satuan (Rp)", min_value=0, step=500),
            "line_total": st.column_config.NumberColumn("Total Item (Rp)", min_value=0, step=500),
            "category":   st.column_config.SelectboxColumn(
                "Kategori",
                options=_VALID_CATEGORIES,
                required=True,
            ),
        },
        key="items_editor",
    )

    # ── Preview JSON ──────────────────────────────────────────────────────────
    with st.expander("🔎 Preview JSON (hasil ekstraksi)", expanded=False):
        preview_transaction = {
            "store_name":       st.session_state.get("edit_store_name", transaction.get("store_name")),
            "store_address":    st.session_state.get("edit_store_address", transaction.get("store_address")),
            "transaction_date": st.session_state.get("edit_transaction_date", transaction.get("transaction_date")),
            "transaction_time": st.session_state.get("edit_transaction_time", transaction.get("transaction_time")),
            "receipt_number":   st.session_state.get("edit_receipt_number", transaction.get("receipt_number")),
            "subtotal":         st.session_state.get("edit_subtotal", transaction.get("subtotal")),
            "discount":         st.session_state.get("edit_discount", transaction.get("discount")),
            "tax":              st.session_state.get("edit_tax", transaction.get("tax")),
            "total":            st.session_state.get("edit_total", transaction.get("total")),
            "payment_method":   st.session_state.get("edit_payment_method", transaction.get("payment_method")),
        }
        preview_items = edited_df.to_dict(orient="records")
        st.json({
            "transaction": preview_transaction,
            "items": preview_items,
            "validation_status": validation_status,
            "needs_review_fields": needs_review,
        })

    # ── Preview SQL ───────────────────────────────────────────────────────────
    with st.expander("🗄️ Preview SQL INSERT", expanded=False):
        sql_preview = _build_insert_preview(
            {**preview_transaction,
             "validation_status": validation_status,
             "needs_review_fields": needs_review},
            preview_items,
        )
        st.code(sql_preview, language="sql")

    # ── Tombol Simpan ─────────────────────────────────────────────────────────
    st.divider()
    col_save, col_cancel = st.columns([1, 4])
    with col_save:
        save_clicked = st.button("💾 Simpan ke Database", type="primary", key="btn_save")
    with col_cancel:
        if st.button("🗑️ Reset / Mulai Ulang", key="btn_reset"):
            _clear_extraction_state()
            st.rerun()

    if save_clicked:
        # Bangun ulang dict dari widget yang mungkin sudah diedit pengguna
        final_transaction = {
            "store_name":       st.session_state.get("edit_store_name") or None,
            "store_address":    st.session_state.get("edit_store_address") or None,
            "transaction_date": st.session_state.get("edit_transaction_date") or None,
            "transaction_time": st.session_state.get("edit_transaction_time") or None,
            "receipt_number":   st.session_state.get("edit_receipt_number") or None,
            "subtotal":         st.session_state.get("edit_subtotal") or 0,
            "discount":         st.session_state.get("edit_discount") or 0,
            "tax":              st.session_state.get("edit_tax") or 0,
            "total":            st.session_state.get("edit_total") or 0,
            "payment_method":   st.session_state.get("edit_payment_method") or None,
        }
        final_items = edited_df.to_dict(orient="records")

        # Jalankan validasi ulang terhadap data yang mungkin sudah diedit
        validated = validate_receipt(final_transaction, final_items)

        # Cek duplikat
        is_dup = check_duplicate(
            validated.get("store_name"),
            validated.get("transaction_date"),
            validated.get("receipt_number"),
            validated.get("total"),
        )
        if is_dup:
            st.warning(
                "⚠️ **Kemungkinan duplikat**: Struk dengan kombinasi toko, tanggal, "
                "nomor struk, dan total yang sama sudah ada di database. "
                "Klik **Simpan Tetap** jika kamu yakin ini bukan duplikat."
            )
            if st.button("✅ Simpan Tetap", type="primary", key="btn_save_anyway"):
                _do_save(validated, final_items)
        else:
            _do_save(validated, final_items)



