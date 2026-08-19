from fastapi import FastAPI
from app.routes.properties import router as properties_router
from app.routes.auth import router as auth_router

from app.database import engine
from app.models import Base #benchodi neeeeeeeeeeeeEEEEEEe

Base.metadata.create_all(engine)

app = FastAPI()

app.include_router(properties_router)
app.include_router(auth_router)

@app.get("/")
def root():
    return {"message": "Foreclosure Intelligence API"}



#FastAPI automatically parses these parameters into your endpoint function arguments
 # /properties/{property_id}parameterized route to get a specific property by its ID
#Multiple query parameters to filter properties by price range GET /properties?min_price=200000&max_price=400000 ?starts the queery string and & seperates parameters.
