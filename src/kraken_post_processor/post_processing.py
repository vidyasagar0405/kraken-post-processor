#!/usr/bin/env python

import argparse
import polars as pl
from build_taxa_lineage import build_lineage_map


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


def save_outputs(df: pl.DataFrame, output_file: str) -> None:
    df.write_excel(
        output_file,
        worksheet="all",
        autofit=True,
    )
    print(f"Output saved to: {output_file}")
    print(f"Estimated memory usage: {df.estimated_size('mb')} MB")


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
        required=True,
        help="Path to ETE SQLite taxa.sqlite (taxonomy database file)",
    )
    parser.add_argument(
        "-o", "--output", required=True, help="Output Excel file (.xlsx)"
    )
    return parser.parse_args()


def main():
    args = parse_args()
    df = load_kraken_report(args.input)
    unclassified, classified = preprocess(df)
    classified_with_lineage = attach_lineage(classified, args.db)
    result = combine_and_filter(unclassified, classified_with_lineage)
    save_outputs(result, args.output)


if __name__ == "__main__":
    main()