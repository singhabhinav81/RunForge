
from app.db.database import SessionLocal
from app.api.worker.worker import recover_one_expired_run


def main() -> None:
    db = SessionLocal()

    try:
        recovered = recover_one_expired_run(db)

        if recovered:
            print("Recovered one expired run.")
        else:
            print("No expired runs were available to recover.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
