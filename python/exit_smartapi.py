import os
import json
from dotenv import load_dotenv
from SmartApi import SmartConnect
from logzero import logger

# Set the path for the angelalgo directory
ANGELALGO_PATH = r"C:\Users\user\projects\angelalgo"

def select_env_file():
    print("Select mode for logout environment:")
    print("1. Trading")
    print("2. Historical Data")
    choice = input("Enter choice (1 or 2): ").strip()
    env_file = ".env.trading" if choice == "1" else ".env.historical"
    env_path = os.path.join(ANGELALGO_PATH, env_file)
    if load_dotenv(env_path):
        print(f"✅ {env_file} loaded successfully!")
    else:
        print(f"❌ Failed to load {env_file}!")
    return env_file

def load_auth_data():
    """Load auth token and client ID from auth_token.json stored under a 'data' key."""
    token_path = os.path.join(ANGELALGO_PATH, "auth_token.json")
    if os.path.exists(token_path):
        with open(token_path, "r") as file:
            data = json.load(file)
            token_data = data.get("data", {})
            return token_data.get("auth_token"), token_data.get("client_id")
    return None, None

def attempt_logout(token, client_id, description, api_key):
    # Provide API key to SmartConnect so that X-PrivateKey header is set.
    smart_api = SmartConnect(api_key=api_key)
    smart_api.setAccessToken(token)
    response = smart_api.terminateSession(client_id)
    if response.get("status"):
        logger.info(f"Logout Successful with {description}! Response: {response}")
    else:
        logger.error(f"Logout Failed with {description}! Response: {response}")
    return response

def logout():
    try:
        # User selects the environment file to load.
        select_env_file()
        api_key = os.getenv("API_KEY")
        if not api_key:
            logger.error("No API_KEY found in the environment. Ensure the .env file is set up correctly.")
            return
        
        auth_token, client_id = load_auth_data()
        if not auth_token or not client_id:
            logger.error("No valid auth token or client ID found. Please log in first.")
            return

        # Debug print the token from auth_token.json.
#        #print("Token read from auth_token.json:", auth_token)

        # Use only token without the Bearer prefix if present.
        if auth_token.startswith("Bearer "):
            auth_token = auth_token[len("Bearer "):]
        
        # Attempt logout with the token (without Bearer prefix).
        attempt_logout(auth_token, client_id, "token without Bearer prefix", api_key)
    
    except Exception as e:
        logger.exception(f"Logout error: {e}")

if __name__ == "__main__":
    logout()