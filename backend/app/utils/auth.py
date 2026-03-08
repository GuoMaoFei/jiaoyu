from datetime import datetime, timedelta, timezone
from typing import Optional, Any
from jose import jwt, JWTError
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import get_settings
from app.database import get_db
from app.models.user import Student, Parent

settings = get_settings()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str):
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        return None

async def get_current_user_token(token: str = Depends(oauth2_scheme)):
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload

async def get_current_student(
    payload: dict = Depends(get_current_user_token),
    db: AsyncSession = Depends(get_db)
):
    user_id = payload.get("sub")
    role = payload.get("role")
    if role != "student":
        raise HTTPException(status_code=403, detail="Not authorized as student")
        
    result = await db.execute(select(Student).where(Student.id == user_id))
    student = result.scalars().first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return student

async def get_current_parent(
    payload: dict = Depends(get_current_user_token),
    db: AsyncSession = Depends(get_db)
):
    user_id = payload.get("sub")
    role = payload.get("role")
    if role != "parent":
        raise HTTPException(status_code=403, detail="Not authorized as parent")
        
    result = await db.execute(select(Parent).where(Parent.id == user_id))
    parent = result.scalars().first()
    if not parent:
        raise HTTPException(status_code=404, detail="Parent not found")
    return parent
