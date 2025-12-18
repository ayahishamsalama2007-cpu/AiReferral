
from db import get_connection
import pandas as pd
import numpy as np
import joblib
pipe = joblib.load("rf_model.pkl")
def insert_patient(payload: list):
    """
    payload: 9-element list
    returns: dict {"id": <int>, "triage_level": 0|1}
    """
    import pandas as pd
    cols = ["gender", "age", "ChiefComplaint", "PainGrade",
            "BlooddpressurSystol", "BlooddpressurDiastol",
            "PulseRate", "RespiratoryRate", "O2Saturation"]
    X = pd.DataFrame([payload], columns=cols)
    triage_flag = int(pipe.predict(X)[0])

    full_payload = payload + [triage_flag]
    sql = ("INSERT INTO patient_records "
           "(gender, age, ChiefComplaint, PainGrade, BlooddpressurSystol, "
           "BlooddpressurDiastol, PulseRate, RespiratoryRate, O2Saturation, TriageLevel) "
           "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)")
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, full_payload)
        conn.commit()
        return {"id": cur.lastrowid, "triage_level": triage_flag}
def list_patients(limit: int = 0):
    """
    limit: 0  -> all rows
    returns: list[dict]  (already json-serialisable)
    """
    sql = "SELECT * FROM patient_records ORDER BY id DESC"
    if limit:
        sql += f" LIMIT {limit}"
    with get_connection() as conn:
        df = pd.read_sql(sql, conn)
    return df.to_dict(orient="records")