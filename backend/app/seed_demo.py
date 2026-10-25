from app.database import SessionLocal
from app.collectors.sample_data import load_sample_data

if __name__ == "__main__":
    db = SessionLocal()
    try:
        load_sample_data(db)
        print("demo data loaded (if sample_data csv files exist)")
    finally:
        db.close()
