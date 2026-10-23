from calendar import monthrange
from datetime import datetime
import random

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Alert, Bill, MeterReading, User
from app.security import require_admin

router = APIRouter()


def calculate_bill(units: float) -> float:
	if units <= 0:
		return 0.0
	if units <= 100:
		return round(units * 1.5, 2)
	elif units <= 300:
		return round((100 * 1.5) + ((units - 100) * 3.0), 2)
	else:
		return round((100 * 1.5) + (200 * 3.0) + ((units - 300) * 5.0), 2)


@router.delete("/clear-bills")
def clear_all_bills(
	db: Session = Depends(get_db),
	_: User = Depends(require_admin),
) -> dict[str, str]:
	db.query(Bill).delete(synchronize_session=False)
	db.commit()
	return {"message": "All bill records cleared successfully"}


@router.delete("/reset-system")
def reset_system(
	db: Session = Depends(get_db),
	_: User = Depends(require_admin),
) -> dict[str, str]:
	db.query(Bill).delete(synchronize_session=False)
	db.query(MeterReading).delete(synchronize_session=False)
	db.query(Alert).delete(synchronize_session=False)
	db.commit()
	return {"message": "System reset successfully"}


@router.put("/alerts/{alert_id}/resolve")
def resolve_alert(
	alert_id: int,
	db: Session = Depends(get_db),
	_: User = Depends(require_admin),
) -> dict[str, str]:
	alert = db.query(Alert).filter(Alert.id == alert_id).first()
	if not alert:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")

	alert.status = "resolved"
	alert.resolved_at = datetime.utcnow()
	db.commit()

	return {"message": "Alert marked as resolved"}


@router.post("/generate-demo-data")
def generate_demo_data(
	db: Session = Depends(get_db),
	_: User = Depends(require_admin),
) -> dict[str, int | str]:
	# Synthetic / mock data generator is disabled for Live Hardware integration
	return {
		"message": "Synthetic demo data generator is disabled. VoltPulse is currently running in Live Hardware Mode with ESP32 & INA219 sensor telemetry.",
		"status": "disabled",
		"users_processed": 0,
		"readings_created": 0,
		"anomalies_created": 0,
		"bills_created": 0,
	}
