from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
import hashlib
import hmac
import secrets
import uuid
import jwt
from datetime import datetime, timedelta
from app.core.config import settings
from app.core.database import db

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
# Password Helpers (PBKDF2-HMAC-SHA256 + per-user salt)
# =======================

_PBKDF2_ITERATIONS = 200_000  # OWASP 2023 推荐

def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    """返回 (password_hash, salt)。salt 为 None 时自动生成。"""
    if salt is None:
        salt = secrets.token_hex(16)
    derived = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), _PBKDF2_ITERATIONS
    )
    return derived.hex(), salt

def verify_password(password: str, password_hash: str, salt: str) -> bool:
    """恒定时间比较，避免计时攻击"""
    derived, _ = hash_password(password, salt)
    return hmac.compare_digest(derived, password_hash)

# =======================
# Token Helpers
# =======================

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

# =======================
# Routes
# =======================

@router.post("/register", response_model=TokenResponse)
def register(user: UserCreate):
    # 密码强度校验
    if len(user.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    user_id = str(uuid.uuid4())
    password_hash, salt = hash_password(user.password)

    created = db.create_user(
        user_id=user_id,
        username=user.username,
        email=user.email,
        password_hash=password_hash,
        salt=salt,
    )
    if not created:
        raise HTTPException(status_code=400, detail="Username already exists")

    token = create_token(user_id, user.username)
    return TokenResponse(
        access_token=token,
        user=UserResponse(
            user_id=user_id,
            username=user.username,
            email=user.email,
        )
    )

@router.post("/login", response_model=TokenResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user_data = db.get_user_by_username(form_data.username)
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )

    if not verify_password(form_data.password, user_data["password_hash"], user_data["salt"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )

    token = create_token(user_data["user_id"], user_data["username"])
    return TokenResponse(
        access_token=token,
        user=UserResponse(
            user_id=user_data["user_id"],
            username=user_data["username"],
            email=user_data["email"],
        )
    )

@router.get("/me", response_model=UserResponse)
def get_current_user(token: str = Depends(oauth2_scheme)):
    payload = decode_token(token)
    user_id = payload.get("sub")

    user_data = db.get_user_by_id(user_id)
    if not user_data:
        raise HTTPException(status_code=404, detail="User not found")

    return UserResponse(
        user_id=user_data["user_id"],
        username=user_data["username"],
        email=user_data["email"],
    )
