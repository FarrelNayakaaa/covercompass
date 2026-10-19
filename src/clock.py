"""Tanggal 'hari ini'. Bisa dipatok lewat variabel CC_TODAY (YYYY-MM-DD) supaya demo dan test selalu
menghasilkan angka yang sama, sebab polis contoh punya tanggal mulai dan berakhir."""
import os
from datetime import date


def today() -> date:
    v = os.getenv("CC_TODAY")
    return date.fromisoformat(v) if v else date.today()
