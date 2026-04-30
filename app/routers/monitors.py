from typing import List, Optional

from fastapi import Depends, HTTPException, APIRouter, Query, status
from firebase_admin import db
from sqlalchemy.orm import Session

from app.auth import TokenData, get_current_user
from app.database import get_db
from app.models.app_auth import AppUser

monitor_router = APIRouter()
