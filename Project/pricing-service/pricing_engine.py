import time
import os
import logging
from sqlalchemy import create_engine, text
from datetime import datetime, timedelta

# Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@db:5432/ticketflow")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "15"))  # Check every 15 seconds

# Setup Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - [PRICING] - %(message)s")
logger = logging.getLogger(__name__)

# Logic Constants
SURGE_THRESHOLD = 5      # If > 5 tickets sold in last min -> Surge
SURGE_MULTIPLIER = 1.10  # +10%
MAX_PRICE = 500          # Maximum price cap

def get_engine():
    return create_engine(DATABASE_URL)

def run_pricing_engine():
    engine = get_engine()
    
    while True:
        try:
            with engine.connect() as conn:
                # 1. Get Active Events (not sold out)
                events = conn.execute(text("SELECT id, name, price, total_tickets FROM events_new")).fetchall()
                
                for event in events:
                    event_id, name, current_price, total_tickets = event
                    
                    # 2. Calculate Velocity (Sales in last 60 seconds)
                    last_min = datetime.utcnow() - timedelta(seconds=60)
                    query_sales = text("""
                        SELECT COUNT(*) FROM orders_new 
                        WHERE event_id = :eid 
                        AND created_at >= :ts
                        AND status IN ('confirmed', 'processing', 'completed')
                    """)
                    sales_last_min = conn.execute(query_sales, {"eid": event_id, "ts": last_min}).scalar()
                    
                    # 3. Apply Surge Pricing Logic (Prices only go UP or stay STEADY)
                    new_price = current_price
                    action = "STEADY"
                    
                    if sales_last_min >= SURGE_THRESHOLD:
                         new_price = int(current_price * SURGE_MULTIPLIER)
                         action = "SURGE (+10%)"
                    
                    # 4. Enforce Price Cap
                    if new_price > MAX_PRICE: new_price = MAX_PRICE
                    
                    # 5. Update DB if price changed
                    if new_price != current_price:
                        update_query = text("UPDATE events_new SET price = :p WHERE id = :eid")
                        conn.execute(update_query, {"p": new_price, "eid": event_id})
                        conn.commit()
                        logger.info(f"Event '{name}' (ID {event_id}): Sales {sales_last_min}/min -> {action}. Price {current_price} -> {new_price}")
                    else:
                        logger.debug(f"Event '{name}': Sales {sales_last_min}/min. Price steady at {current_price}.")
                        
        except Exception as e:
            logger.error(f"Error in pricing loop: {e}")
            
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    run_pricing_engine()
