from flask import Flask, request, jsonify
from app.database import engine, Base, SessionLocal
from app.models import Order, OrderStatus, Event
from keycloak import KeycloakOpenID
from app.services.redis_lock import acquire_lock, get_lock_owner, release_lock
import os
import json

# Create Tables
Base.metadata.create_all(bind=engine)

app = Flask(__name__)

# --- KEYCLOAK CONFIG ---
KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "http://auth-service:8080/")
REALM_NAME = "ticketflow"
CLIENT_ID = "ticketflow-client" 
CLIENT_SECRET = None 

keycloak_openid = KeycloakOpenID(server_url=KEYCLOAK_URL,
                                 client_id=CLIENT_ID,
                                 realm_name=REALM_NAME,
                                 client_secret_key=CLIENT_SECRET)

def get_db_session():
    """Helper to get a database session"""
    session = SessionLocal()
    return session

@app.teardown_appcontext
def shutdown_session(exception=None):
    pass

@app.route("/", methods=["GET"])
def read_root():
    return app.send_static_file('index.html')

# --- AUTH ENDPOINTS ---
@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")
    
    try:
        # Get Token from Keycloak
        token = keycloak_openid.token(username, password)
        # Decode token to get roles
        user_info = keycloak_openid.userinfo(token['access_token'])
        
        return jsonify(token)
    except Exception as e:
        return jsonify({"detail": "Invalid credentials or Keycloak error: " + str(e)}), 401

# --- PUBLIC ENDPOINTS ---
@app.route("/events", methods=["GET"])
def get_events():
    db = get_db_session()
    try:
        events = db.query(Event).all()
        result = []
        for e in events:
            sold = db.query(Order).filter(
                Order.event_id == e.id,
                Order.status == OrderStatus.CONFIRMED.value
            ).count()
            remaining = e.total_tickets - sold
            result.append({
                "id": e.id, 
                "name": e.name, 
                "total_tickets": e.total_tickets, 
                "price": e.price,
                "remaining": remaining
            })
        return jsonify(result)
    finally:
        db.close()

# --- ADMIN ENDPOINTS ---
@app.route("/events", methods=["POST"])
def create_event():
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return jsonify({"detail": "Missing Authorization header"}), 401
    
    try:
        token = auth_header.split(" ")[1]
        # Public Client cannot introspect. We must decode and verify signature.
        token_info = keycloak_openid.decode_token(token)
            
        roles = token_info.get("realm_access", {}).get("roles", [])
        print(f"DEBUG: User Roles: {roles}", flush=True)
        
        if "admin" not in roles:
             return jsonify({"detail": f"Admin role required. Found: {roles}"}), 403

    except Exception as e:
         return jsonify({"detail": "Auth Error: " + str(e)}), 401

    data = request.get_json()
    name = data.get("name")
    total = data.get("total_tickets")
    price = data.get("price")
    
    db = get_db_session()
    try:
        event = Event(name=name, total_tickets=total, price=price)
        db.add(event)
        db.commit()
        return jsonify({"status": "created", "id": event.id})
    except Exception as e:
        return jsonify({"detail": str(e)}), 500
    finally:
        db.close()

# --- RESERVATION (REDIS) ---
@app.route("/reserve", methods=["POST"])
def reserve_ticket():
    auth_header = request.headers.get("Authorization")
    if not auth_header: return jsonify({"detail": "Login required"}), 401
    
    try:
        # Simplified token parsing for MVP (assumes valid structure)
        token = auth_header.split(" ")[1]
    except:
        return jsonify({"detail": "Invalid Token"}), 401

    data = request.get_json()
    event_id = data.get("event_id")
    seat_id = data.get("seat_id")
    user_id = data.get("user_id") 

    lock_key = f"ticket_lock:{event_id}:{seat_id}"
    
    # 0. Check DB if already sold (Crucial Fix)
    db = get_db_session()
    try:
        existing = db.query(Order).filter(
            Order.event_id == event_id,
            Order.seat_id == seat_id,
            Order.status == OrderStatus.CONFIRMED.value
        ).first()
        if existing:
             return jsonify({"detail": f"Seat {seat_id} is ALREADY SOLD (DB)"}), 409
    finally:
        db.close()

    # Store user_id as the lock value
    if acquire_lock(lock_key, value=user_id, ttl_seconds=30):
        return jsonify({"status": "reserved", "message": "Seat Reserved for 10 mins", "lock_key": lock_key})
    else:
        owner = get_lock_owner(lock_key)
        if owner == user_id:
             return jsonify({"detail": "You already reserved this."}), 200
        return jsonify({"detail": "Seat is ALREADY RESERVED by another user"}), 409

@app.route("/buy", methods=["POST"])
def buy_ticket():
    auth_header = request.headers.get("Authorization")
    if not auth_header: return jsonify({"detail": "Login required"}), 401
    data = request.get_json()
    user_id = data.get("user_id")
    event_id = data.get("event_id")
    seat_id = data.get("seat_id")

    # 1. CHECK REDIS RESERVATION
    lock_key = f"ticket_lock:{event_id}:{seat_id}"
    owner = get_lock_owner(lock_key)
    if owner and owner != user_id:
        return jsonify({"detail": f"Cannot Buy: Seat is RESERVED by user {owner}."}), 409

    db = get_db_session()
    try:
        # 2. DB Transaction (with Lock)
        event = db.query(Event).filter(Event.id == event_id).with_for_update().first()
        if not event: return jsonify({"detail": "Event not found"}), 404
             
        sold_count = db.query(Order).filter(
            Order.event_id == event_id,
            Order.status == OrderStatus.CONFIRMED.value
        ).count()
        if sold_count >= event.total_tickets:
             return jsonify({"detail": "Event is SOLD OUT"}), 409

        existing = db.query(Order).filter(
            Order.event_id == event_id,
            Order.seat_id == seat_id,
            Order.status == OrderStatus.CONFIRMED.value
        ).first()

        if existing:
            return jsonify({"detail": f"Seat {seat_id} is ALREADY SOLD"}), 409

        # 3. Create Order
        new_order = Order(user_id=user_id, event_id=event_id, seat_id=seat_id, status=OrderStatus.CONFIRMED.value)
        db.add(new_order)
        db.commit()
        
        # 4. Release Lock (Since purchase is complete)
        if owner == user_id:
            release_lock(lock_key)
            
        return jsonify({"status": "success", "order_id": new_order.id, "message": "Ticket purchased!"})
    except Exception as e:
        db.rollback()
        return jsonify({"detail": str(e)}), 500
    finally:
        db.close()
