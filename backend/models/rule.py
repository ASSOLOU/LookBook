from datetime import datetime

from sqlalchemy import Column, Integer, String, Boolean, Float, Text, DateTime
from database import Base

class Rule(Base):
    __tablename__ = "rules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    active = Column(Boolean, default=True)
    temperature_min = Column(Float, nullable=True)
    temperature_max = Column(Float, nullable=True)
    allow_precipitation = Column(Boolean, default=True)
    max_wind = Column(Float, nullable=True)
    max_uv = Column(Float, nullable=True)
    category = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
