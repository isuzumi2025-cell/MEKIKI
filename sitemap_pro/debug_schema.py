import sys
import os
sys.path.append(os.getcwd())
from app.db import database, models
from app.schemas import schemas

db = database.SessionLocal()
job = db.query(models.Job).first()
if job:
    print(f"Job found: {job.id}")
    try:
        s = schemas.Job.model_validate(job)
        print("Validation Successful")
        print(s.model_dump())
    except Exception as e:
        print(f"Validation Failed: {e}")
else:
    print("No jobs found")
db.close()
