"""
app/db/database.py — Koneksi dan inisialisasi database SQLite.

Penggunaan:
    from app.db.database import get_connection, init_db
    init_db()                  # dipanggil sekali saat aplikasi start
    conn = get_connection()    # ambil koneksi untuk query
"""

import sqlite3
import os
from pathlib import Path

# Lokasi file database — satu level di atas folder app/ (root project)
_DB_PATH = Path(__file__).resolve().parents[2] / "strukku.db"


def get_connection() -> sqlite3.Connection:
    """Kembalikan koneksi SQLite dengan row_factory dan foreign keys aktif.

    Returns:
        sqlite3.Connection: Koneksi siap pakai; tutup setelah selesai.
    """
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row          # akses kolom by name
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """Buat tabel jika belum ada (idempotent — aman dipanggil berkali-kali)."""
    conn = get_connection()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS transactions (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                store_name          TEXT,
                store_address       TEXT,
                transaction_date    TEXT,
                transaction_time    TEXT,
                receipt_number      TEXT,
                subtotal            INTEGER,
                discount            INTEGER DEFAULT 0,
                tax                 INTEGER DEFAULT 0,
                total               INTEGER,
                payment_method      TEXT,
                validation_status   TEXT,
                needs_review_fields TEXT,           -- JSON array serialized
                created_at          TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS transaction_items (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                transaction_id  INTEGER NOT NULL
                                    REFERENCES transactions(id) ON DELETE CASCADE,
                item_name       TEXT,
                quantity        INTEGER DEFAULT 1,
                unit_price      INTEGER,
                line_total      INTEGER,
                category        TEXT
            );
            """
        )
        conn.commit()
    finally:
        conn.close()
