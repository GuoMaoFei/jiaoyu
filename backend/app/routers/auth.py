import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field

from app.database import get_db
from app.models.user import Student, Parent
from app.utils.auth import (
    create_access_token,
    get_current_user_token,
    get_current_student,
    get_current_parent,
    verify_password,
    hash_password,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["Auth"])


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    password: Optional[str] = Field(None, min_length=6, max_length=100)
    role: str = Field(default="student", pattern="^(student|parent)$")


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    nickname: str
    role: str


class BindParentRequest(BaseModel):
    student_id: str = Field(..., min_length=1)
    parent_phone: str = Field(..., min_length=10, max_length=20)


class RegisterParentRequest(BaseModel):
    phone_number: str = Field(..., min_length=10, max_length=20)
    password: str = Field(..., min_length=6, max_length=100)
    nickname: Optional[str] = Field(None, max_length=50)


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    if request.role == "student":
        result = await db.execute(
            select(Student).where(Student.nickname == request.username)
        )
        user = result.scalars().first()

        if not user:
            user = Student(nickname=request.username, grade="初二")
            db.add(user)
            await db.commit()
            await db.refresh(user)
            logger.info(f"Auto-registered new student: {user.nickname}")

        token = create_access_token(
            {"sub": user.id, "name": user.nickname, "role": "student"}
        )
        return LoginResponse(
            access_token=token,
            user_id=user.id,
            nickname=user.nickname,
            role="student",
        )

    elif request.role == "parent":
        if not request.password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password is required for parent login",
            )

        result = await db.execute(
            select(Parent).where(Parent.phone_number == request.username)
        )
        user = result.scalars().first()

        if not user or not user.password_hash:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )

        if not verify_password(request.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )

        token = create_access_token(
            {"sub": user.id, "name": user.nickname or "家长", "role": "parent"}
        )
        return LoginResponse(
            access_token=token,
            user_id=user.id,
            nickname=user.nickname or "家长",
            role="parent",
        )

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role specified"
    )


@router.post("/register/parent", response_model=LoginResponse)
async def register_parent(
    request: RegisterParentRequest, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Parent).where(Parent.phone_number == request.phone_number)
    )
    existing = result.scalars().first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone number already registered",
        )

    password_hash = hash_password(request.password)
    parent = Parent(
        phone_number=request.phone_number,
        password_hash=password_hash,
        nickname=request.nickname or "家长",
    )
    db.add(parent)
    await db.commit()
    await db.refresh(parent)

    token = create_access_token(
        {"sub": parent.id, "name": parent.nickname, "role": "parent"}
    )
    return LoginResponse(
        access_token=token,
        user_id=parent.id,
        nickname=parent.nickname,
        role="parent",
    )


@router.post("/refresh")
async def refresh_token(payload: dict = Depends(get_current_user_token)):
    new_token = create_access_token(
        {
            "sub": payload.get("sub"),
            "name": payload.get("name"),
            "role": payload.get("role"),
        }
    )
    return {"access_token": new_token, "token_type": "bearer"}


@router.post("/bind-parent")
async def bind_parent(
    request: BindParentRequest,
    db: AsyncSession = Depends(get_db),
    current_student: Student = Depends(get_current_student),
):
    if current_student.id != request.student_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only bind parent to your own account",
        )

    student_res = await db.execute(
        select(Student).where(Student.id == request.student_id)
    )
    student = student_res.scalars().first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    parent_res = await db.execute(
        select(Parent).where(Parent.phone_number == request.parent_phone)
    )
    parent = parent_res.scalars().first()

    if not parent:
        parent = Parent(
            phone_number=request.parent_phone, nickname=f"{student.nickname}的家长"
        )
        db.add(parent)
        await db.flush()

    student.parent_id = parent.id
    await db.commit()
    return {"status": "ok", "message": "Successfully bound parent"}
