"""Recursive note discovery and filename-collision disambiguation — a real
case found in this project's actual dataset: a Google-Drive export with
the same-named daily PDF repeated under two different month folders
(same filename, genuinely different content). Uses PDFs with a native
text layer throughout, so no OCR engine is needed (process_pdf's own
native-text-layer path bypasses OCR entirely when enough text is
extractable — see _MIN_NATIVE_TEXT_CHARS).
"""
from __future__ import annotations

import json

from scripts.ingest_notes import disambiguated_stem, main


def _make_simple_pdf(text: str) -> bytes:
    content_stream = f"BT /F1 12 Tf 50 750 Td ({text}) Tj ET"
    content_len = len(content_stream)
    pdf = (
        "%PDF-1.4\n"
        "1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        "2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        "3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        "/Contents 4 0 R /Resources << /Font << /F1 << /Type /Font "
        "/Subtype /Type1 /BaseFont /Helvetica >> >> >> >>\nendobj\n"
        f"4 0 obj\n<< /Length {content_len} >>\nstream\n"
        f"{content_stream}\nendstream\nendobj\n"
        "xref\n0 5\n"
        "0000000000 65535 f \n"
        "0000000009 00000 n \n"
        "0000000058 00000 n \n"
        "0000000115 00000 n \n"
        "0000000266 00000 n \n"
        "trailer\n<< /Size 5 /Root 1 0 R >>\n"
        "startxref\n0\n%%EOF"
    )
    return pdf.encode("latin-1")


def test_disambiguated_stem_unchanged_for_top_level_file(tmp_path):
    from pathlib import Path
    assert disambiguated_stem(Path("Notes.pdf")) == "Notes"


def test_disambiguated_stem_prefixes_with_immediate_parent_for_nested_file():
    from pathlib import Path
    assert disambiguated_stem(Path("April/Apr05_2021.pdf")) == "April_Apr05_2021"
    assert disambiguated_stem(Path("04_Apr/Apr05_2021.pdf")) == "04_Apr_Apr05_2021"


def test_main_discovers_pdfs_nested_in_subdirectories(tmp_path):
    input_dir = tmp_path / "raw"
    output_dir = tmp_path / "ocr"
    nested = input_dir / "04_Apr"
    nested.mkdir(parents=True)
    (nested / "Apr05_2021.pdf").write_bytes(_make_simple_pdf("April content, lots of real native text here."))

    exit_code = main(["--input", str(input_dir), "--output", str(output_dir)])

    assert exit_code == 0
    assert (output_dir / "04_Apr_Apr05_2021.jsonl").exists()


def test_same_named_files_in_different_folders_do_not_collide(tmp_path):
    input_dir = tmp_path / "raw"
    output_dir = tmp_path / "ocr"
    folder_a = input_dir / "04_Apr"
    folder_b = input_dir / "April"
    folder_a.mkdir(parents=True)
    folder_b.mkdir(parents=True)
    (folder_a / "Apr05_2021.pdf").write_bytes(_make_simple_pdf("Content from the 04_Apr folder, genuinely different text."))
    (folder_b / "Apr05_2021.pdf").write_bytes(_make_simple_pdf("Content from the April folder, a totally different document."))

    exit_code = main(["--input", str(input_dir), "--output", str(output_dir)])

    assert exit_code == 0
    out_a = output_dir / "04_Apr_Apr05_2021.jsonl"
    out_b = output_dir / "April_Apr05_2021.jsonl"
    assert out_a.exists() and out_b.exists()

    record_a = json.loads(out_a.read_text(encoding="utf-8").splitlines()[0])
    record_b = json.loads(out_b.read_text(encoding="utf-8").splitlines()[0])
    assert "04_Apr folder" in record_a["text"]
    assert "April folder" in record_b["text"]
    assert record_a["source_id"] != record_b["source_id"]
    assert record_a["content_id"] != record_b["content_id"]


def test_record_source_is_the_relative_path_for_nested_files(tmp_path):
    input_dir = tmp_path / "raw"
    output_dir = tmp_path / "ocr"
    nested = input_dir / "Filters-1"
    nested.mkdir(parents=True)
    (nested / "Analog Filters.pdf").write_bytes(_make_simple_pdf("Some filter notes with enough native text."))

    main(["--input", str(input_dir), "--output", str(output_dir)])

    record = json.loads((output_dir / "Filters-1_Analog Filters.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert record["source"] == "Filters-1/Analog Filters.pdf"


def test_top_level_file_naming_is_unchanged_from_before(tmp_path):
    """Backward compatibility: a file directly in the input root (today's
    existing flat layout) keeps its exact original filename-based naming."""
    input_dir = tmp_path / "raw"
    output_dir = tmp_path / "ocr"
    input_dir.mkdir(parents=True)
    (input_dir / "DFT.pdf").write_bytes(_make_simple_pdf("Top level file with plenty of native text content."))

    main(["--input", str(input_dir), "--output", str(output_dir)])

    assert (output_dir / "DFT.jsonl").exists()
    record = json.loads((output_dir / "DFT.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert record["source"] == "DFT.pdf"
    assert record["source_id"] == "DFT"
