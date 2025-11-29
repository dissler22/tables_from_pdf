"""
Extraction complète du PDF SDP (150+ pages) vers data/output/SDP_full.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from table_extractor.sdp_extractor import SDPExtractor


def main() -> None:
    pdf_path = Path("data/upload/SDP Série D Ind A.pdf")
    output_dir = Path("data/output/SDP_full")
    output_dir.mkdir(parents=True, exist_ok=True)

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF introuvable: {pdf_path}")

    extractor = SDPExtractor()
    pages = extractor.extract_all_pages(pdf_path)
    total_pages = len(pages)

    print(f"[SDP] Extraction complète : {pdf_path.name} ({total_pages} pages)")

    if total_pages == 0:
        print("Aucune page extraite, arrêt.")
        return

    # Sauvegarde JSON consolidé
    pages_dict = []
    for page in pages:
        page_dict = extractor.to_dict(page)
        # Utilisateur préfère un index 1-based
        page_dict["page_number"] = page_dict["page_number"] + 1
        pages_dict.append(page_dict)

        # Sauvegarde par page pour debug (optionnel mais pratique)
        per_page_path = output_dir / f"page{page_dict['page_number']}.json"
        with open(per_page_path, "w", encoding="utf-8") as f_page:
            json.dump(page_dict, f_page, ensure_ascii=False, indent=2)

    full_json = {
        "pdf": pdf_path.name,
        "total_pages": total_pages,
        "pages": pages_dict,
    }

    json_path = output_dir / "sdp_full.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(full_json, f, ensure_ascii=False, indent=2)

    print(f"[SDP] JSON consolidé : {json_path}")

    # Sauvegarde CSV à plat
    csv_path = output_dir / "sdp_all_rows.csv"
    with open(csv_path, "w", encoding="utf-8", newline="") as f_csv:
        writer = None

        for page in pages:
            flat_rows = extractor.to_flat_rows(page)
            headers = ["Page"] + flat_rows[0]

            if writer is None:
                writer = csv.writer(f_csv)
                writer.writerow(headers)

            for row in flat_rows[1:]:
                writer.writerow([page.page_number + 1] + row)

    print(f"[SDP] CSV consolidé : {csv_path}")
    print("[SDP] Terminé ✅")


if __name__ == "__main__":
    main()