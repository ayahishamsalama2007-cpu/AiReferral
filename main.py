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
    ct   = pipe.named_steps['columntransformer']
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


# ---------- routes ----------
@app.post("/insert")
def insert():
    try:
        payload = request.get_json(force=True)
        if not isinstance(payload, list) or len(payload) != 9:
            return jsonify({"error": "Send 9-element list: "+", ".join(EXPECTED_COLS)}), 400

        X = pd.DataFrame([payload], columns=EXPECTED_COLS)
        triage_flag = int(pipe.predict(X)[0])

        sql = """INSERT INTO patient_records
                 (gender,age,ChiefComplaint,PainGrade,BlooddpressurDiastol,BlooddpressurSystol,PulseRate,Respiration,O2Saturation,TriageLevel)
                 VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"""
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(sql, payload + [triage_flag])
            conn.commit()
            return jsonify({"id": cur.lastrowid, "triage_level": triage_flag}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.get("/records")
def records():
    try:
            ensure_table()

        limit = int(request.args.get("limit", 0))
        sql = "SELECT * FROM patient_records ORDER BY id DESC" + (f" LIMIT {limit}" if limit else "")
        with get_conn() as conn:
            rows = pd.read_sql(sql, conn).to_dict(orient="records")
        return jsonify(rows)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
        # render
    
@app.route("/")
def home():
    return "Hello from Render!"
    
# ---------- start ----------
if __name__ == "__main__":
        ensure_table()


    app.run(host="0.0.0.0", port=8080, debug=False)









