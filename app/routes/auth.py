from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from pwdlib import PasswordHash
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordRequestForm
from app.database import get_db
from app.models import User, UserPreference
from app.schemas import UserCreate, UserResponse, UserLogin, Token
from app.security import verify_password, create_access_token, get_current_user


router = APIRouter(
    prefix="/auth",
    tags=["authentication"]
)

password_hash = PasswordHash.recommended()

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
    if not verify_password(form_data.password, user.password_hash):#When the email doesn't match a row, user is None, so user.password_hash crashes.
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
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

class UserPreferencesUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: str | None = None
    district: str | None = None
    city: str | None = None
    locality: str | None = None
    property_types: list[str] = Field(default_factory=list)
    min_reserve_price: float | None = None
    max_reserve_price: float | None = None
    preferred_banks: list[str] = Field(default_factory=list)
    onboarding_completed: bool = True


@router.get("/me/preferences")
def get_my_preferences(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    preference = (
        db.query(UserPreference)
        .filter(UserPreference.user_id == current_user.id)
        .first()
    )
    if preference is None:
        return {
            "state": None,
            "district": None,
            "city": None,
            "locality": None,
            "property_types": [],
            "min_reserve_price": None,
            "max_reserve_price": None,
            "preferred_banks": [],
            "onboarding_completed": False,
        }
    return {
        "state": preference.state,
        "district": preference.district,
        "city": preference.city,
        "locality": preference.locality,
        "property_types": preference.property_types or [],
        "min_reserve_price": (
            float(preference.min_reserve_price)
            if preference.min_reserve_price is not None else None
        ),
        "max_reserve_price": (
            float(preference.max_reserve_price)
            if preference.max_reserve_price is not None else None
        ),
        "preferred_banks": preference.preferred_banks or [],
        "onboarding_completed": preference.onboarding_completed,
    }


@router.put("/me/preferences")
def update_my_preferences(
    payload: UserPreferencesUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    preference = (
        db.query(UserPreference)
        .filter(UserPreference.user_id == current_user.id)
        .first()
    )
    if preference is None:
        preference = UserPreference(user_id=current_user.id)
        db.add(preference)

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(preference, field, value)

    db.commit()
    db.refresh(preference)
    return get_my_preferences(db=db, current_user=current_user)
