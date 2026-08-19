from fastapi import APIRouter, Depends, HTTPException, status
from pwdlib import PasswordHash
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordRequestForm
from app.database import SessionLocal
from app.models import User
from app.schemas import UserCreate, UserResponse, UserLogin,Token
from app.security import verify_password, create_access_token


router = APIRouter(
    prefix="/auth",
    tags=["authentication"]
)


password_hash = PasswordHash.recommended()


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED
)
def register(
    user_data: UserCreate,
    db: Session = Depends(get_db)
):
    existing_user = (
        db.query(User)
        .filter(User.email == user_data.email)
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )
    hashed_password = password_hash.hash(
        user_data.password
        # For passwords, don't use a fast general-purpose hash like SHA-256 directly.
        # Attackers can perform enormous numbers of guesses against fast hashes.
        # Password hashing algorithms such as Argon2 are deliberately designed to make password guessing more expensive.
        # That's exactly what we want.
    )

    user = User(
        email=user_data.email,
        password_hash=hashed_password
        #email            → dharmesh@example.com
        # password_hash    → $argon2id$...
        # role             → user
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user        


#Understand the complete login flow
@router.post("/login",              #suppose postgreSQL contains:
                                    # id:1
                                    # email:test@example.compilepassword_hash:$argon2id$...
                                    # role:user

    response_model=Token
)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    user = (
        db.query(User)
        .filter(User.email == form_data.username)
        .first()
    )

    if user is None:
        raise HTTPException(
            form_data.password,
             user.password_hash
        )

    if not verify_password(
        form_data.password,
        user.password_hash
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials"
        )

    access_token = create_access_token(
        user_id=user.id,
        role=user.role
    )

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }