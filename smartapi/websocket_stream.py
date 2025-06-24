from SmartApi.smartWebSocketV2 import SmartWebSocketV2
from logzero import logger
from login import login

sws = None  # Global variable for the websocket instance

def on_data(wsapp, message):
    logger.info(f"Market Data: {message}")

def on_open(wsapp):
    logger.info("WebSocket Connected!")
    # Subscribe here using the global sws object
    if sws:
        sws.subscribe("nse_cm|26009")  # Example: NIFTY 50 spot

def on_error(wsapp, error):
    logger.error(f"WebSocket Error: {error}")

def on_close(wsapp):
    logger.info("WebSocket Disconnected!")

def start_websocket():
    global sws
    smart_api, auth_token, client_id = login()
    if smart_api is None or auth_token is None:
        logger.error("Could not authenticate. Exiting.")
        return

    try:
        feed_token = smart_api.getfeedToken()
    except Exception as e:
        logger.error(f"Could not get feedToken: {e}")
        return

    api_key = smart_api.api_key

    sws = SmartWebSocketV2(api_key, client_id, auth_token, feed_token)
    sws.on_open = on_open
    sws.on_data = on_data
    sws.on_error = on_error
    sws.on_close = on_close
    sws.connect()

if __name__ == "__main__":
    start_websocket()
