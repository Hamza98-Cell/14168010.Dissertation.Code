import csv
import os
import psycopg2
from psycopg2 import sql
from datetime import datetime

# --------------------
# FOLDERS
# --------------------
input_folder = r"C:\Yorkshire Water\Data"
output_folder = r"C:\Yorkshire Water\Cleaned_CSV"
os.makedirs(output_folder, exist_ok=True)

# --------------------
# DB PARAMETERS
# --------------------
DB_PARAMS = {
    "host": "localhost",
    "dbname": "data_automation",
    "user": "postgres",
    "password": "hello786"
}

# --------------------
# FIELDS TO KEEP
# --------------------
fields_to_keep = [
    "@id",
    "sample.samplingPoint.label",
    "sample.sampleDateTime",
    "determinand.label",
    "determinand.notation",
    "result",
    "determinand.unit.label",
    "sample.sampledMaterialType.label",
    "sample.samplingPoint.easting",
    "sample.samplingPoint.northing",
    "ingested_at"  # version control
]

# --------------------
# TABLE NAME
# --------------------
table_name = "bio_lead_rivers"

# --------------------
# CONFIGURATION: FILTERS
# --------------------
# You can change these two values for different runs
MATERIAL_TYPE_TO_KEEP = ["RIVER / RUNNING SURFACE WATER"] #add more identifies using "" and , within the item
DETERMINAND_CODE_TO_KEEP = ["3377"]

# --------------------
# CONNECT TO DATABASE
# --------------------
conn = psycopg2.connect(**DB_PARAMS)
cur = conn.cursor()

# --------------------
# CREATE TABLE WITH CORRECT DATA TYPES
# --------------------
create_table_query = f"""
CREATE TABLE IF NOT EXISTS {table_name} (
    "@id" TEXT,
    "sample.samplingPoint.label" TEXT,
    "sample.sampleDateTime" TIMESTAMP,
    "determinand.label" TEXT,
    "determinand.notation" TEXT,
    "result" NUMERIC,
    "determinand.unit.label" TEXT,
    "sample.sampledMaterialType.label" TEXT,
    "sample.samplingPoint.easting" INTEGER,
    "sample.samplingPoint.northing" INTEGER,
    "ingested_at" TIMESTAMP
)
"""
cur.execute(create_table_query)
conn.commit()
print(f"[✓] Table {table_name} ready with correct data types.")

# --------------------
# PROCESS CSV FILES
# --------------------
for file in os.listdir(input_folder):
    if file.lower().endswith(".csv"):
        input_file = os.path.join(input_folder, file)
        output_file = os.path.join(output_folder, f"cleaned_{file}")

        print(f"Processing file: {input_file}")

        with open(input_file, newline="", encoding="utf-8") as infile, \
             open(output_file, "w", newline="", encoding="utf-8") as outfile:

            reader = csv.DictReader(infile)
            writer = csv.DictWriter(outfile, fieldnames=fields_to_keep)
            writer.writeheader()

            rows_to_insert = []

            for row in reader:
                if (
                    row.get("determinand.notation") in DETERMINAND_CODE_TO_KEEP and
                    row.get("sample.sampledMaterialType.label") in MATERIAL_TYPE_TO_KEEP
                ):
                    new_row = {k: row.get(k, "") for k in fields_to_keep}

                    # Clean @id
                    new_row["@id"] = new_row["@id"].split("/")[-1] if new_row["@id"] else ""

                    # Convert numeric fields
                    try:
                        new_row["result"] = float(new_row["result"]) if new_row["result"] else None
                        new_row["sample.samplingPoint.easting"] = int(float(new_row["sample.samplingPoint.easting"])) if new_row["sample.samplingPoint.easting"] else None
                        new_row["sample.samplingPoint.northing"] = int(float(new_row["sample.samplingPoint.northing"])) if new_row["sample.samplingPoint.northing"] else None
                    except ValueError:
                        continue  # skip rows with invalid numeric data

                    # Convert datetime field
                    try:
                        new_row["sample.sampleDateTime"] = new_row["sample.sampleDateTime"] if new_row["sample.sampleDateTime"] else None
                    except ValueError:
                        continue

                    # Add ingested timestamp
                    new_row["ingested_at"] = datetime.now()

                    writer.writerow(new_row)
                    rows_to_insert.append([new_row[col] for col in fields_to_keep])

        print(f"[✓] Saved cleaned file: {output_file}")

        # --------------------
        # INSERT INTO DATABASE
        # --------------------
        if rows_to_insert:
            insert_query = sql.SQL(
                "INSERT INTO {} ({}) VALUES ({})"
            ).format(
                sql.Identifier(table_name),
                sql.SQL(", ").join(map(sql.Identifier, fields_to_keep)),
                sql.SQL(", ").join(sql.Placeholder() * len(fields_to_keep))
            )
            cur.executemany(insert_query, rows_to_insert)
            conn.commit()
            print(f"[✓] Inserted {len(rows_to_insert)} rows into table {table_name}")
        else:
            print(f"[!] No matching rows found for {file}")

# --------------------
# CLOSE DB CONNECTION
# --------------------
cur.close()
conn.close()
print("All files processed.")
