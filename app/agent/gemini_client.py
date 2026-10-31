"""
app/agent/gemini_client.py — Klien Google Gemini untuk StrukKu.

Menyediakan dua fungsi publik:
  - extract_from_image(image_bytes, mime_type)  → kirim gambar ke Gemini
  - extract_from_text(text)                     → kirim teks struk ke Gemini

Keduanya mengembalikan dict hasil parsing JSON dari model, atau
melempar GeminiError jika terjadi masalah yang tidak bisa dipulihkan.

Konfigurasi dibaca dari environment (GEMINI_API_KEY, GEMINI_MODEL).
"""

import json
import os
import time
from typing import Any

import httpx
import google.genai as genai
import google.genai.types as t
from google.genai.errors import APIError
from dotenv import load_dotenv

from app.agent.prompt import SYSTEM_PROMPT

# ── Schema JSON yang diminta dari model ───────────────────────────────────────
# Mendefinisikan struktur respons agar model langsung menghasilkan JSON valid.

_ITEM_SCHEMA = t.Schema(
    type="OBJECT",
    properties={
        "item_name":   t.Schema(type="STRING",  nullable=True),
        "quantity":    t.Schema(type="INTEGER", nullable=True),
        "unit_price":  t.Schema(type="INTEGER", nullable=True),
        "line_total":  t.Schema(type="INTEGER", nullable=True),
        "category":    t.Schema(type="STRING",  nullable=True),
    },
)

_TRANSACTION_SCHEMA = t.Schema(
    type="OBJECT",
    properties={
        "store_name":        t.Schema(type="STRING",  nullable=True),
        "store_address":     t.Schema(type="STRING",  nullable=True),
        "transaction_date":  t.Schema(type="STRING",  nullable=True),
        "transaction_time":  t.Schema(type="STRING",  nullable=True),
        "receipt_number":    t.Schema(type="STRING",  nullable=True),
        "subtotal":          t.Schema(type="INTEGER", nullable=True),
        "discount":          t.Schema(type="INTEGER", nullable=True),
        "tax":               t.Schema(type="INTEGER", nullable=True),
        "total":             t.Schema(type="INTEGER", nullable=True),
        "payment_method":    t.Schema(type="STRING",  nullable=True),
    },
)

_RESPONSE_SCHEMA = t.Schema(
    type="OBJECT",
    properties={
        # Kasus normal: struk berhasil diekstrak
        "transaction":           _TRANSACTION_SCHEMA,
        "items":                 t.Schema(type="ARRAY", items=_ITEM_SCHEMA),
        "validation_status":     t.Schema(type="STRING", nullable=True),
        "needs_review_fields":   t.Schema(
            type="ARRAY",
            items=t.Schema(type="STRING"),
            nullable=True,
        ),
        # Kasus error: bukan struk
        "error": t.Schema(type="STRING", nullable=True),
    },
)

# ── Custom exception ───────────────────────────────────────────────────────────

class GeminiError(Exception):
    """Dilempar ketika Gemini gagal atau mengembalikan respons tidak valid."""


# ── Inisialisasi client ────────────────────────────────────────────────────────
# Client di-cache per API key. Jika .env diubah dan Streamlit di-restart,
# client baru otomatis dibuat dengan key yang baru.

_client: genai.Client | None = None
_client_api_key: str = ""          # key yang dipakai client saat ini


def _get_client() -> genai.Client:
    """Kembalikan instance Client, buat ulang jika API key di .env berubah.

    Membaca ulang .env setiap kali dipanggil (override=True) sehingga
    perubahan pada .env langsung terasa tanpa restart Streamlit.

    Raises:
        GeminiError: Jika GEMINI_API_KEY tidak ditemukan di environment.
    """
    global _client, _client_api_key

    # Muat ulang .env agar perubahan setelah startup langsung terdeteksi
    load_dotenv(override=True)

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key or api_key == "your_gemini_api_key_here":
        raise GeminiError(
            "GEMINI_API_KEY belum diset. "
            "Salin .env.example menjadi .env dan isi API key kamu."
        )

    # Buat client baru hanya jika key berubah (atau belum pernah dibuat)
    if _client is None or api_key != _client_api_key:
        _client = genai.Client(
            api_key=api_key,
            http_options=t.HttpOptions(
            timeout=120_000,
            ),
        )

    _client_api_key = api_key

    return _client


def _get_model() -> str:
    """Baca nama model dari environment.

    Raises:
        GeminiError: Jika GEMINI_MODEL tidak ditemukan di .env.
    """
    model = os.getenv("GEMINI_MODEL", "").strip()
    if not model:
        raise GeminiError(
            "GEMINI_MODEL belum diset di file .env. "
            "Tambahkan baris: GEMINI_MODEL=gemini-3.8-flash"
        )
    return model


# ── Config generate (dibuat sekali, dipakai ulang) ────────────────────────────

def _make_config() -> t.GenerateContentConfig:
    """Buat GenerateContentConfig dengan JSON mode dan schema."""
    return t.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        response_mime_type="application/json",
        response_schema=_RESPONSE_SCHEMA,
        temperature=0.1,   # deterministik untuk ekstraksi data
    )


# ── Helper parsing ────────────────────────────────────────────────────────────

def _parse_response(response: t.GenerateContentResponse) -> dict[str, Any]:
    """Ekstrak teks dari respons dan parse sebagai JSON.

    Args:
        response: Objek respons dari Gemini.

    Returns:
        Dict hasil parsing JSON.

    Raises:
        GeminiError: Jika respons kosong atau bukan JSON valid.
    """
    # Ambil teks dari candidate pertama
    try:
        raw_text: str = response.text
    except (AttributeError, IndexError, ValueError) as exc:
        raise GeminiError(
            "Gemini tidak mengembalikan teks. "
            "Coba lagi atau gunakan input teks manual."
        ) from exc

    if not raw_text or not raw_text.strip():
        raise GeminiError("Respons Gemini kosong. Coba lagi.")

    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise GeminiError(
            f"Respons bukan JSON valid: {exc}. "
            "Mungkin ada masalah jaringan atau model. Coba lagi."
        ) from exc

    return data


def _check_bukan_struk(data: dict[str, Any]) -> None:
    """Periksa apakah model mengembalikan {"error": "bukan_struk"}.

    Raises:
        GeminiError: Jika input bukan struk belanja.
    """
    if data.get("error") == "bukan_struk":
        raise GeminiError(
            "Gambar atau teks yang diunggah bukan struk belanja. "
            "Pastikan foto menampilkan struk dengan jelas."
        )



# Kata kunci yang mengindikasikan model tidak tersedia / tidak ditemukan
_MODEL_UNAVAILABLE_KEYWORDS = (
    "no longer available",
    "not found",
    "could not find",
    "deprecated",
    "does not exist",
)

# Kata kunci yang mengindikasikan error sementara yang layak di-retry
_TRANSIENT_KEYWORDS = (
    "high demand",
    "resource exhausted",
    "quota exceeded",
    "rate limit",
    "overloaded",
    "try again",
    "temporarily",
    "503",
    "429",
)

_MAX_RETRIES = 3          # maksimal percobaan ulang
_RETRY_BASE_DELAY = 5.0   # detik — delay awal sebelum retry pertama


def _is_transient(exc: APIError) -> bool:
    """Kembalikan True jika error bersifat sementara dan layak di-retry."""
    raw = (exc.message or str(exc)).lower()
    return any(kw in raw for kw in _TRANSIENT_KEYWORDS) or exc.code in (429, 503)


def _format_api_error(exc: APIError, model: str) -> str:
    """Bentuk pesan error ramah dari APIError.

    Jika error mengindikasikan model tidak tersedia, tampilkan petunjuk
    untuk memperbarui GEMINI_MODEL di .env.

    Args:
        exc:   Instance APIError dari SDK.
        model: Nama model yang sedang dipakai (untuk ditampilkan di pesan).

    Returns:
        String pesan error yang siap ditampilkan di UI.
    """
    raw_msg: str = (exc.message or str(exc)).lower()

    if any(kw in raw_msg for kw in _MODEL_UNAVAILABLE_KEYWORDS):
        return (
            f"Model '{model}' tidak tersedia atau sudah tidak didukung. "
            "Perbarui GEMINI_MODEL di file .env kamu. "
            "Contoh: GEMINI_MODEL=gemini-3.8-flash"
        )

    if _is_transient(exc):
        return (
            "Layanan Gemini sedang mengalami gangguan sementara "
            "atau batas permintaan sedang tercapai. "
            "Sudah dicoba ulang beberapa kali. "
            "Silakan tunggu beberapa menit lalu coba lagi."
        )

    # Error umum lainnya
    friendly = exc.message or str(exc)
    return f"Gagal menghubungi Gemini API: {friendly}"


def _call_with_retry(
    client: genai.Client,
    model: str,
    contents: Any,
    config: t.GenerateContentConfig,
) -> t.GenerateContentResponse:
    """
    Panggil generate_content dengan retry exponential backoff.

    Menangani:
    - Gemini API transient errors
    - HTTPX RemoteProtocolError
    - HTTPX ConnectError
    - HTTPX ReadTimeout
    - HTTPX WriteTimeout
    - HTTPX PoolTimeout
    """

    last_exc: Exception | None = None

    retryable_http_errors = (
        httpx.RemoteProtocolError,
        httpx.ConnectError,
        httpx.ReadTimeout,
        httpx.WriteTimeout,
        httpx.PoolTimeout,
    )

    for attempt in range(1, _MAX_RETRIES + 1):

        try:
            return client.models.generate_content(
                model=model,
                contents=contents,
                config=config,
            )

        except APIError as exc:

            if not _is_transient(exc):
                raise GeminiError(
                    _format_api_error(exc, model)
                ) from exc

            last_exc = exc

        except retryable_http_errors as exc:

            last_exc = exc

        except httpx.TimeoutException as exc:

            last_exc = exc

        # Retry dengan exponential backoff
        if attempt < _MAX_RETRIES:

            delay = _RETRY_BASE_DELAY * (2 ** (attempt - 1))

            print(
                f"[Gemini Retry] Attempt {attempt}/{_MAX_RETRIES} "
                f"gagal: {type(last_exc).__name__}. "
                f"Mencoba lagi dalam {delay} detik..."
            )

            time.sleep(delay)

    # Semua percobaan gagal
    if isinstance(last_exc, APIError):
        message = _format_api_error(last_exc, model)
    else:
        message = (
            "Koneksi ke server Gemini terputus atau mengalami timeout. "
            "Sudah dicoba ulang beberapa kali. "
            "Periksa koneksi internet dan coba kembali."
        )

    raise GeminiError(message) from last_exc

# ── Fungsi publik ─────────────────────────────────────────────────────────────

def extract_from_image(
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
) -> dict[str, Any]:
    """Kirim gambar struk ke Gemini dan kembalikan data terstruktur.

    Args:
        image_bytes: Bytes gambar (JPEG atau PNG).
        mime_type:   MIME type gambar, default "image/jpeg".

    Returns:
        Dict dengan key: transaction, items, validation_status, needs_review_fields.

    Raises:
        GeminiError: Jika API error, bukan struk, atau JSON tidak valid.
    """
    client = _get_client()
    model  = _get_model()
    config = _make_config()

    # Buat parts: gambar + instruksi singkat
    parts = [
        t.Part.from_bytes(data=image_bytes, mime_type=mime_type),
        t.Part.from_text(text="Ekstrak data struk belanja ini."),
    ]

    response = _call_with_retry(client, model, parts, config)

    data = _parse_response(response)
    _check_bukan_struk(data)
    return data


def extract_from_text(text: str) -> dict[str, Any]:
    """Kirim teks struk ke Gemini dan kembalikan data terstruktur.

    Args:
        text: Teks struk yang diketik manual oleh pengguna.

    Returns:
        Dict dengan key: transaction, items, validation_status, needs_review_fields.

    Raises:
        GeminiError: Jika API error, bukan struk, atau JSON tidak valid.
    """
    if not text or not text.strip():
        raise GeminiError("Teks struk tidak boleh kosong.")

    client = _get_client()
    model  = _get_model()
    config = _make_config()

    response = _call_with_retry(client, model, text, config)

    data = _parse_response(response)
    _check_bukan_struk(data)
    return data
