"""Server-side SVG QR codes: a few KB, no JavaScript QR library on the phone."""

import io

import segno


def bolt11_svg(bolt11: str) -> str:
    # Uppercase bech32 fits QR alphanumeric mode: denser code, easier scan on cheap cameras.
    qr = segno.make(f"lightning:{bolt11}".upper(), error="m", micro=False)
    buf = io.BytesIO()
    qr.save(buf, kind="svg", scale=1, border=2, dark="#111", light="#fff",
            xmldecl=False, omitsize=True, svgclass=None, lineclass=None)
    return buf.getvalue().decode()
