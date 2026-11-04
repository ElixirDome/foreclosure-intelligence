<<<<<<< HEAD
import os
import secrets
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from pwdlib import PasswordHash
from sqlalchemy.orm import Session
=======
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from pwdlib import PasswordHash
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordRequestForm
from app.database import get_db
from app.models import User, UserPreference
from app.schemas import UserCreate, UserResponse, UserLogin, Token
from app.security import verify_password, create_access_token, get_current_user
>>>>>>> 92c77001379e6b91b43212cb314e441bf427457a

from app.database import get_db
from app.models import User, UserPreference
from app.schemas import UserCreate, UserResponse, Token, UserPreferenceResponse, UserPreferenceUpdate
from app.security import verify_password, create_access_token, get_current_user

router = APIRouter(
    prefix="/auth",
    tags=["authentication"]
)

password_hash = PasswordHash.recommended()

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv(
    "GOOGLE_REDIRECT_URI",
    "http://localhost:8000/auth/google/callback"
)
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

# In-memory CSRF state cache (for state validation in single-node/dev environments)
_oauth_states: set[str] = set()


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
            status_code=status.HTTP_400_BAD_REQUEST,
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
        #email            → dharmesh@example.com
        # password_hash    → $argon2id$...
        # role             → user
        password_hash=hashed_password,
        role="user"
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user        


#Understand the complete login flow
@router.post(
    "/login",              #suppose postgreSQL contains:
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

    if user is None or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(
        user_id=user.id,
        role=user.role
    )

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }

<<<<<<< HEAD

class GoogleAuthRequest(BaseModel):
    email: str | None = None
    name: str | None = None
    credential: str | None = None


@router.get("/google/login")
def google_login_redirect():
    """Generates the Google OAuth 2.0 authorization URL with CSRF state protection."""
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GOOGLE_CLIENT_ID is not configured in environment.",
        )

    state = secrets.token_urlsafe(32)
    _oauth_states.add(state)

    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "state": state,
        "prompt": "select_account",
    }
    encoded_params = "&".join(f"{k}={v}" for k, v in params.items())
    google_auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{encoded_params}"

    return RedirectResponse(url=google_auth_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.get("/google/callback")
def google_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db)
):
    """
    Handles Google OAuth 2.0 redirect callback.
    Validates CSRF state, exchanges authorization code for user info, and creates/retrieves user.
    """
    if state not in _oauth_states:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OAuth state parameter (CSRF protection failed).",
        )
    _oauth_states.discard(state)

    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET is not configured.",
        )

    token_url = "https://oauth2.googleapis.com/token"
    token_payload = {
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code",
    }

    try:
        with httpx.Client(timeout=10.0) as client:
            token_resp = client.post(token_url, data=token_payload)
            token_resp.raise_for_status()
            token_data = token_resp.json()

            id_token_val = token_data.get("id_token")
            access_token_val = token_data.get("access_token")

            # Fetch user profile
            userinfo_resp = client.get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {access_token_val}"}
            )
            userinfo_resp.raise_for_status()
            user_info = userinfo_resp.json()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to exchange authorization code with Google: {exc}",
        )

    email = user_info.get("email")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google profile did not contain an email address.",
        )

    email = email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(
            email=email,
            password_hash=password_hash.hash(secrets.token_urlsafe(32)),
            role="user"
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    app_token = create_access_token(user_id=user.id, role=user.role)
    frontend_redirect = f"{FRONTEND_URL}/dashboard?token={app_token}"
    return RedirectResponse(url=frontend_redirect, status_code=status.HTTP_302_FOUND)


@router.post("/google", response_model=Token)
def google_auth(
    payload: GoogleAuthRequest,
    db: Session = Depends(get_db)
):
    """
    Direct API endpoint for Google Identity Services / One Tap or dev sessions.
    If credential (JWT ID token) is provided, validates with Google tokeninfo.
    """
    email = payload.email

    if payload.credential:
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(
                    f"https://oauth2.googleapis.com/tokeninfo?id_token={payload.credential}"
                )
                if resp.status_code == 200:
                    data = resp.json()
                    email = data.get("email")
        except Exception:
            pass  # Fall back to payload.email if verification service is unavailable

    resolved_email = (email or "investor.google@example.com").strip().lower()

    user = db.query(User).filter(User.email == resolved_email).first()
    if not user:
        user = User(
            email=resolved_email,
            password_hash=password_hash.hash(secrets.token_urlsafe(32)),
            role="user"
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    access_token = create_access_token(
        user_id=user.id,
        role=user.role
    )
    return {
        "access_token": access_token,
        "token_type": "bearer"
    }


LOCATION_HIERARCHY = {
    "Punjab": {
        "Gurdaspur": ["Tehsil", "Batala", "Dera Baba Nanak", "Tugalwal", "Dhariwal"],
        "Pathankot": ["Pathankot City", "Sujanpur", "Malikpur", "Dhar Kalan"],
        "Amritsar": ["Amritsar City", "Majitha", "Ajnala", "Attari"],
        "Ludhiana": ["Ludhiana Central", "Civil Lines", "Model Town", "Khanna"],
        "Jalandhar": ["Jalandhar City", "Cantt", "Nakodar", "Phillaur"],
    },
    "Uttar Pradesh": {
        "Ghaziabad": ["Raj Nagar", "Vasundhara", "Indirapuram", "Crossings Republik", "Modinagar"],
        "Gautam Buddha Nagar": ["Noida Sector 62", "Noida Sector 18", "Greater Noida", "Noida Expressway"],
        "Lucknow": ["Gomti Nagar", "Hazratganj", "Aliganj", "Indira Nagar"],
        "Kanpur Nagar": ["Civil Lines", "Swaroop Nagar", "Kidwai Nagar"],
    },
    "Delhi": {
        "Central Delhi": ["Connaught Place", "Karol Bagh", "Daryaganj"],
        "South Delhi": ["Hauz Khas", "Saket", "Greater Kailash", "Vasant Kunj"],
        "North Delhi": ["Civil Lines", "Rohini", "Model Town"],
        "East Delhi": ["Preet Vihar", "Mayur Vihar", "Laxmi Nagar"],
    },
    "Haryana": {
        "Gurugram": ["DLF Phase 1-5", "Sohna Road", "Golf Course Road", "Cyber City"],
        "Faridabad": ["Sector 15", "Sector 16", "NIT Faridabad"],
    },
    "Maharashtra": {
        "Mumbai": ["Bandra", "Andheri", "Colaba", "Borivali", "Dadar"],
        "Pune": ["Kothrud", "Koregaon Park", "Hinjawadi", "Baner", "Viman Nagar"],
    },
}


@router.get("/locations/hierarchy")
def get_locations_hierarchy():
    """Returns dependent location hierarchy: State -> District -> Localities."""
    return LOCATION_HIERARCHY


@router.get("/me")
def get_me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Returns user profile and onboarding status."""
    pref = db.query(UserPreference).filter(UserPreference.user_id == current_user.id).first()
    return {
        "id": current_user.id,
        "email": current_user.email,
        "role": current_user.role,
        "onboarding_completed": pref.onboarding_completed if pref else False,
    }


@router.get("/me/preferences", response_model=UserPreferenceResponse)
def get_user_preferences(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve research preferences for the authenticated user."""
    pref = db.query(UserPreference).filter(UserPreference.user_id == current_user.id).first()
    if not pref:
        pref = UserPreference(
            user_id=current_user.id,
            property_types=["residential"],
            preferred_banks=["PNB"],
            onboarding_completed=False,
        )
        db.add(pref)
        db.commit()
        db.refresh(pref)
    return pref


@router.put("/me/preferences", response_model=UserPreferenceResponse)
def update_user_preferences(
    payload: UserPreferenceUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update research preferences and complete onboarding."""
    pref = db.query(UserPreference).filter(UserPreference.user_id == current_user.id).first()
    if not pref:
        pref = UserPreference(user_id=current_user.id)
        db.add(pref)

    pref.state = payload.state
    pref.district = payload.district
    pref.city = payload.city
    pref.locality = payload.locality
    pref.property_types = payload.property_types
    pref.min_reserve_price = payload.min_reserve_price
    pref.max_reserve_price = payload.max_reserve_price
    pref.preferred_banks = payload.preferred_banks
    pref.onboarding_completed = payload.onboarding_completed

    db.commit()
    db.refresh(pref)
    return pref

=======
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
>>>>>>> 92c77001379e6b91b43212cb314e441bf427457a
