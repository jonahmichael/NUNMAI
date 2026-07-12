"""
qr_tool.py — investor-facing QR/hash lookup tool.

Generates a QR code encoding a verification URL (not raw data) so a
retail investor can scan a code printed/embedded in a SEBI circular,
broker email footer, etc. and land straight on a human-readable
verification result, without needing to understand tokens or hashes
themselves.
"""

import io
import qrcode


def build_verification_url(token: str, base_url: str = "https://verify.nunmai.in") -> str:
    return f"{base_url}/v/{token}"


def generate_qr_png_bytes(token: str, base_url: str = "https://verify.nunmai.in") -> bytes:
    """Returns raw PNG bytes for the QR code. Used by the API's
    GET /qr/{token} endpoint (StreamingResponse) and by anything that
    wants to embed the QR directly into a generated PDF/email footer."""
    url = build_verification_url(token, base_url)
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=2,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()