#!/usr/bin/env python

import argparse
import os
from pathlib import Path

import xlsxwriter
import polars as pl
from build_taxa_lineage import build_lineage_map
from kraken_post_processor.spli_taxa import split_taxa_by_rank


def ensure_outdir(outdir: str) -> None:
    Path(outdir).mkdir(parents=True, exist_ok=True)


def load_kraken_report(filepath: str) -> pl.LazyFrame:
    df = pl.read_csv(filepath, separator="\t", has_header=False).lazy()
    return df.rename(
        {
            "column_1": "percentage",
            "column_2": "reads_clade",
            "column_3": "reads_direct",
            "column_4": "rank_code",
            "column_5": "ncbi_tax_id",
            "column_6": "name",
        }
    )


def preprocess(df: pl.LazyFrame) -> tuple[pl.LazyFrame, pl.LazyFrame]:
    taxa_df = df.select(
        [
            pl.col("ncbi_tax_id").cast(pl.Int64),
            pl.col("reads_direct").cast(pl.Int64),
            pl.col("percentage").str.strip_chars().cast(pl.Float64),
        ]
    )

    unclassified = taxa_df.filter(pl.col("ncbi_tax_id") == 0)
    classified = taxa_df.filter(
        (pl.col("ncbi_tax_id") != 0) & (pl.col("reads_direct") != 0)
    )

    return unclassified, classified


def attach_lineage(classified: pl.LazyFrame, db_path: str) -> pl.LazyFrame:
    taxid_list = (
        classified.select("ncbi_tax_id").unique().collect()["ncbi_tax_id"].to_list()
    )
    lineage_dict = build_lineage_map(taxid_list, dbfile=db_path)

    lineage_lf = pl.DataFrame(
        {
            "ncbi_tax_id": list(lineage_dict.keys()),
            "lineage": list(lineage_dict.values()),
        }
    ).lazy()

    return classified.join(lineage_lf, on="ncbi_tax_id", how="left")


def combine_and_filter(
    unclassified: pl.LazyFrame, classified_with_lineage: pl.LazyFrame
) -> pl.DataFrame:

    unclassified = unclassified.with_columns([pl.lit("unclassified").alias("lineage")])
    combined = pl.concat([unclassified, classified_with_lineage])

    return (
        combined.filter((pl.col("lineage").is_not_null()) & (pl.col("lineage") != ""))
        .select(["lineage", "ncbi_tax_id", "reads_direct", "percentage"])
        .collect()
    )


def write_outputs_to_dir(
    rank_dfs: dict[str, pl.LazyFrame],
    combined: pl.DataFrame,
    outdir: str,
    excel_file: str,
    include_combined: bool = True,
    include_unclassified: bool = True,
):
    ensure_outdir(outdir)
    sheets = {}

    # CSV outputs
    for rank, lf in rank_dfs.items():
        df = lf.collect()
        df.write_csv(f"{outdir}/{rank}.csv")
        sheets[rank] = df

    if include_combined:
        combined.write_csv(f"{outdir}/all.csv")
        sheets["all"] = combined

    if include_unclassified:
        unclassified = combined.filter(pl.col("lineage") == "unclassified")
        unclassified.write_csv(f"{outdir}/Unclassified.csv")
        sheets["Unclassified"] = unclassified

    # Excel output
    with xlsxwriter.Workbook(excel_file) as workbook:
        for sheet_name, df in sheets.items():
            worksheet = workbook.add_worksheet(sheet_name[:31])
            max_widths = [len(str(col)) for col in df.columns]

            for col_idx, col_name in enumerate(df.columns):
                worksheet.write(0, col_idx, col_name)

            for row_idx, row in enumerate(df.rows(), start=1):
                for col_idx, val in enumerate(row):
                    val_str = str(val)
                    worksheet.write(row_idx, col_idx, val)
                    max_widths[col_idx] = max(max_widths[col_idx], len(val_str))

            for col_idx, width in enumerate(max_widths):
                if col_idx == 1:
                    worksheet.set_column(col_idx, col_idx, None, None, {"hidden": True})
                else:
                    worksheet.set_column(col_idx, col_idx, min(width + 2, 50))

    print(
        f"All outputs written to:\n  Directory: {outdir}/\n  Excel file: {excel_file}"
    )


def parse_args():
    parser = argparse.ArgumentParser(
        description="Process Kraken2 report and attach NCBI lineage using ETE database."
    )
    parser.add_argument(
        "-i", "--input", required=True, help="Input Kraken report file (.tsv)"
    )
    parser.add_argument(
        "-d",
        "--db",
        help="Path to ETE SQLite taxa.sqlite (taxonomy database file)",
    )
    parser.add_argument(
        "-o",
        "--outdir",
        default=None,
        help="Output directory (default: '<input_base>-taxa/')",
    )
    parser.add_argument(
        "-e",
        "--xlsx",
        default=None,
        help="Optional Excel output file name (default: '<outdir>-taxa.xlsx')",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    input_basename = os.path.splitext(os.path.basename(args.input))[0]
    outdir = args.outdir or f"{input_basename}-taxonomy"
    excel_file = args.xlsx or f"{outdir}taxa.xlsx"

    df = load_kraken_report(args.input)
    unclassified, classified = preprocess(df)
    classified_with_lineage = attach_lineage(classified, args.db)

    all_rank_dfs = split_taxa_by_rank(classified_with_lineage)
    result = combine_and_filter(unclassified, classified_with_lineage)

    write_outputs_to_dir(all_rank_dfs, result, outdir, excel_file)


if __name__ == "__main__":
    main()
