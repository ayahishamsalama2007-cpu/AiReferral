# ---------- main.py  (single-file, copy-paste-run) ----------
import os
import joblib
from flask import Flask, request, jsonify
from dotenv import load_dotenv
import mysql.connector
import pandas as pd

load_dotenv()

app = Flask(__name__)

# ---------- config ----------
MODEL_PATH = "rf_model.pkl"
EXPECTED_FEATURES = [
    "gender", "age", "ChiefComplaint", "PainGrade",
    "BlooddpressurDiastol", "BlooddpressurSystol",
    "PulseRate", "Respiration", "O2Saturation"
]

# ---------- load model ----------
try:
    pref = joblib.load(MODEL_PATH)          # <── model object
except FileNotFoundError:
    raise RuntimeError(f"Model file {MODEL_PATH} not found – place it in the project root")

# ---------- DB helpers ----------
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
    """Create the table if it does not yet exist."""
    ddl = """
    CREATE TABLE IF NOT EXISTS patient_records (
        id              INT AUTO_INCREMENT PRIMARY KEY,
        gender          VARCHAR(10),
        age             INT,
        ChiefComplaint  VARCHAR(255),
        PainGrade       INT,
        BlooddpressurDiastol  INT,
        BlooddpressurSystol   INT,
        PulseRate       INT,
        Respiration     INT,
        O2Saturation    INT,
        TriageLevel     TINYINT,
        created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(ddl)
        conn.commit()

# ---------- routes ----------
@app.post("/insert")
def insert():
    """Insert a new patient record, run model, store prediction."""
    try:
        data = request.get_json(force=True)

        # 1. prediction
        X = pd.DataFrame([data])[EXPECTED_FEATURES]
        pred_int = int(pref.predict(X)[0])
        proba = pref.predict_proba(X)[0].tolist()

        # 2. persist to DB
        cols = EXPECTED_FEATURES + ["TriageLevel"]
        vals = [data[f] for f in EXPECTED_FEATURES] + [pred_int]
        sql = f"INSERT INTO patient_records ({','.join(cols)}) VALUES ({','.join(['%s']*len(cols))})"
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(sql, vals)
            conn.commit()

        # 3. respond
        return jsonify(
            prediction=pred_int,
            probability={"not_urgent": round(proba[0], 3),
                         "urgent":     round(proba[1], 3)}
        )
    except Exception as e:
        return jsonify(error=str(e)), 400


@app.get("/summary")
def summary():
    """Return aggregate stats and all rows."""
    try:
        with get_conn() as conn, conn.cursor(dictionary=True) as cur:
            cur.execute("SELECT * FROM patient_records ORDER BY created_at DESC")
            rows = cur.fetchall()

            cur.execute("SELECT COUNT(*) AS c FROM patient_records WHERE TriageLevel=0")
            cnt_0 = cur.fetchone()['c']
            cur.execute("SELECT COUNT(*) AS c FROM patient_records WHERE TriageLevel=1")
            cnt_1 = cur.fetchone()['c']

            return jsonify(total_records=len(rows),
                           triage_level_0_count=cnt_0,
                           triage_level_1_count=cnt_1,
                           records=rows)
    except Exception as e:
        return jsonify(error=str(e)), 500


# ---------- start ----------
if __name__ == "__main__":
    ensure_table()
    app.run(host="0.0.0.0", port=8080, debug=False)
