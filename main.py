# -----------------------------  TRAINING + FLASK  -----------------------------
import os
import joblib
import numpy as np
import pandas as pd
from flask import Flask, request, jsonify
from dotenv import load_dotenv
import mysql.connector

# ---------------------------------------------------------------------------
# 1.  ENVIRONMENT
# ---------------------------------------------------------------------------
load_dotenv()

# ---------------------------------------------------------------------------
# 2.  CONFIG
# ---------------------------------------------------------------------------
MODEL_PATH   = "rf_model.pkl"
EXPECTED_FEATURES = [
    "gender", "age", "ChiefComplaint", "PainGrade",
    "BlooddpressurDiastol", "BlooddpressurSystol",
    "PulseRate", "RespiratoryRate", "O2Saturation"
]

# ---------------------------------------------------------------------------
# 3.  ENSURE A MODEL EXISTS (train once, reuse forever)
# ---------------------------------------------------------------------------
def _build_model() -> "Pipeline":
    """Create + fit a minimal pipeline -> return fitted pipeline."""
    from sklearn.compose import ColumnTransformer
    from sklearn.preprocessing import OneHotEncoder
    from sklearn.pipeline   import Pipeline
    from sklearn.ensemble   import RandomForestClassifier

    # --- fake data ------------------------------------------------------------
    rng = np.random.RandomState(42)
    n   = 1000
    train = pd.DataFrame({
        "gender"                : rng.choice(["M", "F"], n),
        "age"                   : rng.randint(18, 90, n),
        "ChiefComplaint"        : rng.choice(["chest pain", "fever", "trauma"], n),
        "PainGrade"             : rng.randint(0, 11, n),
        "BlooddpressurSystol"   : rng.randint(90, 200, n),
        "BlooddpressurDiastol"  : rng.randint(60, 120, n),
        "PulseRate"             : rng.randint(60, 120, n),
        "RespiratoryRate"       : rng.randint(12, 30, n),
        "O2Saturation"          : rng.randint(85, 100, n),
    })
    y = rng.randint(0, 2, n)               # random 0/1 target

    # --- pipeline ------------------------------------------------------------
    cat_cols = ["gender", "ChiefComplaint"]
    num_cols = [c for c in EXPECTED_FEATURES if c not in cat_cols]

    pre = ColumnTransformer(
        [("cat", OneHotEncoder(handle_unknown="ignore"), cat_cols)],
        remainder="passthrough"
    )
    clf = RandomForestClassifier(
        n_estimators=300, random_state=42, class_weight="balanced"
    )
    pipe = Pipeline(steps=[("prep", pre), ("model", clf)])
    pipe.fit(train, y)
    return pipe


if not os.path.isfile(MODEL_PATH):
    print("Model not found – training a new one …")
    pref = _build_model()
    joblib.dump(pref, MODEL_PATH)
    print("Saved", MODEL_PATH)
else:
    pref = joblib.load(MODEL_PATH)
    if not hasattr(pref, "predict"):
        raise TypeError("rf_model.pkl does not contain an estimator – delete it and restart.")

# ---------------------------------------------------------------------------
# 4.  DATABASE
# ---------------------------------------------------------------------------
DB_CFG = dict(
    host    =os.getenv('DB_HOST'),
    user    =os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD'),
    database=os.getenv('DB_NAME'),
    port    =int(os.getenv('DB_PORT', 3306))
)

def get_conn():
    return mysql.connector.connect(**DB_CFG)

def ensure_table():
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

# ---------------------------------------------------------------------------
# 5.  FLASK APP
# ---------------------------------------------------------------------------
app = Flask(__name__)

@app.post("/insert")
def insert():
    try:
        data = request.get_json(force=True)
        missing = [f for f in EXPECTED_FEATURES if f not in data]
        if missing:
            return jsonify(error=f"Missing fields: {missing}"), 400

        X = pd.DataFrame([data])[EXPECTED_FEATURES]
        pred_int = int(pref.predict(X)[0])
        proba    = pref.predict_proba(X)[0].tolist()

        cols = EXPECTED_FEATURES + ["TriageLevel"]
        vals = [data[f] for f in EXPECTED_FEATURES] + [pred_int]
        placeholders = ",".join(["%s"] * len(cols))
        sql = f"INSERT INTO patient_records ({','.join(cols)}) VALUES ({placeholders})"

        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(sql, vals)
            conn.commit()

        return jsonify(
            prediction=pred_int,
            probability={"not_urgent": round(proba[0], 3),
                         "urgent"    : round(proba[1], 3)}
        )
    except Exception as e:
        return jsonify(error=str(e)), 400


@app.get("/summary")
def summary():
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

# ---------------------------------------------------------------------------
# 6.  START
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    ensure_table()
    app.run(host="0.0.0.0", port=8080, debug=False)
