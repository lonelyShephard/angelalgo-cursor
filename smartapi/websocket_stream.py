# c:\Users\user\projects\angelalgo\smartapi\websocket_stream.py (Final Corrected Version)
import threading
import time
import json
import os
from datetime import datetime
import pytz
from SmartApi.smartWebSocketV2 import SmartWebSocketV2
from .log_utils import logger, tick_logger # Import our new loggers
from .login import login # The class now depends on the login function

class WebSocketStreamer:
    """
    Handles connection to the SmartAPI WebSocket feed.
    It now manages its own authentication, subscribes to instruments,
    and calls a callback function for each received tick.
    """
    def __init__(self, instrument_keys, on_tick_callback, exchange_type=1, feed_mode=1, log_ticks=False):
        """
        Args:
            instrument_keys (list): A list of instrument tokens (as strings) to subscribe to.
            on_tick_callback (function): The function to call with tick data.
                                         Expected signature: on_tick(timestamp, price, volume)
            exchange_type (int): The exchange type (1: NSE_CM, 2: NSE_FO, etc.).
            feed_mode (int): The feed type (1: LTP, 2: Quote, 3: SnapQuote).
            log_ticks (bool): If True, prints every tick to the console for real-time monitoring.
        """
        self.instrument_keys = instrument_keys
        self.on_tick_callback = on_tick_callback

        # Internal state for credentials and connection objects
        self.api_key = None
        self.client_id = None
        self.auth_token = None
        self.feed_token = None
        self.smart_api = None

        self.sws = None
        self.ws_thread = None
        self.is_running = False
        self.ist_tz = pytz.timezone('Asia/Kolkata')
        self.exchange_type = exchange_type
        self.feed_mode = feed_mode
        self.log_ticks = log_ticks

    def _authenticate_and_get_tokens(self):
        """
        Handles the entire authentication process and sets instance attributes.
        Returns True on success, False on failure.
        """
        logger.info("Performing login to get session tokens for WebSocket...")
        try:
            self.smart_api, self.auth_token, _ = login()
            if not self.smart_api or not self.auth_token:
                logger.error("Authentication failed. Cannot proceed with WebSocket.")
                return False

            self.feed_token = self.smart_api.getfeedToken()
            self.api_key = self.smart_api.api_key
            self.client_id = os.getenv("CLIENT_ID")

            if not all([self.feed_token, self.api_key, self.client_id]):
                logger.error("Failed to retrieve one or more required tokens (feed_token, api_key, client_id).")
                return False
            
            logger.info("Authentication successful. All tokens for WebSocket are ready.")
            return True

        except Exception as e:
            logger.error(f"An error occurred during the authentication process: {e}")
            return False

    def _on_open(self, wsapp):
        """Callback executed when the WebSocket connection is opened."""
        logger.info("WebSocket Connection Opened.")
        self._subscribe()

    def _subscribe(self):
        """Subscribes to the list of instrument tokens."""
        if not self.is_running or not self.sws:
            logger.warning("Cannot subscribe, WebSocket is not running.")
            return

        logger.info(f"Subscribing to tokens: {self.instrument_keys} on exchange type {self.exchange_type} with mode {self.feed_mode}")
        token_list = [{"exchangeType": self.exchange_type, "tokens": self.instrument_keys}]
        self.sws.subscribe(correlation_id="strategy_sub", mode=self.feed_mode, token_list=token_list)

    def _unsubscribe(self):
        """Unsubscribes from the list of instrument tokens."""
        if not self.is_running or not self.sws:
            logger.warning("Cannot unsubscribe, WebSocket is not running.")
            return

        logger.info(f"Unsubscribing from tokens: {self.instrument_keys} on exchange type {self.exchange_type} with mode {self.feed_mode}")
        token_list = [{"exchangeType": self.exchange_type, "tokens": self.instrument_keys}]
        self.sws.unsubscribe(correlation_id="strategy_sub", mode=self.feed_mode, token_list=token_list)

    def _on_data(self, wsapp, message):
        """
        Callback for each message. Parses tick data and calls the strategy's on_tick method.
        This is now robust enough to handle index ticks that may not have volume data.
        """
        # The raw tick logging can be commented out now that we've found the issue.
        # logger.info(f"RAW_TICK_RECEIVED: {message}")
        
        try:
            # FIX: The condition now correctly checks for 'exchange_timestamp'.
            if 'last_traded_price' in message and 'exchange_timestamp' in message:
                price = float(message['last_traded_price']) / 100.0
                epoch_ms = int(message['exchange_timestamp'])
                timestamp = datetime.fromtimestamp(epoch_ms / 1000, tz=self.ist_tz)
                
                # Volume is correctly treated as optional.
                volume = int(message.get('last_traded_quantity', 0))
                
                # 1. Unconditionally log to the dedicated price_ticks.log file.
                tick_logger.info(f"{timestamp.isoformat()},{price:.2f},{volume}")

                if self.on_tick_callback:
                    # 2. Conditionally print to the console for visibility.
                    if self.log_ticks:
                        print(f"LIVE TICK: {timestamp.strftime('%Y-%m-%d %H:%M:%S')} | Price: {price:<8.2f} | Volume: {volume}")
                    # 3. Always call the strategy callback.
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
        """Internal method to authenticate and then run the WebSocket connection loop."""
        self.is_running = True
        logger.info("WebSocket thread started. Beginning authentication...")
        
        if not self._authenticate_and_get_tokens():
            logger.error("Halting WebSocket thread due to authentication failure.")
            self.is_running = False
            return

        self.sws = SmartWebSocketV2(self.auth_token, self.api_key, self.client_id, self.feed_token)
        
        self.sws.on_open = self._on_open
        self.sws.on_data = self._on_data
        self.sws.on_error = self._on_error
        self.sws.on_close = self._on_close
        
        logger.info("Connecting to WebSocket feed...")
        self.sws.connect()
        
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
        if not self.is_running and not self.sws:
            return
            
        logger.info("Stopping WebSocket connection...")
        self.is_running = False
        if self.sws:
            self.sws.close_connection()
        
        if self.ws_thread and self.ws_thread.is_alive():
            self.ws_thread.join(timeout=5)
            if self.ws_thread.is_alive():
                logger.warning("WebSocket thread did not terminate gracefully.")
        
        logger.info("WebSocket has been stopped.")

    def pause_stream(self):
        """Pauses the data stream by unsubscribing from tokens."""
        logger.info("Pausing WebSocket data stream...")
        self._unsubscribe()

    def resume_stream(self):
        """Resumes the data stream by re-subscribing to tokens."""
        logger.info("Resuming WebSocket data stream...")
        self._subscribe()
