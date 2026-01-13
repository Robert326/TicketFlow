import requests
import threading
import random
import time
import sys

# Configuration
BASE_URL = "http://localhost:8000"
EVENT_ID = 2
NUM_USERS = 6
DELAY_BETWEEN_ACTIONS = 0.2  # seconds
PASSWORD = "1234"

def get_user_token(username, password):
    """Authenticates a specific user to get their unique JWT"""
    try:
        resp = requests.post(f"{BASE_URL}/login", json={
            "username": username,
            "password": password
        })
        if resp.status_code == 200:
            token = resp.json().get('access_token')
            print(f"[{username}] Login Successful", flush=True)
            return token
        else:
            print(f"[{username}] Login Failed: {resp.text}", flush=True)
            return None
    except Exception as e:
        print(f"[{username}] Auth Exception: {e}", flush=True)
        return None

def simulate_user(user_index):
    username = f"user{user_index}"
    password = PASSWORD
    
    print(f"[{username}] Authenticating...", flush=True)
    token = get_user_token(username, password)
    
    if not token:
        print(f"[{username}] Skipping (No Token)", flush=True)
        return

    # Auth Header with UNIQUE token
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    try:
        # 1. Get Seats
        response = requests.get(f"{BASE_URL}/events/{EVENT_ID}/seats")
        if response.status_code != 200:
            print(f"[{username}] Failed to get seats: {response.text}", flush=True)
            return

        data = response.json()
        available_seats = [s for s in data['seats'] if s['status'] == 'available']

        if not available_seats:
            print(f"[{username}] No seats available!", flush=True)
            return

        # 2. Pick Random Seat
        seat = random.choice(available_seats)
        seat_id = seat['id']
        print(f"[{username}] Chose seat {seat_id}", flush=True)

        # 3. Reserve
        reserve_payload = {
            "user_id": username,
            "event_id": EVENT_ID,
            "seat_id": seat_id
        }
        res_resp = requests.post(f"{BASE_URL}/reserve", json=reserve_payload, headers=headers)
        
        if res_resp.status_code == 200:
            print(f"[{username}] Reserved {seat_id} successfully.", flush=True)
        elif res_resp.status_code == 409:
            print(f"[{username}] Failed to reserve {seat_id} (Already taken).", flush=True)
            return
        else:
            print(f"[{username}] Reserve error: {res_resp.text}", flush=True)
            return

        time.sleep(random.uniform(0.5, 2.0))

        # 4. Buy
        buy_payload = {
            "user_id": username,
            "event_id": EVENT_ID,
            "seat_id": seat_id,
            "email": f"{username}@simulation.com"
        }
        buy_resp = requests.post(f"{BASE_URL}/buy", json=buy_payload, headers=headers)

        if buy_resp.status_code == 200:
            print(f"[{username}] BOUGHT {seat_id}!", flush=True)
        else:
            print(f"[{username}] Buy failed for {seat_id}: {buy_resp.text}", flush=True)

    except Exception as e:
        print(f"[{username}] Exception: {e}", flush=True)

def main():
    print("--- Starting Load Test Simulation ---")
    print(f"Target: {NUM_USERS} concurrent users")
    
    threads = []
    
    # Create threads
    for i in range(1, NUM_USERS + 1):
        t = threading.Thread(target=simulate_user, args=(i,))
        threads.append(t)
        t.start()
        # Stagger starts
        time.sleep(0.2)

    # Wait for all
    for t in threads:
        t.join()

    print("Load Test Completed.")

if __name__ == "__main__":
    main()
