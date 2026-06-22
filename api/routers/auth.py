from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from typing import Optional
import hashlib
import jwt
from datetime import datetime, timedelta
from app.core.config import settings

router = APIRouter(prefix="/api/auth", tags=["Auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# =======================
# Models
# =======================

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    user_id: str
    username: str
    email: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

# =======================
# Helpers
# =======================

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, hashed: str) -> bool:
    return hash_password(password) == hashed

def create_token(user_id: str, username: str) -> str:
    expire = datetime.utcnow() + timedelta(hours=settings.JWT_EXPIRE_HOURS)
    payload = {
        "sub": user_id,
        "username": username,
        "exp": expire
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

# Simple in-memory user store (replace with database in production)
USERS_DB: dict = {}

# =======================
# Routes
# =======================

@router.post("/register", response_model=TokenResponse)
def register(user: UserCreate):
    user_id = hashlib.md5(user.username.encode()).hexdigest()[:12]
    
    if user_id in USERS_DB:
        raise HTTPException(status_code=400, detail="Username already exists")
    
    hashed_pw = hash_password(user.password)
    
    USERS_DB[user_id] = {
        "user_id": user_id,
        "username": user.username,
        "email": user.email,
        "password": hashed_pw
    }
    
    token = create_token(user_id, user.username)
    
    return TokenResponse(
        access_token=token,
        user=UserResponse(
            user_id=user_id,
            username=user.username,
            email=user.email
        )
    )

@router.post("/login", response_model=TokenResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user_id = hashlib.md5(form_data.username.encode()).hexdigest()[:12]
    
    if user_id not in USERS_DB:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )
    
    user_data = USERS_DB[user_id]
    if not verify_password(form_data.password, user_data["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )
    
    token = create_token(user_id, user_data["username"])
    
    return TokenResponse(
        access_token=token,
        user=UserResponse(
            user_id=user_id,
            username=user_data["username"],
            email=user_data["email"]
        )
    )

@router.get("/me", response_model=UserResponse)
def get_current_user(token: str = Depends(oauth2_scheme)):
    payload = decode_token(token)
    user_id = payload.get("sub")
    
    if user_id not in USERS_DB:
        raise HTTPException(status_code=404, detail="User not found")
    
    user_data = USERS_DB[user_id]
    return UserResponse(
        user_id=user_id,
        username=user_data["username"],
        email=user_data["email"]
    )
