from pydantic import BaseModel

class EventCreate(BaseModel):
    name: str
    total_tickets: int
    price: int

class ReserveRequest(BaseModel):
    user_id: str
    event_id: int
    seat_id: str

class BuyRequest(BaseModel):
    user_id: str
    event_id: int
    seat_id: str
