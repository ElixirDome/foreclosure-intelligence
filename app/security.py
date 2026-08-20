import os
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.models import (
User,
Property#required in >def require_property_owner
)
import jwt
from dotenv import load_dotenv
from pwdlib import PasswordHash
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer


load_dotenv()

oauth2_scheme = OAuth2PasswordBearer(#"When an endpoint requires authentication, look for a Bearer token in the Authorization header."
    tokenUrl="/auth/login"
)

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    print("CURRENT USER DB:", id(db))
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={
            "WWW-Authenticate": "Bearer"#Right now, in this Python code, it's a dict — a native Python data structure, living in memory, nothing to do with text/JSON yet.
# It only becomes JSON at the moment FastAPI serializes the HTTP response — converting this Python dict into an actual JSON-formatted string that gets sent over the network to the client.
        }
    )

    try:
        payload = decode_access_token(token)

        user_id = payload.get("sub")

        if user_id is None:
            raise credentials_exception

        user_id = int(user_id)

    except (jwt.InvalidTokenError, ValueError):
        raise credentials_exception

    user = (
        db.query(User)
        .filter(User.id == user_id)
        .first()
    )

    if user is None:
        raise credentials_exception

    return user

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

if not JWT_SECRET_KEY:
    raise RuntimeError(
        "JWT_SECRET_KEY is not configured"
    )

password_hash = PasswordHash.recommended()

def verify_password(
    plain_password: str,
    hashed_password: str
) -> bool:
    return password_hash.verify(
        plain_password,
        hashed_password
    )

def create_access_token(
    user_id: int,
    role: str
) -> str:

    expire = datetime.now(timezone.utc) + timedelta(
        minutes=30
    )

    payload = {
        "sub": str(user_id),# sub means subject sub="1" means userID =1
        "role": role,
        "exp": expire # Expiration time , prevents the token from being valid forever.
    }

    token = jwt.encode(
        payload,
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM
    )
    return token

def decode_access_token(token: str) -> dict:
   
    return jwt.decode(
        token,
        JWT_SECRET_KEY,
        algorithms=[JWT_ALGORITHM]
    )
    # JWT
    #  ↓
    # signature verification
    #  ↓
    # expiration verification
    #  ↓
    # payload
def require_role(required_role: str):

    def role_checker(
        current_user: User = Depends(get_current_user)#get_current_user is a function — current_user is assigned the return value of calling that function, and critically, you never call it yourself. Depends() is what tells FastAPI "call this function for me, and give the result to this parameter."
    ):#notice: no parentheses after get_current_user here. Same rule as outer vs outer() from the closure example — you're passing the function itself to Depends, not calling it. Depends receives the function as a reference, and FastAPI itself calls it later, at request time, then substitutes the result in as current_user's actual value.
        if current_user.role != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )

        return current_user

    return role_checker

def require_property_owner(
    property_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    print("OWNER DB:", id(db))
    property = (
        db.query(Property)
        .filter(Property.id == property_id)
        .first()
    )

    if property is None:
        raise HTTPException(
            status_code=404,
            detail="Property not found"
        )

    if ( property.user_id != current_user.id
        and current_user.role != "admin"
    ):
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to modify this property"
        )

    return property
# Authorization header
#         ↓
# OAuth2PasswordBearer
#         ↓
# token
#         ↓
# decode_access_token()
#         ↓
# sub = user ID
#         ↓
# PostgreSQL
#         ↓
# User