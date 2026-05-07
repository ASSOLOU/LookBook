from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, DateTime
from database import Base

class WeatherCache(Base):
    __tablename__ = "weather_cache"

    id = Column(Integer, primary_key=True, index=True)
    query = Column(String, nullable=False, index=True)
    provider = Column(String, nullable=False)
    response_data = Column(Text, nullable=False)
    fetched_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
