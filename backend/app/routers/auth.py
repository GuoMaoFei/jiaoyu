import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.database import get_db
from app.models.user import Student, Parent
from app.utils.auth import create_access_token, get_current_user_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["Auth"])

class LoginRequest(BaseModel):
    username: str # mobile, nickname, or whatever is used
    password: Optional[str] = None
    role: str = "student" # student or parent

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    nickname: str
    role: str

class BindParentRequest(BaseModel):
    student_id: str
    parent_phone: str

@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Login endpoint for both students and parents.
    If student bypasses password (MVP logic), we just issue JWT.
    """
    if request.role == "student":
        result = await db.execute(select(Student).where(Student.nickname == request.username))
        user = result.scalars().first()
        
        # Auto-register if not found (demo mode)
        if not user:
            user = Student(
                nickname=request.username,
                grade="初二", # Default
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
            logger.info(f"Auto-registered new student during login: {user.nickname} ({user.id})")
            
        token = create_access_token({"sub": user.id, "name": user.nickname, "role": "student"})
        return LoginResponse(
            access_token=token,
            user_id=user.id,
            nickname=user.nickname,
            role="student"
        )
        
    elif request.role == "parent":
        # MVP: simple phone check. In prod, check passlib.hash.bcrypt
        result = await db.execute(select(Parent).where(Parent.phone_number == request.username))
        user = result.scalars().first()
        
        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")
            
        # TODO: verify password logic here
            
        token = create_access_token({"sub": user.id, "name": user.nickname, "role": "parent"})
        return LoginResponse(
            access_token=token,
            user_id=user.id,
            nickname=user.nickname or "家长",
            role="parent"
        )
    else:
        raise HTTPException(status_code=400, detail="Invalid role specified")

@router.post("/refresh")
async def refresh_token(payload: dict = Depends(get_current_user_token)):
    """Refresh JWT token."""
    new_token = create_access_token({
        "sub": payload.get("sub"),
        "name": payload.get("name"),
        "role": payload.get("role")
    })
    return {"access_token": new_token, "token_type": "bearer"}

@router.post("/bind-parent")
async def bind_parent(request: BindParentRequest, db: AsyncSession = Depends(get_db)):
    """Bind a student to a parent using phone number."""
    # Find student
    student_res = await db.execute(select(Student).where(Student.id == request.student_id))
    student = student_res.scalars().first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
        
    # Find parent
    parent_res = await db.execute(select(Parent).where(Parent.phone_number == request.parent_phone))
    parent = parent_res.scalars().first()
    
    # If parent doesn't exist, create it for MVP (in prod, they should register)
    if not parent:
        parent = Parent(phone_number=request.parent_phone, nickname=f"{student.nickname}的家长")
        db.add(parent)
        await db.flush()
        
    student.parent_id = parent.id
    await db.commit()
    return {"status": "ok", "message": "Successfully bound parent"}
