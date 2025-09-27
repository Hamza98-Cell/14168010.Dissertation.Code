import requests
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime
import time

# --------------------
# CONFIG
# --------------------
DB_PARAMS = {
    "host": "localhost",
    "dbname": "data_automation",
    "user": "postgres",
    "password": "hello786"
}

TABLE_NAME = "lead_rivers_lead"
AREA_CODE = "3-34"
DETERMINAND = "0050"
MATERIAL_TYPE_TO_KEEP = "RIVER / RUNNING SURFACE WATER"   # Change this as needed
API_URL = "https://environment.data.gov.uk/water-quality/data/measurement"
BATCH_SIZE = 100        # increase if stable
CHUNK_SIZE = 200         # rows per DB insert
PAUSE_BETWEEN_BATCHES = 0.5  # seconds

# --------------------
# CONNECT TO DATABASE
# --------------------
conn = psycopg2.connect(**DB_PARAMS)
cur = conn.cursor()

# Ensure unique constraint on @id (once, safe to re-run)
try:
    cur.execute(f'ALTER TABLE {TABLE_NAME} ADD CONSTRAINT uq_id UNIQUE ("@id")')
    conn.commit()
except psycopg2.errors.UniqueViolation:
    conn.rollback()
except psycopg2.errors.DuplicateTable:
    conn.rollback()
except Exception:
    conn.rollback()

# --------------------
# GET LATEST RECORD DATE
# --------------------
cur.execute(f'SELECT MAX("sample.sampleDateTime") FROM {TABLE_NAME} WHERE "determinand.notation" = %s', (DETERMINAND,))
last_dt = cur.fetchone()[0]
start_date = (last_dt.date() if last_dt else datetime(2000, 1, 1).date()).strftime("%Y-%m-%d")

print(f"Fetching records since {start_date}")

# --------------------
# FETCH DATA
# --------------------
def fetch_api_batch(start_date, offset=0):
    params = {
        "area": AREA_CODE,
        "determinand": DETERMINAND,
        "startDate": start_date,
        "_limit": BATCH_SIZE,
        "_offset": offset
    }
    r = requests.get(API_URL, params=params, timeout=60)
    r.raise_for_status()
    return r.json().get("items", [])

# --------------------
# PREPARE ROWS
# --------------------
def prepare_rows(records):
    rows = []
    for rec in records:
        try:
            samp = rec.get("sample", {}) or {}
            sp   = samp.get("samplingPoint", {}) or {}
            detd = rec.get("determinand", {}) or {}
            unit = detd.get("unit", {}) or {}

            # Filter by material type
            material_type = samp.get("sampledMaterialType", {}).get("label")
            if material_type != MATERIAL_TYPE_TO_KEEP:
                continue  # Skip rows that don’t match filter

            # @id short form
            rid = rec.get("@id", "").split("/")[-1]

            # Parse datetime
            dt_str = samp.get("sampleDateTime")
            if not dt_str:
                continue
            dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))

            row = [
                rid,
                sp.get("label"),
                dt,
                detd.get("label"),
                detd.get("notation"),
                float(rec.get("result")) if rec.get("result") else None,
                unit.get("label"),
                material_type,
                int(sp.get("easting")) if sp.get("easting") else None,
                int(sp.get("northing")) if sp.get("northing") else None,
                datetime.now()
            ]
            rows.append(row)
        except Exception as e:
            print(f"[!] Skipped record: {e}")
    return rows

# --------------------
# INSERT ROWS
# --------------------
def insert_rows(rows):
    if not rows:
        return
    insert_sql = f"""
    INSERT INTO {TABLE_NAME} (
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
        "ingested_at"
    ) VALUES %s
    ON CONFLICT ("@id") DO NOTHING
    """
    for i in range(0, len(rows), CHUNK_SIZE):
        chunk = rows[i:i+CHUNK_SIZE]
        execute_values(cur, insert_sql, chunk)
        conn.commit()
        print(f"[✓] Inserted {i+len(chunk)} rows so far")

# --------------------
# MAIN LOOP
# --------------------
offset = 0
total_inserted = 0

while True:
    batch = fetch_api_batch(start_date, offset=offset)
    if not batch:
        break
    rows = prepare_rows(batch)
    insert_rows(rows)
    total_inserted += len(rows)
    offset += len(batch)
    time.sleep(PAUSE_BETWEEN_BATCHES)

print(f"[✓] Update complete, total inserted: {total_inserted}")

cur.close()
conn.close()
