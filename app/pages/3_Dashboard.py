"""
app/pages/3_Dashboard.py — Halaman dashboard pengeluaran.

Menampilkan:
  - Metric cards: total pengeluaran, jumlah struk, rata-rata per struk.
  - Pie chart: pengeluaran per kategori item.
  - Bar chart: pengeluaran per bulan.
  - Tabel 5 struk terbesar.

Semua grafik menggunakan Plotly. Data kosong ditangani dengan pesan ramah.
"""

import sys
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

from app.db.database import init_db
from app.db.queries import get_summary, get_spending_by_category, get_spending_by_month, get_all_transactions
from app.utils.validator import format_rupiah

init_db()

# ── Palet warna konsisten dengan tema ─────────────────────────────────────────
_COLOR_PRIMARY  = "#1E40AF"   # biru utama
_COLOR_ACCENT   = "#F97316"   # oranye aksen
_COLOR_PIE      = [
    "#1E40AF", "#F97316", "#10B981", "#F59E0B",
    "#6366F1", "#EC4899", "#14B8A6", "#84CC16",
]

# ── Helpers ────────────────────────────────────────────────────────────────────

def _label_kategori(cat: str | None) -> str:
    """Kembalikan label kategori yang lebih mudah dibaca."""
    mapping = {
        "makanan":          "Makanan",
        "minuman":          "Minuman",
        "kebutuhan_rumah":  "Kebutuhan Rumah",
        "perawatan_diri":   "Perawatan Diri",
        "transportasi":     "Transportasi",
        "lainnya":          "Lainnya",
    }
    return mapping.get(cat or "", cat or "—")


def _make_pie_chart(data: list[dict]) -> go.Figure:
    """Buat pie chart pengeluaran per kategori.

    Args:
        data: List dict dengan key 'category' dan 'total'.

    Returns:
        Plotly Figure siap ditampilkan.
    """
    labels = [_label_kategori(r["category"]) for r in data]
    values = [r["total"] for r in data]

    fig = go.Figure(
        go.Pie(
            labels=labels,
            values=values,
            marker=dict(colors=_COLOR_PIE),
            textinfo="label+percent",
            hovertemplate="<b>%{label}</b><br>%{value:,.0f}<br>%{percent}<extra></extra>",
            hole=0.35,   # donut style
        )
    )
    fig.update_layout(
        margin=dict(t=30, b=10, l=10, r=10),
        legend=dict(orientation="v", x=1.02, y=0.5),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=True,
    )
    return fig


def _make_bar_chart(data: list[dict]) -> go.Figure:
    """Buat bar chart pengeluaran per bulan.

    Args:
        data: List dict dengan key 'bulan' (YYYY-MM) dan 'total'.

    Returns:
        Plotly Figure siap ditampilkan.
    """
    months = [r["bulan"] for r in data]
    totals = [r["total"] for r in data]

    # Label bulan dalam Bahasa Indonesia
    _bulan_id = {
        "01": "Jan", "02": "Feb", "03": "Mar", "04": "Apr",
        "05": "Mei", "06": "Jun", "07": "Jul", "08": "Agu",
        "09": "Sep", "10": "Okt", "11": "Nov", "12": "Des",
    }
    labels = []
    for m in months:
        parts = m.split("-")
        if len(parts) == 2:
            labels.append(f"{_bulan_id.get(parts[1], parts[1])} {parts[0]}")
        else:
            labels.append(m)

    fig = go.Figure(
        go.Bar(
            x=labels,
            y=totals,
            marker_color=_COLOR_PRIMARY,
            hovertemplate="<b>%{x}</b><br>Rp %{y:,.0f}<extra></extra>",
            text=[format_rupiah(v) for v in totals],
            textposition="outside",
            textfont=dict(size=11),
        )
    )
    fig.update_layout(
        xaxis=dict(title="Bulan", tickangle=-30),
        yaxis=dict(title="Pengeluaran (Rp)", tickformat=","),
        margin=dict(t=40, b=60, l=60, r=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        bargap=0.35,
    )
    return fig


# ── Halaman ────────────────────────────────────────────────────────────────────

st.title("📊 Dashboard Pengeluaran")
st.caption("Ringkasan dan visualisasi pengeluaran yang tersimpan di database.")

# ── Ambil data ────────────────────────────────────────────────────────────────
summary        = get_summary()
by_category    = get_spending_by_category()
by_month       = get_spending_by_month()
all_tx         = get_all_transactions()

# ── Tangani data kosong ───────────────────────────────────────────────────────
if not all_tx:
    st.info(
        "Belum ada data pengeluaran.  \n"
        "Upload struk pertamamu di halaman **📤 Upload Struk** untuk melihat dashboard."
    )
    st.stop()

# ── Metric cards ──────────────────────────────────────────────────────────────
st.subheader("Ringkasan")

c1, c2, c3 = st.columns(3)
c1.metric(
    label="💰 Total Pengeluaran",
    value=format_rupiah(int(summary.get("total_pengeluaran") or 0)),
)
c2.metric(
    label="🧾 Jumlah Struk",
    value=int(summary.get("jumlah_struk") or 0),
)
rata = summary.get("rata_rata_per_struk") or 0
c3.metric(
    label="📈 Rata-rata per Struk",
    value=format_rupiah(int(rata)),
)

st.divider()

# ── Grafik dua kolom ──────────────────────────────────────────────────────────
col_pie, col_bar = st.columns([1, 1], gap="large")

# ── Pie chart: per kategori ───────────────────────────────────────────────────
with col_pie:
    st.subheader("Pengeluaran per Kategori")
    if by_category:
        fig_pie = _make_pie_chart(by_category)
        st.plotly_chart(fig_pie, use_container_width=True)

        # Tabel pendukung di bawah pie
        cat_df = pd.DataFrame(by_category)
        cat_df["category"] = cat_df["category"].apply(_label_kategori)
        cat_df["total"]    = cat_df["total"].apply(lambda v: format_rupiah(int(v)) if v else "Rp —")
        cat_df = cat_df.rename(columns={"category": "Kategori", "total": "Total"})
        st.dataframe(cat_df, use_container_width=True, hide_index=True)
    else:
        st.info("Belum ada data kategori item.")

# ── Bar chart: per bulan ──────────────────────────────────────────────────────
with col_bar:
    st.subheader("Pengeluaran per Bulan")
    if by_month:
        fig_bar = _make_bar_chart(by_month)
        st.plotly_chart(fig_bar, use_container_width=True)

        # Tabel pendukung di bawah bar
        month_df = pd.DataFrame(by_month)
        _bulan_id_full = {
            "01": "Januari", "02": "Februari", "03": "Maret",
            "04": "April",   "05": "Mei",      "06": "Juni",
            "07": "Juli",    "08": "Agustus",  "09": "September",
            "10": "Oktober", "11": "November", "12": "Desember",
        }

        def _fmt_bulan(m: str) -> str:
            parts = m.split("-")
            if len(parts) == 2:
                return f"{_bulan_id_full.get(parts[1], parts[1])} {parts[0]}"
            return m

        month_df["bulan"] = month_df["bulan"].apply(_fmt_bulan)
        month_df["total"] = month_df["total"].apply(lambda v: format_rupiah(int(v)) if v else "Rp —")
        month_df = month_df.rename(columns={"bulan": "Bulan", "total": "Total"})
        st.dataframe(month_df, use_container_width=True, hide_index=True)
    else:
        st.info("Belum ada data bulanan.")

st.divider()

# ── Tabel 5 struk terbesar ────────────────────────────────────────────────────
st.subheader("5 Struk dengan Pengeluaran Terbesar")

top5_df = (
    pd.DataFrame(all_tx)
    .assign(total_int=lambda df: df["total"].fillna(0).astype(int))
    .sort_values("total_int", ascending=False)
    .head(5)
)

if not top5_df.empty:
    display_cols = ["transaction_date", "store_name", "receipt_number", "total", "payment_method", "validation_status"]
    for col in display_cols:
        if col not in top5_df.columns:
            top5_df[col] = None

    top5_df = top5_df[display_cols].copy()
    top5_df["total"] = top5_df["total"].apply(
        lambda v: format_rupiah(int(v)) if v is not None else "Rp —"
    )
    top5_df = top5_df.rename(columns={
        "transaction_date":  "Tanggal",
        "store_name":        "Toko",
        "receipt_number":    "No. Struk",
        "total":             "Total",
        "payment_method":    "Pembayaran",
        "validation_status": "Status",
    })
    st.dataframe(top5_df, use_container_width=True, hide_index=True)
