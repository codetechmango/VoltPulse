import os
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load environment variables from .env file
load_dotenv()

from app.database import Base, SessionLocal, engine
import app.models
from app.models import User
from app.routes import admin, auth, meter, user
from app.routes.dashboard import router as dashboard_router
from app.security import hash_password
from sqlalchemy import inspect

app = FastAPI(title="Smart Electricity System API")

# Configure CORS origins from environment
origins_str = os.getenv("ALLOWED_ORIGINS", "*")
origins = [origin.strip() for origin in origins_str.split(",") if origin.strip()]

if "*" in origins or origins == ["*"]:
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r".*",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


app.include_router(dashboard_router)
app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(admin.router, prefix="/admin", tags=["Admin"])
app.include_router(meter.router, prefix="/meter", tags=["Meter"])
app.include_router(user.router, prefix="/users", tags=["Users"])


def ensure_auth_columns() -> None:
    inspector = inspect(engine)
    if "users" in inspector.get_table_names():
        column_names = {col["name"] for col in inspector.get_columns("users")}

        if "password_hash" not in column_names:
            with engine.begin() as connection:
                connection.exec_driver_sql("ALTER TABLE users ADD COLUMN password_hash VARCHAR NOT NULL DEFAULT ''")

        if "role" not in column_names:
            with engine.begin() as connection:
                connection.exec_driver_sql("ALTER TABLE users ADD COLUMN role VARCHAR NOT NULL DEFAULT 'user'")


def ensure_alert_columns() -> None:
    inspector = inspect(engine)
    if "alerts" in inspector.get_table_names():
        column_names = {col["name"] for col in inspector.get_columns("alerts")}

        with engine.begin() as connection:
            if "explanation" not in column_names:
                connection.exec_driver_sql("ALTER TABLE alerts ADD COLUMN explanation VARCHAR")

            if "percentage_increase" not in column_names:
                connection.exec_driver_sql("ALTER TABLE alerts ADD COLUMN percentage_increase FLOAT")

            if "status" not in column_names:
                connection.exec_driver_sql("ALTER TABLE alerts ADD COLUMN status VARCHAR NOT NULL DEFAULT 'open'")

            if "resolved_at" not in column_names:
                # PostgreSQL uses TIMESTAMP for Datetime columns
                db_url = str(engine.url)
                col_type = "TIMESTAMP" if "sqlite" not in db_url else "DATETIME"
                connection.exec_driver_sql(f"ALTER TABLE alerts ADD COLUMN resolved_at {col_type}")

            connection.exec_driver_sql("UPDATE alerts SET status = 'open' WHERE status IS NULL OR status = ''")


def ensure_meter_reading_columns() -> None:
    inspector = inspect(engine)
    if "meter_readings" in inspector.get_table_names():
        column_names = {col["name"] for col in inspector.get_columns("meter_readings")}

        with engine.begin() as connection:
            if "voltage" not in column_names:
                connection.exec_driver_sql("ALTER TABLE meter_readings ADD COLUMN voltage FLOAT")
            if "current_mA" not in column_names:
                connection.exec_driver_sql("ALTER TABLE meter_readings ADD COLUMN current_mA FLOAT")
            if "power_w" not in column_names:
                connection.exec_driver_sql("ALTER TABLE meter_readings ADD COLUMN power_w FLOAT")


def ensure_default_auth_users() -> None:
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.email == "admin@smartgrid.com").first()
        if not admin:
            db.add(
                User(
                    name="System Admin",
                    email="admin@smartgrid.com",
                    area="HQ",
                    password_hash=hash_password("Admin@123"),
                    role="admin",
                )
            )

        demo_user = db.query(User).filter(User.email == "priya@consumer.com").first()
        if not demo_user:
            db.add(
                User(
                    name="Priya Kumar",
                    email="priya@consumer.com",
                    area="Chennai North",
                    password_hash=hash_password("User@123"),
                    role="user",
                )
            )

        db.query(User).filter(User.role.is_(None)).update({"role": "user"}, synchronize_session=False)
        db.query(User).filter(User.password_hash.is_(None)).update({"password_hash": ""}, synchronize_session=False)
        db.commit()
    finally:
        db.close()


@app.on_event("startup")
def on_startup() -> None:
    ensure_auth_columns()
    Base.metadata.create_all(bind=engine)
    ensure_alert_columns()
    ensure_meter_reading_columns()
    ensure_default_auth_users()
