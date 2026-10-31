"""
tests/test_validator.py — Pytest untuk app/utils/validator.py.

Jalankan:
    pytest tests/ -v
"""

import json
import sys
import os
from pathlib import Path

# Pastikan root project ada di sys.path agar import app.* berfungsi
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest
from app.utils.validator import validate_receipt, format_rupiah


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_data() -> tuple[dict, list[dict]]:
    """Muat data struk sampel dari tests/sample_receipt.json."""
    path = Path(__file__).parent / "sample_receipt.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["transaction"], data["items"]


# ── Kasus: data valid ─────────────────────────────────────────────────────────

def test_valid_receipt_status_ok(sample_data):
    """Struk dengan matematika benar harus menghasilkan status 'ok'."""
    transaction, items = sample_data
    result = validate_receipt(transaction, items)
    assert result["validation_status"] == "ok"


def test_valid_receipt_no_review_fields(sample_data):
    """Struk valid tidak boleh menambahkan field ke needs_review_fields."""
    transaction, items = sample_data
    result = validate_receipt(transaction, items)
    assert result["needs_review_fields"] == []


def test_valid_receipt_does_not_mutate_original(sample_data):
    """validate_receipt tidak boleh mengubah dict asli (immutable pattern)."""
    transaction, items = sample_data
    original_status = transaction.get("validation_status")
    validate_receipt(transaction, items)
    assert transaction.get("validation_status") == original_status


# ── Kasus: Cek 1 gagal (sum items ≠ subtotal) ────────────────────────────────

def test_cek1_mismatch_sum_items_wrong():
    """Jika sum(line_total) ≠ subtotal → status mismatch."""
    transaction = {
        "subtotal": 20000, "discount": 0, "tax": 0, "total": 20000
    }
    items = [{"line_total": 10000}, {"line_total": 5000}]  # sum = 15000, bukan 20000
    result = validate_receipt(transaction, items)
    assert result["validation_status"] == "mismatch"


def test_cek1_mismatch_adds_subtotal_to_review():
    """Cek 1 gagal → 'subtotal' masuk ke needs_review_fields."""
    transaction = {
        "subtotal": 20000, "discount": 0, "tax": 0, "total": 20000
    }
    items = [{"line_total": 15000}]
    result = validate_receipt(transaction, items)
    assert "subtotal" in result["needs_review_fields"]


# ── Kasus: Cek 2 gagal (subtotal - discount + tax ≠ total) ───────────────────

def test_cek2_mismatch_total_wrong():
    """Jika subtotal - discount + tax ≠ total → status mismatch."""
    transaction = {
        "subtotal": 20000, "discount": 2000, "tax": 0, "total": 20000  # harusnya 18000
    }
    items = [{"line_total": 20000}]
    result = validate_receipt(transaction, items)
    assert result["validation_status"] == "mismatch"


def test_cek2_mismatch_adds_total_to_review():
    """Cek 2 gagal → 'total' masuk ke needs_review_fields."""
    transaction = {
        "subtotal": 20000, "discount": 2000, "tax": 0, "total": 20000
    }
    items = [{"line_total": 20000}]
    result = validate_receipt(transaction, items)
    assert "total" in result["needs_review_fields"]


# ── Kasus: toleransi ±1 ───────────────────────────────────────────────────────

def test_tolerance_within_1_ok():
    """Selisih 1 rupiah karena pembulatan masih boleh → status ok."""
    transaction = {
        "subtotal": 10000, "discount": 0, "tax": 0, "total": 10001  # selisih 1
    }
    items = [{"line_total": 10000}]
    result = validate_receipt(transaction, items)
    assert result["validation_status"] == "ok"


def test_tolerance_exceeds_1_mismatch():
    """Selisih lebih dari 1 rupiah harus menjadi mismatch."""
    transaction = {
        "subtotal": 10000, "discount": 0, "tax": 0, "total": 10002  # selisih 2
    }
    items = [{"line_total": 10000}]
    result = validate_receipt(transaction, items)
    assert result["validation_status"] == "mismatch"


# ── Kasus: nilai None ─────────────────────────────────────────────────────────

def test_none_subtotal_treated_as_zero():
    """subtotal=None diperlakukan sebagai 0; jika total juga 0 → ok."""
    transaction = {
        "subtotal": None, "discount": 0, "tax": 0, "total": None
    }
    items = []
    result = validate_receipt(transaction, items)
    # sum items = 0 == subtotal(0) → cek1 ok; 0-0+0=0 == total(0) → cek2 ok
    assert result["validation_status"] == "ok"


def test_none_fields_added_to_needs_review():
    """Field 'subtotal' dan 'total' yang None harus masuk needs_review_fields."""
    transaction = {
        "subtotal": None, "discount": 0, "tax": 0, "total": None
    }
    items = []
    result = validate_receipt(transaction, items)
    assert "subtotal" in result["needs_review_fields"]
    assert "total" in result["needs_review_fields"]


# ── Kasus: dengan pajak dan diskon ────────────────────────────────────────────

def test_with_tax_and_discount_ok():
    """Struk dengan diskon dan pajak: subtotal=50000, disc=5000, tax=2000, total=47000."""
    transaction = {
        "subtotal": 50000, "discount": 5000, "tax": 2000, "total": 47000
    }
    items = [
        {"line_total": 30000},
        {"line_total": 20000},
    ]
    result = validate_receipt(transaction, items)
    assert result["validation_status"] == "ok"


# ── Kasus: needs_review_fields dari model tidak terhapus ─────────────────────

def test_existing_review_fields_preserved():
    """Field needs_review_fields dari model tetap dipertahankan oleh validator."""
    transaction = {
        "subtotal": 10000, "discount": 0, "tax": 0, "total": 10000,
        "needs_review_fields": ["store_name"]
    }
    items = [{"line_total": 10000}]
    result = validate_receipt(transaction, items)
    assert "store_name" in result["needs_review_fields"]
    assert result["validation_status"] == "ok"


# ── format_rupiah ─────────────────────────────────────────────────────────────

def test_format_rupiah_basic():
    assert format_rupiah(15000) == "Rp 15.000"


def test_format_rupiah_million():
    assert format_rupiah(1500000) == "Rp 1.500.000"


def test_format_rupiah_zero():
    assert format_rupiah(0) == "Rp 0"


def test_format_rupiah_none():
    assert format_rupiah(None) == "Rp —"
