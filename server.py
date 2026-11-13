import asyncio
from contextlib import suppress
from fastapi import FastAPI, APIRouter, Query
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, DESCENDING, IndexModel
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict, BeforeValidator
from typing import List, Optional, Annotated
import uuid
from datetime import datetime, timezone

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

PyObjectId = Annotated[str, BeforeValidator(str)]

INDEXES: dict[str, list[IndexModel]] = {
    "checkouts": [
        IndexModel(
            [("id", ASCENDING)],
            name="id",
            unique=True,
            partialFilterExpression={"id": {"$type": "string"}},
        ),
        IndexModel([("timestamp", DESCENDING)], name="timestamp_desc"),
        IndexModel([("table_number", ASCENDING)], name="table_number"),
    ],
}

async def ensure_indexes() -> None:
    for collection, models in INDEXES.items():
        for model in models:
            try:
                await db[collection].create_indexes([model])
            except Exception as exc:
                logging.getLogger(__name__).error("ensure_indexes(%s.%s): %s", collection, model.document["name"], exc)

app = FastAPI()
api_router = APIRouter(prefix="/api")

class BaseDocument(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    id: PyObjectId = Field(default_factory=lambda: str(uuid.uuid4()), alias="_id")

    def to_mongo(self) -> dict:
        doc = self.model_dump(by_alias=True, mode="json")
        return doc

    @classmethod
    def from_mongo(cls, doc: dict):
        doc = dict(doc)
        doc["_id"] = str(doc["_id"])
        return cls(**doc)

class CheckoutItem(BaseModel):
    name: str
    price: float
    selected: bool

class CheckoutCreate(BaseModel):
    table_number: str
    pay_mode: str
    payment_method: str
    tip_percent: int
    items: List[CheckoutItem]
    subtotal: float
    tip_amount: float
    total: float

class Checkout(BaseDocument):
    table_number: str
    pay_mode: str
    payment_method: str
    tip_percent: int
    items: List[CheckoutItem]
    subtotal: float
    tip_amount: float
    total: float
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

@api_router.get("/")
async def root():
    return {"message": "PayTable API"}

@api_router.post("/checkouts", response_model=Checkout)
async def create_checkout(input: CheckoutCreate):
    checkout = Checkout(**input.model_dump())
    await db.checkouts.insert_one(checkout.to_mongo())
    return checkout

@api_router.get("/checkouts", response_model=List[Checkout])
async def get_checkouts(table_number: Optional[str] = None, limit: int = Query(20, ge=1, le=100)):
    query = {"table_number": table_number} if table_number else {}
    docs = await db.checkouts.find(query, {"_id": 0}).sort("timestamp", -1).limit(limit).to_list(limit)
    for doc in docs:
        if isinstance(doc['timestamp'], str):
            doc['timestamp'] = datetime.fromisoformat(doc['timestamp'])
    return docs

app.include_router(api_router)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@app.on_event("startup")
async def start_index_build():
    app.state.index_task = asyncio.create_task(ensure_indexes())

@app.on_event("shutdown")
async def shutdown_db_client():
    app.state.index_task.cancel()
    with suppress(asyncio.CancelledError):
        await app.state.index_task
    client.close()