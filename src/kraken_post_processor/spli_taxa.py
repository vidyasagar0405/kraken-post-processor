import polars as pl
from typing import Dict


# Define taxonomy levels to extract: (Label, Include_Prefix, Exclude_Prefix)
RANKS = [
    ("Domain", "d__", "p__"),
    ("Phylum", "p__", "c__"),
    ("Class", "c__", "o__"),
    ("Order", "o__", "f__"),
    ("Family", "f__", "g__"),
    ("Genus", "g__", "s__"),
    ("Species", "s__", "t__"),
]


def split_taxa_by_rank(df: pl.LazyFrame) -> Dict[str, pl.LazyFrame]:
    """
    Returns a dictionary of LazyFrames split by taxonomic rank from a LazyFrame with a `lineage` column.
    """
    rank_lfs = {}

    for rank_name, include, exclude in RANKS:
        # Include pattern
        lf = df.filter(pl.col("lineage").str.contains(include))

        # Exclude pattern
        if exclude:
            lf = lf.filter(~pl.col("lineage").str.contains(exclude))

        # Extract rank-specific name
        lf = lf.with_columns(
            [
                pl.col("lineage")
                .str.extract(f"({include}[^|]+)", 1)
                .str.replace(include, "")
                .str.replace("_", " ")
                .alias(rank_name)
            ]
        )

        # Reorder
        lf = lf.select(
            [
                rank_name,
                "lineage",
                "ncbi_tax_id",
                "percentage",
                "reads_direct",
            ]
        )

        rank_lfs[rank_name] = lf

    return rank_lfs
