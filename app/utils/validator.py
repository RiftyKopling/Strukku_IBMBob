"""
app/utils/validator.py — Validasi matematis struk belanja.

Validasi dilakukan di sisi aplikasi (bukan oleh model AI) sehingga
hasilnya menimpa nilai validation_status yang dikembalikan Gemini.

Aturan:
  Cek 1: sum(item.line_total) == subtotal         (toleransi ±1)
  Cek 2: subtotal - discount + tax == total        (toleransi ±1)
  Jika salah satu gagal → validation_status = "mismatch"
  Jika semua lulus     → validation_status = "ok"
"""

from typing import Any


_TOLERANCE = 1  # toleransi pembulatan rupiah


def _to_int(value: Any, default: int = 0) -> int:
    """Konversi nilai ke int; kembalikan default jika None atau tidak valid."""
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def validate_receipt(
    transaction: dict[str, Any],
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    """Validasi struk dan kembalikan transaction yang sudah diperbarui.

    Fungsi ini MEMODIFIKASI salinan transaction (tidak in-place) dengan
    mengisi ulang ``validation_status`` dan menambahkan entri ke
    ``needs_review_fields`` jika ada field numerik yang None.

    Args:
        transaction: Dict field transaksi (subtotal, discount, tax, total, dst.).
        items: List dict item (masing-masing memiliki line_total).

    Returns:
        Dict transaction yang sudah diperbarui dengan validation_status yang benar.
    """
    result = dict(transaction)  # salin agar tidak mengubah aslinya

    subtotal  = _to_int(result.get("subtotal"))
    discount  = _to_int(result.get("discount"), 0)
    tax       = _to_int(result.get("tax"), 0)
    total     = _to_int(result.get("total"))

    # Kumpulkan needs_review_fields yang sudah ada dari model
    existing_review: list[str] = list(result.get("needs_review_fields") or [])

    # Tandai field numerik yang kosong (None) sebagai needs review
    for field in ("subtotal", "total"):
        if result.get(field) is None and field not in existing_review:
            existing_review.append(field)

    # ── Cek 1: jumlah line_total item == subtotal ──────────────────────────
    sum_items = sum(_to_int(item.get("line_total")) for item in items)
    cek1_ok = abs(sum_items - subtotal) <= _TOLERANCE

    # ── Cek 2: subtotal - discount + tax == total ──────────────────────────
    expected_total = subtotal - discount + tax
    cek2_ok = abs(expected_total - total) <= _TOLERANCE

    # ── Tentukan status ────────────────────────────────────────────────────
    if cek1_ok and cek2_ok:
        result["validation_status"] = "ok"
    else:
        result["validation_status"] = "mismatch"
        # Tambahkan keterangan field yang bermasalah ke needs_review_fields
        if not cek1_ok and "subtotal" not in existing_review:
            existing_review.append("subtotal")
        if not cek2_ok and "total" not in existing_review:
            existing_review.append("total")

    result["needs_review_fields"] = existing_review
    return result


def format_rupiah(amount: int | None) -> str:
    """Format integer rupiah ke string ber-separator titik, misal 15000 → 'Rp 15.000'.

    Args:
        amount: Nilai rupiah sebagai integer.

    Returns:
        String rupiah yang sudah diformat, atau 'Rp —' jika None.
    """
    if amount is None:
        return "Rp —"
    return f"Rp {amount:,}".replace(",", ".")
