import requests
import sys

BASE_URL = "http://localhost:8000/api"

def main():
    print("Logging in a test user...")
    resp = requests.post(f"{BASE_URL}/auth/login", json={"username": "stu_demo", "password": "pwd", "role": "student"})
    if resp.status_code != 200:
        print("Login failed:", resp.text)
        sys.exit(1)
        
    data = resp.json()
    token = data["access_token"]
    user_id = data["user_id"]
    print(f"Logged in, user_id = {user_id}")
    
    print("Fetching profile...")
    headers = {"Authorization": f"Bearer {token}"}
    profile_resp = requests.get(f"{BASE_URL}/students/{user_id}/profile", headers=headers)
    print("Profile status code:", profile_resp.status_code)
    print("Profile response:", profile_resp.text)

if __name__ == "__main__":
    main()
