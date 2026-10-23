from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict


class MeterReading(BaseModel):
    user_id: int
    previous_reading: float
    current_reading: float
    reading_date: date | None = None
    voltage: float | None = None
    current_mA: float | None = None
    power_w: float | None = None


class ConsumptionResponse(BaseModel):
    user_id: int
    units_consumed: float
    estimated_bill: float


class UserCreate(BaseModel):
    name: str
    email: str
    area: str
    password: str | None = None
    role: Literal["user", "admin"] | None = "user"


class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    area: str
    role: Literal["user", "admin"] = "user"

    model_config = ConfigDict(from_attributes=True)


class AuthRegisterRequest(BaseModel):
    name: str
    email: str
    area: str
    password: str
    role: Literal["user", "admin"] | None = "user"


class AuthLoginRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
