# websocket_stream.py (Refactored for Integration)
import threading
import time
import json
import os
from datetime import datetime
import pytz
from SmartApi.smartWebSocketV2 import SmartWebSocketV2
from logzero import logger
from login import login # Assuming login.py is in the same directory or accessible

class WebSocketStreamer:
    """
    Handles connection to the SmartAPI WebSocket feed, subscribes to instruments,
    and calls a callback function for each received tick.
    """
    def __init__(self, api_key, client_id, auth_token, feed_token, instrument_keys, on_tick_callback):
        """
        Args:
            api_key (str): Your Angel One API key.
            client_id (str): Your Angel One client ID.
            auth_token (str): The session's authentication token.
            feed_token (str): The session's feed token.
            instrument_keys (list): A list of instrument tokens (as strings) to subscribe to.
            on_tick_callback (function): The function to call with tick data.
                                         Expected signature: on_tick(timestamp, price, volume)
        """
        self.api_key = api_key
        self.client_id = client_id
        self.auth_token = auth_token
        self.feed_token = feed_token
        self.instrument_keys = instrument_keys
        self.on_tick_callback = on_tick_callback

        self.sws = None
        self.ws_thread = None
        self.is_running = False
        self.ist_tz = pytz.timezone('Asia/Kolkata')
        
        # SmartAPI requires specific exchange types. Assuming NSE_FO for this example.
        # This should be configured based on the instrument.
        self.exchange_type = 2 # 1: NSE_CM, 2: NSE_FO

    def _on_open(self, wsapp):
        """Callback executed when the WebSocket connection is opened."""
        logger.info("WebSocket Connection Opened.")
        self._subscribe()

    def _subscribe(self):
        """Subscribes to the list of instrument tokens."""
        if not self.is_running or not self.sws:
            logger.warning("Cannot subscribe, WebSocket is not running.")
            return

        logger.info(f"Subscribing to tokens: {self.instrument_keys}")
        # SmartAPI subscription format
        token_list = [
            {"exchangeType": self.exchange_type, "tokens": self.instrument_keys}
        ]
        # Mode 1 is for LTP (Last Traded Price)
        self.sws.subscribe(correlation_id="strategy_sub", mode=1, token_list=token_list)

    def _on_data(self, wsapp, message):
        """
        Callback for each message. Parses tick data and calls the strategy's on_tick method.
        """
        try:
            # We only care about price updates, not heartbeats or other messages.
            # 'last_traded_price' is the key indicator of a tick message.
            if 'last_traded_price' in message and 'last_traded_quantity' in message and 'feed_timestamp' in message:
                
                # 1. Parse Price: Sent as an integer, needs division.
                price = float(message['last_traded_price']) / 100.0
                
                # 2. Parse Volume
                volume = int(message['last_traded_quantity'])
                
                # 3. Parse Timestamp: Sent as Unix epoch milliseconds.
                epoch_ms = int(message['feed_timestamp'])
                timestamp = datetime.fromtimestamp(epoch_ms / 1000, tz=self.ist_tz)
                
                # 4. Call the strategy's callback function with the clean data
                if self.on_tick_callback:
                    self.on_tick_callback(timestamp, price, volume)

        except Exception as e:
            logger.error(f"Error processing tick message: {e}\nMessage: {message}")

    def _on_error(self, wsapp, error):
        """Callback for WebSocket errors."""
        logger.error(f"WebSocket Error: {error}")

    def _on_close(self, wsapp, code, reason):
        """Callback for when the connection is closed."""
        logger.warning(f"WebSocket Connection Closed. Code: {code}, Reason: {reason}")

    def _run_connection(self):
        """Internal method to run the WebSocket connection loop."""
        self.is_running = True
        logger.info("WebSocket thread started. Connecting...")
        
        self.sws = SmartWebSocketV2(self.auth_token, self.api_key, self.client_id, self.feed_token)
        
        # Assign the instance methods as callbacks
        self.sws.on_open = self._on_open
        self.sws.on_data = self._on_data
        self.sws.on_error = self._on_error
        self.sws.on_close = self._on_close
        
        # This call is blocking and will run until the connection closes
        self.sws.connect()
        
        # Once connect() returns, it means the connection was closed.
        self.is_running = False
        logger.info("WebSocket connection loop has ended.")

    def connect(self):
        """Establishes the WebSocket connection in a separate thread."""
        if self.is_running:
            logger.warning("Connection is already running.")
            return
            
        self.ws_thread = threading.Thread(target=self._run_connection, daemon=True)
        self.ws_thread.start()

    def stop(self):
        """Stops the WebSocket connection gracefully."""
        if not self.is_running:
            return
            
        logger.info("Stopping WebSocket connection...")
        self.is_running = False # Prevent any auto-reconnect logic if it were added
        if self.sws:
            self.sws.close_connection()
        
        if self.ws_thread and self.ws_thread.is_alive():
            self.ws_thread.join(timeout=5) # Wait for the thread to finish
            if self.ws_thread.is_alive():
                logger.warning("WebSocket thread did not terminate gracefully.")
        
        logger.info("WebSocket has been stopped.")

