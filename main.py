# main.py  ––  single-file Flask API (Colab-ready)
import os
import joblib
from flask import Flask, request, jsonify
from dotenv import load_dotenv
import mysql.connector
import pandas as pd

load_dotenv()

app = Flask(__name__)

# ---------- config ----------
MODEL_PATH = "rf_model.pkl"          # pickle produced by your Colab notebook
EXPECTED_COLS = [
    "age", "PainGrade", "BlooddpressurSystol", "BlooddpressurDiastol",
    "PulseRate", "RespiratoryRate", "O2Saturation", "gender_Male"
]

# ---------- load model ----------
try:
    model = joblib.load(MODEL_PATH)          # any sklearn-style estimator
except FileNotFoundError:
    raise RuntimeError(f"Model file {MODEL_PATH} not found – place it in cwd")

# ---------- DB helpers ----------
def get_conn():
    return mysql.connector.connect(
        host=os.getenv('DB_HOST'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        database=os.getenv('DB_NAME'),
        port=int(os.getenv('DB_PORT', 3306)),
    )

def ensure_table():
    """Create table once at start-up if it does not exist."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS patient_records (
                id              INT AUTO_INCREMENT PRIMARY KEY,
                age             FLOAT,
                PainGrade       FLOAT,
                BlooddpressurSystol  FLOAT,
                BlooddpressurDiastol FLOAT,
                PulseRate       FLOAT,
                RespiratoryRate FLOAT,
                O2Saturation    FLOAT,
                gender_Male     BOOLEAN,
                TriageGrade_urgent BOOLEAN,
                ChiefComplaint  TEXT,
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

# ---------- routes ----------
@app.post("/predict")
def predict():
    """
    Expects JSON list with 8 numeric/bool features in EXPECTED_COLS order.
    Returns {"triage_urgent": bool, "id": int} after DB insert.
    """
    try:
        payload = request.get_json(force=True)
        if not isinstance(payload, list) or len(payload) != 8:
            return jsonify({"error": "Send 8-element list: "+", ".join(EXPECTED_COLS)}), 400

        X = pd.DataFrame([payload], columns=EXPECTED_COLS)
        triage_urgent = bool(model.predict(X)[0])          # model outputs 0/1 → False/True

        sql = """INSERT INTO patient_records
                 (age,PainGrade,BlooddpressurSystol,BlooddpressurDiastol,
                  PulseRate,RespiratoryRate,O2Saturation,gender_Male,TriageGrade_urgent)
                 VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)"""
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(sql, payload + [triage_urgent])
            conn.commit()
            return jsonify({"id": cur.lastrowid, "triage_urgent": triage_urgent}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.get("/summary")
def summary():
    try:
        with get_conn() as conn, conn.cursor(dictionary=True) as cur:
            cur.execute("SELECT COUNT(*) AS total FROM patient_records")
            total = cur.fetchone()['total']
            cur.execute("SELECT COUNT(*) AS urgent FROM patient_records WHERE TriageGrade_urgent=1")
            urgent = cur.fetchone()['urgent']
            cur.execute("SELECT * FROM patient_records ORDER BY id DESC LIMIT 100")
            records = cur.fetchall()
            return jsonify({"total_records": total,
                            "urgent_count": urgent,
                            "recent": records})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ---------- start ----------
if __name__ == "__main__":
    ensure_table()
    app.run(host="0.0.0.0", port=8080, debug=False)
