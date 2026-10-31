"""
app/pages/2_Riwayat.py — Halaman riwayat transaksi.

Fitur:
  - Tabel semua transaksi dengan filter rentang tanggal dan validation_status.
  - Lihat detail item per transaksi (expandable).
  - Hapus transaksi (dengan konfirmasi).
"""

import sys
import os
import json

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import streamlit as st
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

from app.db.database import init_db
from app.db.queries import get_all_transactions, get_transaction_items, delete_transaction
from app.utils.validator import format_rupiah

init_db()

# ── Helpers ────────────────────────────────────────────────────────────────────

def _status_badge(status: str | None) -> str:
    """Kembalikan emoji badge untuk validation_status."""
    if status == "ok":
        return "✅ ok"
    if status == "mismatch":
        return "❌ mismatch"
    return "❓ —"


def _parse_needs_review(raw: str | list | None) -> list[str]:
    """Parse needs_review_fields dari TEXT (JSON array) atau list."""
    if not raw:
        return []
    if isinstance(raw, list):
        return raw
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _transactions_to_df(rows: list[dict]) -> pd.DataFrame:
    """Konversi list dict transaksi ke DataFrame siap tampil."""
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)

    # Kolom yang ditampilkan dan urutannya
    display_cols = [
        "id", "transaction_date", "store_name", "receipt_number",
        "subtotal", "discount", "tax", "total",
        "payment_method", "validation_status", "created_at",
    ]
    # Tambahkan kolom yang mungkin tidak ada
    for col in display_cols:
        if col not in df.columns:
            df[col] = None

    df = df[display_cols].copy()

    # Rename untuk tampilan yang lebih ramah
    df = df.rename(columns={
        "id":                "ID",
        "transaction_date":  "Tanggal",
        "store_name":        "Toko",
        "receipt_number":    "No. Struk",
        "subtotal":          "Subtotal",
        "discount":          "Diskon",
        "tax":               "Pajak",
        "total":             "Total",
        "payment_method":    "Pembayaran",
        "validation_status": "Status",
        "created_at":        "Dicatat",
    })

    return df


# ── Layout halaman ─────────────────────────────────────────────────────────────

st.title("📋 Riwayat Transaksi")

# ── Filter ────────────────────────────────────────────────────────────────────
with st.expander("🔎 Filter", expanded=True):
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        date_from = st.date_input("Dari tanggal", value=None, key="filter_date_from")
    with col_f2:
        date_to = st.date_input("Sampai tanggal", value=None, key="filter_date_to")
    with col_f3:
        status_filter = st.selectbox(
            "Status Validasi",
            options=["Semua", "ok", "mismatch"],
            key="filter_status",
        )

# Konversi date ke string untuk query
str_from = str(date_from) if date_from else None
str_to   = str(date_to)   if date_to   else None
str_status = None if status_filter == "Semua" else status_filter

# ── Ambil data ────────────────────────────────────────────────────────────────
rows = get_all_transactions(
    date_from=str_from,
    date_to=str_to,
    validation_status=str_status,
)

if not rows:
    st.info("Belum ada transaksi yang tersimpan. Upload struk di halaman **📤 Upload Struk**.")
    st.stop()

# ── Ringkasan cepat ───────────────────────────────────────────────────────────
total_tampil   = sum(r.get("total") or 0 for r in rows)
jumlah_tampil  = len(rows)
mismatch_count = sum(1 for r in rows if r.get("validation_status") == "mismatch")

m1, m2, m3 = st.columns(3)
m1.metric("Transaksi Ditampilkan", jumlah_tampil)
m2.metric("Total Pengeluaran", format_rupiah(total_tampil))
m3.metric("Perlu Diperiksa (mismatch)", mismatch_count)

st.divider()

# ── Tabel transaksi ───────────────────────────────────────────────────────────
st.subheader("Daftar Transaksi")

df = _transactions_to_df(rows)

# Format kolom rupiah
for col in ["Subtotal", "Diskon", "Pajak", "Total"]:
    if col in df.columns:
        df[col] = df[col].apply(lambda v: format_rupiah(int(v)) if v is not None else "Rp —")

st.dataframe(
    df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "ID":        st.column_config.NumberColumn("ID", width="small"),
        "Tanggal":   st.column_config.TextColumn("Tanggal", width="small"),
        "Toko":      st.column_config.TextColumn("Toko"),
        "No. Struk": st.column_config.TextColumn("No. Struk"),
        "Status":    st.column_config.TextColumn("Status", width="small"),
        "Dicatat":   st.column_config.TextColumn("Dicatat", width="medium"),
    },
)

st.divider()

# ── Detail item per transaksi ─────────────────────────────────────────────────
st.subheader("Detail Item & Aksi")
st.caption("Pilih ID transaksi untuk melihat detail item atau menghapus transaksi.")

# Buat mapping id → row untuk lookup cepat
id_to_row = {r["id"]: r for r in rows}
tx_ids    = [r["id"] for r in rows]

selected_id = st.selectbox(
    "Pilih ID Transaksi",
    options=tx_ids,
    format_func=lambda tid: (
        f"#{tid} — {id_to_row[tid].get('store_name') or '(tanpa nama toko)'} "
        f"| {id_to_row[tid].get('transaction_date') or '—'} "
        f"| {format_rupiah(id_to_row[tid].get('total'))}"
    ),
    key="detail_select",
)

if selected_id is not None:
    tx = id_to_row[selected_id]

    # Info header transaksi terpilih
    with st.container(border=True):
        col_h1, col_h2, col_h3 = st.columns(3)
        with col_h1:
            st.markdown(f"**Toko:** {tx.get('store_name') or '—'}")
            st.markdown(f"**Alamat:** {tx.get('store_address') or '—'}")
            st.markdown(f"**No. Struk:** {tx.get('receipt_number') or '—'}")
        with col_h2:
            st.markdown(f"**Tanggal:** {tx.get('transaction_date') or '—'}")
            st.markdown(f"**Jam:** {tx.get('transaction_time') or '—'}")
            st.markdown(f"**Pembayaran:** {tx.get('payment_method') or '—'}")
        with col_h3:
            st.markdown(f"**Subtotal:** {format_rupiah(tx.get('subtotal'))}")
            st.markdown(f"**Diskon:** {format_rupiah(tx.get('discount'))}")
            st.markdown(f"**Pajak:** {format_rupiah(tx.get('tax'))}")
            st.markdown(f"**Total:** {format_rupiah(tx.get('total'))}")

        # Tampilkan status validasi
        vstatus = tx.get("validation_status")
        if vstatus == "mismatch":
            st.error(f"❌ Status Validasi: **mismatch** — data matematis tidak cocok.")
        elif vstatus == "ok":
            st.success("✅ Status Validasi: **ok**")

        # Tampilkan needs_review_fields jika ada
        needs = _parse_needs_review(tx.get("needs_review_fields"))
        if needs:
            st.warning(f"🔍 Field perlu diperiksa: `{', '.join(needs)}`")

    # Tabel item
    items = get_transaction_items(selected_id)
    if items:
        st.markdown("**Daftar Item:**")
        items_df = pd.DataFrame(items)

        # Kolom tampilan
        show_cols = ["item_name", "quantity", "unit_price", "line_total", "category"]
        for col in show_cols:
            if col not in items_df.columns:
                items_df[col] = None

        items_df = items_df[show_cols].rename(columns={
            "item_name":  "Nama Item",
            "quantity":   "Qty",
            "unit_price": "Harga Satuan",
            "line_total": "Total Item",
            "category":   "Kategori",
        })

        # Format rupiah
        for col in ["Harga Satuan", "Total Item"]:
            items_df[col] = items_df[col].apply(
                lambda v: format_rupiah(int(v)) if v is not None else "Rp —"
            )

        st.dataframe(items_df, use_container_width=True, hide_index=True)
    else:
        st.info("Tidak ada item tersimpan untuk transaksi ini.")

    # ── Aksi hapus ────────────────────────────────────────────────────────────
    st.divider()
    st.markdown("**Hapus Transaksi**")
    st.caption("Menghapus transaksi akan menghapus semua item terkait secara permanen.")

    # Gunakan session_state untuk konfirmasi dua langkah
    confirm_key = f"confirm_delete_{selected_id}"

    if not st.session_state.get(confirm_key, False):
        if st.button(
            f"🗑️ Hapus Transaksi #{selected_id}",
            type="secondary",
            key=f"btn_delete_{selected_id}",
        ):
            st.session_state[confirm_key] = True
            st.rerun()
    else:
        st.warning(
            f"⚠️ Yakin ingin menghapus transaksi **#{selected_id}** "
            f"({tx.get('store_name') or '—'}, {format_rupiah(tx.get('total'))})? "
            "Tindakan ini tidak dapat dibatalkan."
        )
        col_yes, col_no = st.columns(2)
        with col_yes:
            if st.button("✅ Ya, Hapus", type="primary", key=f"btn_confirm_delete_{selected_id}"):
                try:
                    delete_transaction(selected_id)
                    st.session_state.pop(confirm_key, None)
                    st.success(f"Transaksi #{selected_id} berhasil dihapus.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Gagal menghapus: {e}")
        with col_no:
            if st.button("❌ Batal", key=f"btn_cancel_delete_{selected_id}"):
                st.session_state.pop(confirm_key, None)
                st.rerun()
