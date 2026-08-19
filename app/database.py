import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

#Base has to be defined in exactly one place, and every model must import that same instance — this goes back directly to what we just covered: Base.metadata is a shared registry, and sharing only works if everyone is inheriting from the same object.

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")# retrieves the value from the ().env)environment.

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not configured"
    )


engine = create_engine(DATABASE_URL) # the DBconnection itself
#engine holds the actual connection config (URL, credentials, pool settings

Base= declarative_base()

SessionLocal = sessionmaker(bind=engine)#factory that creates sessions using that connection


#The general principle, worth keeping beyond just this case: anything that needs to be shared and consistent across multiple files — Base, engine, SessionLocal — should be defined in exactly one place and imported everywhere else it's needed, never redefined. This is the same reasoning, generalized, behind why we were careful earlier about SessionLocal living in database.py rather than being recreated inside every route file.