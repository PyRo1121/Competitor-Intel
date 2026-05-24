"""SEC Form D bulk ZIP parsing (offline fixture)."""

from __future__ import annotations

import io
import zipfile

from collectors.edgar_form_d_bulk import _read_tsv, _row_cap


def test_read_tsv_from_minimal_zip(tmp_path):
    buf = io.BytesIO()
    tsv = (
        "ACCESSIONNUMBER\tIS_PRIMARYISSUER_FLAG\tENTITYNAME\tENTITYTYPE\n"
        "0001-25-000001\tYES\tAcme AI Software Inc\tCorporation\n"
    )
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("2025Q4_d/ISSUERS.tsv", tsv)
    buf.seek(0)
    with zipfile.ZipFile(buf) as zf:
        rows = _read_tsv(zf, "ISSUERS.tsv")
    assert len(rows) == 1
    assert rows[0]["ENTITYNAME"] == "Acme AI Software Inc"


def test_row_cap_default_is_high_volume():
    assert _row_cap() >= 10000
