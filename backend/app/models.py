from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    area: Mapped[str] = mapped_column(String, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False, default="")
    role: Mapped[str] = mapped_column(String, nullable=False, default="user")

    meter_readings: Mapped[list["MeterReading"]] = relationship(
        "MeterReading", back_populates="user"
    )
    bills: Mapped[list["Bill"]] = relationship(
        "Bill", back_populates="user"
    )
    alerts: Mapped[list["Alert"]] = relationship(
        "Alert", back_populates="user"
    )


class MeterReading(Base):
    __tablename__ = "meter_readings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    units: Mapped[float] = mapped_column(Float, nullable=False)
    load_value: Mapped[float] = mapped_column(Float, nullable=False)
    voltage: Mapped[float | None] = mapped_column(Float, nullable=True)
    current_mA: Mapped[float | None] = mapped_column(Float, nullable=True)
    power_w: Mapped[float | None] = mapped_column(Float, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    is_anomaly: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    user: Mapped["User"] = relationship("User", back_populates="meter_readings")


class Bill(Base):
    __tablename__ = "bills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    month: Mapped[str] = mapped_column(String, nullable=False)
    total_units: Mapped[float] = mapped_column(
        Float, default=0.0, nullable=False
    )
    predicted_amount: Mapped[float] = mapped_column(
        Float, default=0.0, nullable=False
    )

    user: Mapped["User"] = relationship("User", back_populates="bills")


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    message: Mapped[str] = mapped_column(String, nullable=False)
    explanation: Mapped[str | None] = mapped_column(String, nullable=True)
    percentage_increase: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="open")
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    type: Mapped[str] = mapped_column(String, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    user: Mapped["User"] = relationship("User", back_populates="alerts")