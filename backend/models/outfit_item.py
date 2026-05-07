from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.orm import relationship

from database import Base

class OutfitItem(Base):
    __tablename__ = "outfit_items"

    outfit_id = Column(Integer, ForeignKey("outfits.id"), primary_key=True)
    item_id = Column(Integer, ForeignKey("items.id"), primary_key=True)

    outfit = relationship("Outfit", back_populates="items")
    item = relationship("Item", back_populates="outfits")
