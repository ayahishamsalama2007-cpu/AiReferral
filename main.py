# ---------- main.py ----------
import os
import joblib
from flask import Flask, request, jsonify
from dotenv import load_dotenv
import mysql.connector
import pandas as pd

# Load environment variables
load_dotenv()

app = Flask(__name__)

# ---------- Configuration ----------
MODEL_PATH = "rf_pipeline.pkl"
EXPECTED_FEATURES = [
    "gender", "age", "ChiefComplaint", "PainGrade",
    "BlooddpressurDiastol", "BlooddpressurSystol",
    "PulseRate", "RespiratoryRate", "O2Saturation"
]

# ---------- Load Model ----------
try:
    pref = joblib.load(MODEL_PATH)  # Full pipeline with preprocessing + classifier
except FileNotFoundError:
    raise RuntimeError(f"Model file {MODEL_PATH} not found – place it in the project root")
except Exception as e:
    raise RuntimeError(f"Failed to load model: {e}")

# ---------- Database Configuration ----------
DB_CFG = dict(
    host=os.getenv('DB_HOST'),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD'),
    database=os.getenv('DB_NAME'),
    port=int(os.getenv('DB_PORT', 3306))
)

def get_conn():
    return mysql.connector.connect(**DB_CFG)

def ensure_table():
    """Create the patient_records table if it does not exist."""
    ddl = """
    CREATE TABLE IF NOT EXISTS patient_records (
        id INT AUTO_INCREMENT PRIMARY KEY,
        gender VARCHAR(10),
        age INT,
        ChiefComplaint VARCHAR(255),
        PainGrade INT,
        BlooddpressurDiastol INT,
        BlooddpressurSystol INT,
        PulseRate INT,
        RespiratoryRate INT,
        O2Saturation INT,
        TriageLevel TINYINT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(ddl)
        conn.commit()

# ---------- Routes ----------

@app.post("/insert")
def insert():
    """Insert a new patient record, run prediction, save to DB, return saved row."""
    try:
        data = request.get_json(force=True)

        # --- basic validation ---
        if not all(f in data for f in EXPECTED_FEATURES):
            missing = [f for f in EXPECTED_FEATURES if f not in data]
            return jsonify(error=f"Missing fields: {missing}"), 400

        # --- prediction ---
        X = pd.DataFrame([data])[EXPECTED_FEATURES]
        pred_int = int(pref.predict(X)[0])

        # --- insert ---
        cols = EXPECTED_FEATURES + ["TriageLevel"]
        vals = [data[f] for f in EXPECTED_FEATURES] + [pred_int]
        placeholders = ",".join(["%s"] * len(cols))
        sql_insert = f"""
            INSERT INTO patient_records ({','.join(cols)})
            VALUES ({placeholders})
        """
        with get_conn() as conn, conn.cursor(dictionary=True) as cur:
            cur.execute(sql_insert, vals)
            new_id = cur.lastrowid                       # MySQL auto-increment id
            # read the row we just wrote
            cur.execute(
                "SELECT * FROM patient_records WHERE id = %s",
                (new_id,)
            )
            saved_row = cur.fetchone()                   # dict with all columns
            conn.commit()

        # --- send the database row back ---
        return jsonify(saved_row), 201

    except Exception as e:
        return jsonify(error=str(e)), 400
@app.get("/summary")
def summary():
    """Return all patient records and triage level stats."""
    try:
        with get_conn() as conn, conn.cursor(dictionary=True) as cur:
            cur.execute("SELECT * FROM patient_records ORDER BY created_at DESC")
            records = cur.fetchall()

            cur.execute("SELECT COUNT(*) AS c FROM patient_records WHERE TriageLevel=0")
            count_0 = cur.fetchone()['c']
            cur.execute("SELECT COUNT(*) AS c FROM patient_records WHERE TriageLevel=1")
            count_1 = cur.fetchone()['c']

            return jsonify(
                total_records=len(records),
                triage_level_0_count=count_0,
                triage_level_1_count=count_1,
                records=records
            )
    except Exception as e:
        return jsonify(error=str(e)), 500

# ---------- Start Server ----------
if __name__ == "__main__":
    ensure_table()
    app.run(host="0.0.0.0", port=8080, debug=False)



