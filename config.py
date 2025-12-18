
from __future__ import annotations
import os
from dotenv import load_dotenv

load_dotenv()
DATABASE = dict(
    host=os.getenv('DB_HOST'),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD'),
    database=os.getenv('DB_NAME'),
    port=int(os.getenv('DB_PORT')),
    pool_name='rf_pool',
    pool_size=10,
)