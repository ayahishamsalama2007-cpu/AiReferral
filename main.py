# main.py  (single-file, copy–paste–run)
import os
import joblib
from flask import Flask, request, jsonify
from dotenv import load_dotenv
import mysql.connector
import pandas as pd

from db import ensure_table

load_dotenv()

app = Flask(__name__)

# ---------- config ---------- 
MODEL_PATH = "rf_model.pkl"         
EXPECTED_COLS = [
    "gender", "age", "ChiefComplaint", "PainGrade",
    "BlooddpressurDiastol", "BlooddpressurSystol",
    "PulseRate", "Respiration", "O2Saturation"
]

# ---------- load model ----------
try:
    pipe = joblib.load("rf_model.pkl")
    
except FileNotFoundError:
    raise RuntimeError(f"Model file {MODEL_PATH} not found – place it in the project root")

# ---------- DB helpers ----------
def get_conn():
    return mysql.connector.connect(
        host=os.getenv('DB_HOST'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        database=os.getenv('DB_NAME'),
        port=int(os.getenv('DB_PORT', 3306))
    )

from sklearn.preprocessing import LabelEncoder

# Initialize label encoders for categorical columns
gender_encoder = LabelEncoder().fit(["male", "female"])

@app.post("/insert")
def insert():
    try:
        payload = request.get_json(force=True)
        if not isinstance(payload, list) or len(payload) != 9:
            return jsonify({"error": "Send 9-element list: "+", ".join(EXPECTED_COLS)}), 400
        
        # Preprocess categorical variables
        payload[0] = gender_encoder.transform([payload[0]])[0]  # Encode gender

        X = pd.DataFrame([payload], columns=EXPECTED_COLS)
        
        # Ensure all values are in the correct format
        X = X.astype({
            'age': 'float',
            'PainGrade': 'float',
            'BlooddpressurDiastol': 'float',
            'BlooddpressurSystol': 'float',
            'PulseRate': 'float',
            'Respiration': 'float',
            'O2Saturation': 'float'
        })

        triage_flag = int(pipe.predict(X)[0])

        sql = """INSERT INTO patient_records
                 (gender, age, ChiefComplaint, PainGrade, BlooddpressurDiastol, 
                 BlooddpressurSystol, PulseRate, Respiration, O2Saturation, TriageLevel)
                 VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"""
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(sql, payload + [triage_flag])
            conn.commit()
            return jsonify({"id": cur.lastrowid, "triage_level": triage_flag}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.get("/summary")
def summary():
    try:
        with get_conn() as conn, conn.cursor(dictionary=True) as cur:
            # Fetch all records
            cur.execute("SELECT * FROM patient_records")
            all_records = cur.fetchall()

            # Count records where TriageLevel is 0
            cur.execute("SELECT COUNT(*) AS count FROM patient_records WHERE TriageLevel = 0")
            count_triage_0 = cur.fetchone()['count']

            # Count records where TriageLevel is 1
            cur.execute("SELECT COUNT(*) AS count FROM patient_records WHERE TriageLevel = 1")
            count_triage_1 = cur.fetchone()['count']

            # Total records
            total_records = len(all_records)

            return jsonify({
                'total_records': total_records,
                'triage_level_0_count': count_triage_0,
                'triage_level_1_count': count_triage_1,
                'records': all_records
            })
    except Exception as e:
        return jsonify({"error": str(e)}), 500    
# ---------- start ----------
if __name__ == "__main__":
        ensure_table()
        app.run(host="0.0.0.0", port=8080, debug=False)









