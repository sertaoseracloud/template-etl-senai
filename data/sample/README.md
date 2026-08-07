# Sample data

This dataset is synthetic. It was invented for this template's example ETL
pipeline. It is not INMET data, not Epagri data, and not any real
meteorological record.

## Files

Three CSVs, one per registered partition date: `temperaturas_2026-01-15.csv`,
`temperaturas_2026-01-16.csv`, `temperaturas_2026-01-17.csv`. Each has the
header `cidade,data_medicao,temp_min,temp_max` and one row per city:
Florianópolis, Joinville, Blumenau, Chapecó, Lages, Criciúma.

## Columns

- `cidade` — city name.
- `data_medicao` — measurement date (`YYYY-MM-DD`), also the Glue partition
  key `data_medicao` once the data lands in the curated bucket. It is a real
  column inside the CSV as well as the partition key, which is why these
  files are uploaded to a flat `temperaturas/` prefix in the raw bucket
  rather than a Hive-style `data_medicao=.../` path — putting the date in
  the S3 key too would give the Phase 2 job two conflicting sources for the
  same column.
- `temp_min` — minimum temperature recorded for the day, in Celsius.
- `temp_max` — maximum temperature recorded for the day, in Celsius.
- `temp_media` — **does not appear in this input.** It is derived on write
  by the Phase 2 `csv_to_parquet` job, and only exists in the curated
  Parquet output that `catalog/bootstrap.py` registers in the Data Catalog.

## Loading

`./run.sh seed` uploads these three files to
`s3://${PROJECT_NAME}-raw/temperaturas/` in the emulated S3 (Floci). It does
not generate the data at runtime — the CSVs are committed here so the input
stays inspectable for someone learning the template.
