from typing import List, Optional

from fastapi import Depends, HTTPException, APIRouter, Query, status
from firebase_admin import db
from sqlalchemy.orm import Session

from app.auth import TokenData, get_current_user
from app.database import get_db
from app.models.app_auth import AppUser

monitor_router = APIRouter()


# we need to create and track shifts for monitors. This will allow us to associate inspections and passenger counts with specific shifts, and also track which monitor is on shift at any given time.
@monitor_router.post("/shift_management/")
def create_shift_management(
    db: Session = Depends(get_db), current_user: TokenData = Depends(get_current_user)
):

    pass
