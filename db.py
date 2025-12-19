import os
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

def get_connection():
    return mysql.connector.connect(
        host=os.getenv('DB_HOST'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        database=os.getenv('DB_NAME'),
        port=int(os.getenv('DB_PORT', 3306)),
    )

def ensure_table():
    """Create table once at start-up if it does not exist."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS patient_records (
                id INT AUTO_INCREMENT PRIMARY KEY,
                gender VARCHAR(10),
                age INT,
                paingrade INT,
                systolic INT,
                diastolic INT,
                pulserate INT,
                respiratoryrate INT,
                o2saturation INT,
                chiefcomplaint TEXT,
                TriageLevel TINYINT(1) NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
