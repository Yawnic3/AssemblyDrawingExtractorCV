from pipeline import PDFPartsPipeline
from excel_exporter import export_to_excel


PDF_PATH = "input/test.pdf"


# =========================================================
# 1. Create pipeline
# =========================================================

pipeline = PDFPartsPipeline(
    pdf_path=PDF_PATH,
    output_root="output/pages"
)


try:

    # =====================================================
    # 2. Process entire PDF
    # =====================================================

    result = (
        pipeline.process_all_pages()
    )


finally:

    # Always close PDF.
    pipeline.close()


# =========================================================
# 3. Summary
# =========================================================

rows = result["rows"]
errors = result["errors"]


print()
print("=" * 80)
print("PIPELINE COMPLETE")
print("=" * 80)

print(
    "Rows extracted:",
    len(rows)
)

print(
    "Pages with errors:",
    len(errors)
)


# =========================================================
# 4. Preview records
# =========================================================

print()
print("FIRST 10 RECORDS")
print("-" * 80)

for row in rows[:10]:

    print(
        row["page"],
        "|",
        row["assembly"],
        "|",
        row["item"],
        "|",
        row["part_name"],
        "|",
        row["qty"],
        "|",
        row["stock_name"],
        "|",
        row["weight_kg"]
    )


# =========================================================
# 5. Export Excel
# =========================================================

export_to_excel(
    rows=rows,
    errors=errors,
    output_path="output/master_bom.xlsx"
)