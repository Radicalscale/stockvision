import requests

BASE_URL = "http://localhost:5050"

def test_auth():
    print("--- Testing Redirects ---")
    r = requests.get(BASE_URL, allow_redirects=False)
    print(f"GET / redirect status: {r.status_code}")
    print(f"Location Header: {r.headers.get('Location')}")
    
    print("\n--- Testing Signup ---")
    signup_data = {"email": "test_user@example.com", "password": "password123"}
    r = requests.post(f"{BASE_URL}/api/auth/signup", json=signup_data)
    print(f"POST /api/auth/signup logic: {r.status_code}, {r.json()}")
    
    print("\n--- Testing Login ---")
    session = requests.Session()
    login_data = {"email": "test_user@example.com", "password": "password123"}
    r = session.post(f"{BASE_URL}/api/auth/login", json=login_data)
    print(f"POST /api/auth/login: {r.status_code}, {r.json()}")
    
    print("\n--- Testing Auth Status ---")
    r = session.get(f"{BASE_URL}/api/auth/status")
    print(f"GET /api/auth/status: {r.status_code}, {r.json()}")
    
    print("\n--- Testing Dashboard Access ---")
    r = session.get(BASE_URL)
    print(f"GET / (after login): {r.status_code}")
    
    print("\n--- Testing Logout ---")
    r = session.post(f"{BASE_URL}/api/auth/logout")
    print(f"POST /api/auth/logout: {r.status_code}, {r.json()}")
    
    print("\n--- Testing Auth Status (after logout) ---")
    r = session.get(f"{BASE_URL}/api/auth/status")
    print(f"GET /api/auth/status: {r.status_code}, {r.json()}")

if __name__ == "__main__":
    try:
        test_auth()
    except Exception as e:
        print(f"Error: {e}")
