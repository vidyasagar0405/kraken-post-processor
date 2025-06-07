# kraken_post_processor

Post-processing utility for Kraken2 output. Adds NCBI lineage metadata using an ETE4-compatible taxonomy database and generates summary reports by taxonomic rank.

---

## 🔧 Installation

Install directly from GitHub:

```bash
pip install git+https://github.com/vidyasagar0405/kraken-post-processor.git#egg=kraken-post-processor
```

---

## 📄 Requirements

* Python 3.10+
* Dependencies (auto-installed):
  `polars`, `xlsxwriter`, `ete4` (for lineage lookups)

---

## 🚀 Usage

```bash
kraken_post_processor \
  -i <kraken_report.tsv> \
  -d <taxa.sqlite> \
  -o <output_directory> \
  --xlsx <optional_excel_filename>
```

### Arguments

| Argument        | Description                                                              |
| --------------- | ------------------------------------------------------------------------ |
| `-i / --input`  | Input Kraken report file (`.tsv`)                                        |
| `-d / --db`     | Path to `taxa.sqlite` (ETE4 taxonomy SQLite database)                    |
| `-o / --outdir` | Output directory for per-rank CSVs and auxiliary files                   |
| `--xlsx`        | (Optional) Custom Excel output file name (default: `<outdir>-taxa.xlsx`) |

---

## 📦 Output

When given `-o trial`, the script generates:

```bash
trial/
├── genus.csv
├── species.csv
├── all.csv
├── Unclassified.csv
└── ...
trial-taxa.xlsx  # Combined Excel summary
```

* Columns are auto-fit.
* The second column (`reads_clade`) is hidden in the Excel sheet.

---

## 📚 Lineage Database

You must supply an ETE-compatible `taxa.sqlite` database. You can build this using [ETE Toolkit](http://etetoolkit.org/).

---

## 🧬 Functionality

* Parses Kraken2 report
* Filters unclassified and low-confidence hits
* Maps NCBI TaxIDs to full taxonomic lineages
* Splits output by taxonomic rank
* Saves results as:

  * Individual CSVs (per rank)
  * A combined Excel workbook

---
