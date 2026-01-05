from sqlalchemy import Column, Integer, String, ForeignKey, Enum
from sqlalchemy.orm import relationship
from .database import Base
import enum

class OrderStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"

class Event(Base):
    __tablename__ = "events_new"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    total_tickets = Column(Integer)
    price = Column(Integer)

class Order(Base):
    __tablename__ = "orders_new"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True) # From Keycloak
    event_id = Column(Integer, ForeignKey("events_new.id"))
    seat_id = Column(String)
    status = Column(String, default=OrderStatus.PENDING)
