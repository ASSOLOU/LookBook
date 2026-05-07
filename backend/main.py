from datetime import date, datetime, timedelta
import json
import os
import secrets
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
import uvicorn

from database import Base, SessionLocal, engine
import models
from models.item import Item
from models.outfit import Outfit
from models.outfit_item import OutfitItem
from models.rule import Rule
from models.trip import Trip
from models.trip_history import TripHistory
from models.user import User
from models.weather_cache import WeatherCache
from passlib.context import CryptContext


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
TOKENS: dict[str, int] = {}


class UserCreate(BaseModel):
    username: str
    email: str
    password: str


class UserOut(BaseModel):
    id: int
    username: str
    email: str

    class Config:
        from_attributes = True


class UserLogin(BaseModel):
    email: str
    password: str


class TokenOut(BaseModel):
    token: str


class ItemCreate(BaseModel):
    user_id: int
    name: str
    category: str
    color: str | None = None
    warmth: int | None = 0
    waterproof: bool | None = False
    style: str | None = None


class ItemOut(BaseModel):
    id: int
    user_id: int
    name: str
    category: str
    color: str | None = None
    warmth: int
    waterproof: bool
    style: str | None = None

    class Config:
        from_attributes = True


class TripCreate(BaseModel):
    user_id: int
    destination: str
    start_date: date
    end_date: date
    notes: str | None = None


class TripOut(BaseModel):
    id: int
    user_id: int
    destination: str
    start_date: date
    end_date: date
    notes: str | None = None

    class Config:
        from_attributes = True


class RuleCreate(BaseModel):
    name: str
    description: str | None = None
    active: bool | None = True
    temperature_min: float | None = None
    temperature_max: float | None = None
    allow_precipitation: bool | None = True
    max_wind: float | None = None
    max_uv: float | None = None
    category: str | None = None


class RuleOut(BaseModel):
    id: int
    name: str
    description: str | None = None
    active: bool
    temperature_min: float | None = None
    temperature_max: float | None = None
    allow_precipitation: bool
    max_wind: float | None = None
    max_uv: float | None = None
    category: str | None = None

    class Config:
        from_attributes = True


class OutfitCreate(BaseModel):
    user_id: int
    trip_id: int
    name: str
    item_ids: list[int]


class OutfitOut(BaseModel):
    id: int
    user_id: int
    trip_id: int
    name: str
    item_ids: list[int]

    class Config:
        from_attributes = True


class TripHistoryCreate(BaseModel):
    trip_id: int
    user_id: int
    action: str
    details: str | None = None


class TripHistoryOut(BaseModel):
    id: int
    trip_id: int
    user_id: int
    action: str
    details: str | None = None

    class Config:
        from_attributes = True


class WeatherResponse(BaseModel):
    location: str
    provider: str
    fetched_at: datetime
    expires_at: datetime
    data: dict


class RecommendationOut(BaseModel):
    trip_id: int
    user_id: int
    destination: str
    weather: dict
    recommended_item_ids: list[int]
    combination_count: int
    rules_applied: list[str]


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)


@app.get("/")
def read_root():
    return {"message": "Backend Lookbook fonctionne"}


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(authorization: str | None = Header(None), db: Session = Depends(get_db)) -> User:
    if not authorization:
        raise HTTPException(status_code=401, detail="Token manquant")

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="En-tete Authorization invalide")

    user_id = TOKENS.get(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Token invalide")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="Utilisateur introuvable")
    return user


OPENWEATHER_GEOCODING_URL = "https://api.openweathermap.org/geo/1.0/direct"
OPENWEATHER_ONECALL_URL = "https://api.openweathermap.org/data/3.0/onecall"
OPENWEATHER_PROVIDER = "openweather"
CACHE_TTL_MINUTES = 30


def fetch_openweather_location(location: str) -> dict:
    api_key = os.getenv("OPENWEATHER_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Cle OpenWeather manquante")

    params = {"q": location, "limit": 1, "appid": api_key}
    request = Request(f"{OPENWEATHER_GEOCODING_URL}?{urlencode(params)}")
    with urlopen(request, timeout=10) as response:
        data = json.loads(response.read().decode("utf-8"))

    if not data:
        raise HTTPException(status_code=404, detail="Localisation introuvable")
    return data[0]


def fetch_openweather_forecast(lat: float, lon: float) -> dict:
    api_key = os.getenv("OPENWEATHER_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Cle OpenWeather manquante")

    params = {
        "lat": lat,
        "lon": lon,
        "exclude": "minutely,hourly,alerts",
        "units": "metric",
        "appid": api_key,
    }
    request = Request(f"{OPENWEATHER_ONECALL_URL}?{urlencode(params)}")
    with urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def get_cached_weather(location: str, db: Session) -> dict:
    normalized = location.strip().lower()
    now = datetime.utcnow()

    cache = (
        db.query(WeatherCache)
        .filter(WeatherCache.query == normalized)
        .filter(WeatherCache.provider == OPENWEATHER_PROVIDER)
        .filter(WeatherCache.expires_at > now)
        .first()
    )
    if cache:
        return {
            "location": location,
            "provider": OPENWEATHER_PROVIDER,
            "fetched_at": cache.fetched_at,
            "expires_at": cache.expires_at,
            "data": json.loads(cache.response_data),
        }

    geo = fetch_openweather_location(normalized)
    forecast = fetch_openweather_forecast(geo["lat"], geo["lon"])
    expires_at = now + timedelta(minutes=CACHE_TTL_MINUTES)

    db.add(
        WeatherCache(
            query=normalized,
            provider=OPENWEATHER_PROVIDER,
            response_data=json.dumps(forecast),
            fetched_at=now,
            expires_at=expires_at,
        )
    )
    db.commit()

    return {
        "location": location,
        "provider": OPENWEATHER_PROVIDER,
        "fetched_at": now,
        "expires_at": expires_at,
        "data": forecast,
    }


def build_recommendation_rules(weather: dict, items: list[Item], db: Session) -> tuple[list[int], list[str]]:
    recommended: list[int] = []
    rules_applied: list[str] = []
    daily = weather["data"].get("daily", [])

    if not daily:
        return recommended, rules_applied

    day_weather = daily[0]
    temp_day = day_weather.get("temp", {}).get("day", 0)
    pop = day_weather.get("pop", 0)
    wind = day_weather.get("wind_speed", 0)
    uv = day_weather.get("uvi", 0)

    active_rules = db.query(Rule).filter(Rule.active == True).all()

    for item in items:
        score = 0
        for rule in active_rules:
            applies = True
            if rule.temperature_min is not None and temp_day < rule.temperature_min:
                applies = False
            if rule.temperature_max is not None and temp_day > rule.temperature_max:
                applies = False
            if rule.allow_precipitation is False and pop > 0.1:
                applies = False
            if rule.max_wind is not None and wind > rule.max_wind:
                applies = False
            if rule.max_uv is not None and uv > rule.max_uv:
                applies = False
            if rule.category and item.category != rule.category:
                applies = False

            if applies:
                score += 1
                if rule.name not in rules_applied:
                    rules_applied.append(rule.name)

        if score >= 1:
            recommended.append(item.id)

    return recommended, rules_applied


def compute_combination_count(items: list[Item]) -> int:
    categories: dict[str, int] = {}
    for item in items:
        categories[item.category] = categories.get(item.category, 0) + 1

    count = 1
    for value in categories.values():
        count *= max(1, value)
    return count


@app.get("/weather", response_model=WeatherResponse)
def weather(location: str, db: Session = Depends(get_db)):
    return get_cached_weather(location, db)


@app.get("/recommendations/{trip_id}", response_model=RecommendationOut)
def recommendations(trip_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    trip = db.query(Trip).filter(Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Voyage non trouve")
    if trip.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Acces refuse")

    weather_data = get_cached_weather(trip.destination, db)
    user_items = db.query(Item).filter(Item.user_id == trip.user_id).all()
    recommended_item_ids, rules_applied = build_recommendation_rules(weather_data, user_items, db)

    return RecommendationOut(
        trip_id=trip.id,
        user_id=trip.user_id,
        destination=trip.destination,
        weather={
            "temp": weather_data["data"].get("daily", [{}])[0].get("temp", {}),
            "pop": weather_data["data"].get("daily", [{}])[0].get("pop", 0),
            "wind_speed": weather_data["data"].get("daily", [{}])[0].get("wind_speed", 0),
            "uvi": weather_data["data"].get("daily", [{}])[0].get("uvi", 0),
        },
        recommended_item_ids=recommended_item_ids,
        combination_count=compute_combination_count(user_items),
        rules_applied=rules_applied,
    )


@app.post("/register", response_model=UserOut)
def register(user: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == user.email).first():
        raise HTTPException(status_code=400, detail="Email deja utilise")

    new_user = User(
        username=user.username,
        email=user.email,
        hashed_password=pwd_context.hash(user.password),
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@app.post("/login", response_model=TokenOut)
def login(credentials: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == credentials.email).first()
    if not user or not pwd_context.verify(credentials.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Identifiants invalides")

    token = secrets.token_hex(16)
    TOKENS[token] = user.id
    return TokenOut(token=token)


@app.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db)):
    return db.query(User).all()


@app.get("/items", response_model=list[ItemOut])
def list_items(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Item).filter(Item.user_id == current_user.id).all()


@app.post("/items", response_model=ItemOut)
def create_item(item: ItemCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if item.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Acces refuse")

    new_item = Item(
        user_id=item.user_id,
        name=item.name,
        category=item.category,
        color=item.color,
        warmth=item.warmth or 0,
        waterproof=item.waterproof or False,
        style=item.style,
    )
    db.add(new_item)
    db.commit()
    db.refresh(new_item)
    return new_item


@app.get("/trips", response_model=list[TripOut])
def list_trips(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Trip).filter(Trip.user_id == current_user.id).all()


@app.post("/trips", response_model=TripOut)
def create_trip(trip: TripCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if trip.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Acces refuse")

    new_trip = Trip(**trip.model_dump())
    db.add(new_trip)
    db.commit()
    db.refresh(new_trip)
    return new_trip


@app.get("/rules", response_model=list[RuleOut])
def list_rules(db: Session = Depends(get_db)):
    return db.query(Rule).all()


@app.post("/rules", response_model=RuleOut)
def create_rule(rule: RuleCreate, db: Session = Depends(get_db)):
    new_rule = Rule(**rule.model_dump())
    db.add(new_rule)
    db.commit()
    db.refresh(new_rule)
    return new_rule


@app.put("/rules/{rule_id}", response_model=RuleOut)
def update_rule(rule_id: int, rule: RuleCreate, db: Session = Depends(get_db)):
    existing = db.query(Rule).filter(Rule.id == rule_id).first()
    if not existing:
        raise HTTPException(status_code=404, detail="Regle non trouvee")

    for key, value in rule.model_dump().items():
        setattr(existing, key, value)

    db.commit()
    db.refresh(existing)
    return existing


@app.post("/outfits", response_model=OutfitOut)
def create_outfit(outfit: OutfitCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if outfit.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Acces refuse")

    new_outfit = Outfit(user_id=outfit.user_id, trip_id=outfit.trip_id, name=outfit.name)
    db.add(new_outfit)
    db.commit()

    for item_id in outfit.item_ids:
        db.add(OutfitItem(outfit_id=new_outfit.id, item_id=item_id))
    db.commit()
    db.refresh(new_outfit)

    return OutfitOut(
        id=new_outfit.id,
        user_id=new_outfit.user_id,
        trip_id=new_outfit.trip_id,
        name=new_outfit.name,
        item_ids=outfit.item_ids,
    )


@app.get("/outfits", response_model=list[OutfitOut])
def list_outfits(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    outfits = db.query(Outfit).filter(Outfit.user_id == current_user.id).all()
    return [
        OutfitOut(
            id=outfit.id,
            user_id=outfit.user_id,
            trip_id=outfit.trip_id,
            name=outfit.name,
            item_ids=[link.item_id for link in outfit.items],
        )
        for outfit in outfits
    ]


@app.post("/trip-history", response_model=TripHistoryOut)
def create_trip_history(entry: TripHistoryCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if entry.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Acces refuse")

    history = TripHistory(**entry.model_dump())
    db.add(history)
    db.commit()
    db.refresh(history)
    return history


@app.get("/trip-history", response_model=list[TripHistoryOut])
def list_trip_history(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(TripHistory).filter(TripHistory.user_id == current_user.id).all()


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
