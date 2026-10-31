"""
app/db/queries.py — Semua query CRUD untuk StrukKu.

Seluruh query menggunakan parameter (?) untuk mencegah SQL injection.
Fungsi mengembalikan dict atau list[dict] agar mudah dipakai di UI.
"""

import json
import sqlite3
from typing import Any

from app.db.database import get_connection


# ── Helpers ───────────────────────────────────────────────────────────────────

def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    """Konversi sqlite3.Row ke dict biasa."""
    return dict(row)


# ── Insert ────────────────────────────────────────────────────────────────────

def insert_transaction(transaction: dict[str, Any], items: list[dict[str, Any]]) -> int:
    """Simpan satu transaksi beserta item-itemnya ke database.

    Args:
        transaction: Dict dengan field sesuai skema tabel transactions.
        items: List dict dengan field sesuai skema tabel transaction_items.

    Returns:
        int: ID transaksi yang baru disimpan.

    Raises:
        sqlite3.DatabaseError: Jika terjadi error saat menulis ke database.
    """
    conn = get_connection()
    try:
        # Serialisasi needs_review_fields ke JSON string jika berupa list
        needs_review = transaction.get("needs_review_fields", [])
        if isinstance(needs_review, list):
            needs_review = json.dumps(needs_review, ensure_ascii=False)

        cur = conn.execute(
            """
            INSERT INTO transactions
                (store_name, store_address, transaction_date, transaction_time,
                 receipt_number, subtotal, discount, tax, total, payment_method,
                 validation_status, needs_review_fields)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                transaction.get("store_name"),
                transaction.get("store_address"),
                transaction.get("transaction_date"),
                transaction.get("transaction_time"),
                transaction.get("receipt_number"),
                transaction.get("subtotal"),
                transaction.get("discount", 0) or 0,
                transaction.get("tax", 0) or 0,
                transaction.get("total"),
                transaction.get("payment_method"),
                transaction.get("validation_status"),
                needs_review,
            ),
        )
        transaction_id = cur.lastrowid

        # Insert semua item sekaligus
        conn.executemany(
            """
            INSERT INTO transaction_items
                (transaction_id, item_name, quantity, unit_price, line_total, category)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    transaction_id,
                    item.get("item_name"),
                    item.get("quantity", 1) or 1,
                    item.get("unit_price"),
                    item.get("line_total"),
                    item.get("category"),
                )
                for item in items
            ],
        )
        conn.commit()
        return transaction_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Select ────────────────────────────────────────────────────────────────────

def get_all_transactions(
    date_from: str | None = None,
    date_to: str | None = None,
    validation_status: str | None = None,
) -> list[dict[str, Any]]:
    """Ambil daftar transaksi dengan filter opsional.

    Args:
        date_from: Batas awal tanggal (YYYY-MM-DD), inklusif.
        date_to:   Batas akhir tanggal (YYYY-MM-DD), inklusif.
        validation_status: "ok", "mismatch", atau None (semua).

    Returns:
        List dict transaksi, diurutkan terbaru dulu.
    """
    clauses: list[str] = []
    params: list[Any] = []

    if date_from:
        clauses.append("transaction_date >= ?")
        params.append(date_from)
    if date_to:
        clauses.append("transaction_date <= ?")
        params.append(date_to)
    if validation_status:
        clauses.append("validation_status = ?")
        params.append(validation_status)

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"SELECT * FROM transactions {where} ORDER BY created_at DESC"

    conn = get_connection()
    try:
        rows = conn.execute(sql, params).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def get_transaction_items(transaction_id: int) -> list[dict[str, Any]]:
    """Ambil semua item untuk satu transaksi.

    Args:
        transaction_id: ID transaksi.

    Returns:
        List dict item.
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM transaction_items WHERE transaction_id = ? ORDER BY id",
            (transaction_id,),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


# ── Duplikat ──────────────────────────────────────────────────────────────────

def check_duplicate(
    store_name: str | None,
    transaction_date: str | None,
    receipt_number: str | None,
    total: int | None,
) -> bool:
    """Cek apakah kombinasi store+date+receipt+total sudah ada di database.

    Returns:
        True jika duplikat ditemukan.
    """
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT 1 FROM transactions
            WHERE store_name = ? AND transaction_date = ?
              AND receipt_number = ? AND total = ?
            LIMIT 1
            """,
            (store_name, transaction_date, receipt_number, total),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


# ── Delete ────────────────────────────────────────────────────────────────────

def delete_transaction(transaction_id: int) -> None:
    """Hapus transaksi dan semua item-nya (CASCADE).

    Args:
        transaction_id: ID transaksi yang akan dihapus.
    """
    conn = get_connection()
    try:
        conn.execute("DELETE FROM transactions WHERE id = ?", (transaction_id,))
        conn.commit()
    finally:
        conn.close()


# ── Agregat (untuk Dashboard) ─────────────────────────────────────────────────

def get_summary() -> dict[str, Any]:
    """Hitung ringkasan keseluruhan pengeluaran.

    Returns:
        Dict dengan key: total_pengeluaran, jumlah_struk, rata_rata_per_struk.
    """
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT
                COALESCE(SUM(total), 0)   AS total_pengeluaran,
                COUNT(*)                   AS jumlah_struk,
                COALESCE(AVG(total), 0)   AS rata_rata_per_struk
            FROM transactions
            """
        ).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def get_spending_by_category() -> list[dict[str, Any]]:
    """Total pengeluaran per kategori item (untuk pie chart).

    Returns:
        List dict dengan key: category, total.
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT category, SUM(line_total) AS total
            FROM transaction_items
            GROUP BY category
            ORDER BY total DESC
            """
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def get_spending_by_month() -> list[dict[str, Any]]:
    """Total pengeluaran per bulan (untuk bar chart).

    Returns:
        List dict dengan key: bulan (YYYY-MM), total.
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT
                SUBSTR(transaction_date, 1, 7) AS bulan,
                SUM(total)                      AS total
            FROM transactions
            WHERE transaction_date IS NOT NULL
            GROUP BY bulan
            ORDER BY bulan ASC
            """
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()
