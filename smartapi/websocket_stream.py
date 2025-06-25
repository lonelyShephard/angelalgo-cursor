import threading
import time
import json
import os
import tkinter as tk
from tkinter import ttk, messagebox
from SmartApi.smartWebSocketV2 import SmartWebSocketV2
from logzero import logger
from login import login

# --- Global State Management ---
sws = None
ws_thread = None
is_running = False
current_tokens = []
current_exchange_type = 1

# --- WebSocket Callbacks ---

def on_data(wsapp, message):
    """
    Callback function to handle incoming market data.
    It now correctly parses the price for clear logging.
    """
    try:
        # Check if the message is a price update (LTP mode)
        if message.get('subscription_mode') == 1 and 'last_traded_price' in message:
            token = message.get('token')
            # The API sends price as an integer (e.g., 12345 for 123.45).
            # We must divide by 100.0 to get the actual price.
            raw_price = message['last_traded_price']
            actual_price = raw_price / 100.0
            logger.info(f"Tick for Token {token}: Price = {actual_price:.2f}")
        else:
            # Log other message types as-is
            logger.info(f"System Message: {message}")
    except Exception as e:
        logger.error(f"Error processing message: {message} - Error: {e}")

def on_open(wsapp):
    """Callback function triggered when the WebSocket connection is established."""
    logger.info("WebSocket Connected!")
    # Auto-subscribe if tokens are set
    if sws and current_tokens:
        logger.info(f"Subscribing to tokens: {current_tokens}")
        sws.subscribe(
            correlation_id="sub1",
            mode=1,
            token_list=[{"exchangeType": current_exchange_type, "tokens": current_tokens}]
        )

def on_error(wsapp, error):
    """Callback function to handle WebSocket errors."""
    logger.error(f"WebSocket Error: {error}")
    messagebox.showerror("WebSocket Error", str(error))

def on_close(wsapp, code, reason):
    """Callback function triggered when the WebSocket connection is closed."""
    logger.warning(f"WebSocket Disconnected! Code: {code}, Reason: {reason}")

# --- WebSocket Core Functions ---

def start_websocket_connection():
    """
    Authenticates, retrieves tokens, and starts a single WebSocket connection attempt.
    """
    global sws
    
    logger.info("Attempting to start WebSocket connection...")
    
    # The login() function returns (smart_api, auth_token, refresh_token).
    # We need the client_id, which login() writes to auth_token.json.
    smart_api, auth_token, _ = login()
    
    if not smart_api or not auth_token:
        logger.error("Authentication failed. Will retry.")
        return

    # The login() function saves the client_id in auth_token.json.
    # We read it from there to ensure we have the correct value.
    client_id = None
    try:
        ANGELALGO_PATH = r"C:\Users\user\projects\angelalgo"
        token_path = os.path.join(ANGELALGO_PATH, "auth_token.json")
        with open(token_path, "r") as f:
            data = json.load(f)
            client_id = data.get("data", {}).get("client_id")
    except Exception as e:
        logger.error(f"Could not read client_id from {token_path}: {e}")
        return

    if not client_id:
        logger.error("Failed to retrieve client_id after login. Will retry.")
        return

    try:
        feed_token = smart_api.getfeedToken()
    except Exception as e:
        logger.error(f"Could not get feedToken: {e}")
        return

    api_key = smart_api.api_key

    sws = SmartWebSocketV2(auth_token, api_key, client_id, feed_token)
    
    sws.on_open = on_open
    sws.on_data = on_data
    sws.on_error = on_error
    sws.on_close = lambda ws, code, reason: on_close(ws, code, reason)

    sws.connect()

def run_websocket_manager():
    """A robust manager that handles automatic reconnections."""
    global is_running
    is_running = True
    
    reconnect_delay = 5
    max_reconnect_delay = 60

    while is_running:
        start_websocket_connection()
        
        if is_running:
            logger.warning(f"WebSocket disconnected. Reconnecting in {reconnect_delay}s...")
            time.sleep(reconnect_delay)
            reconnect_delay = min(reconnect_delay * 2, max_reconnect_delay)
    
    logger.info("WebSocket manager has been stopped.")

def stop_websocket():
    """Stops the WebSocket connection gracefully and prevents reconnection."""
    global is_running, sws
    if not is_running:
        return
        
    logger.info("Stopping WebSocket connection and manager...")
    is_running = False
    if sws:
        sws.close_connection()
    sws = None

def pause_webstream():
    """Unsubscribes from the current set of tokens, effectively pausing the data flow."""
    global sws, current_tokens
    if sws and current_tokens:
        sws.unsubscribe(
            correlation_id="sub1",
            mode=1,
            token_list=[{"exchangeType": current_exchange_type, "tokens": current_tokens}]
        )
        logger.info(f"WebSocket stream paused (unsubscribed from {current_tokens}).")
        messagebox.showinfo("Paused", "WebSocket stream paused.")
    else:
        messagebox.showwarning("Warning", "Cannot pause. Not connected or no tokens subscribed.")

def resume_webstream(tokens_entry):
    """
    Resumes the stream by reading the latest tokens from the GUI and subscribing.
    This allows you to change tokens while paused.
    """
    global sws, current_tokens

    # Read the potentially new list of tokens from the entry box
    new_tokens = [t.strip() for t in tokens_entry.get().split(",") if t.strip()]
    if not new_tokens:
        messagebox.showwarning("Input Error", "Cannot resume with no tokens. Please enter at least one.")
        return

    # Update the global state with the new tokens
    current_tokens = new_tokens

    if sws:
        sws.subscribe(
            correlation_id="sub1",
            mode=1,
            token_list=[{"exchangeType": current_exchange_type, "tokens": current_tokens}]
        )
        logger.info(f"WebSocket stream resumed with new tokens: {current_tokens}")
        messagebox.showinfo("Resumed", f"Resumed with tokens: {', '.join(current_tokens)}")
    else:
        messagebox.showwarning("Warning", "Cannot resume. Not connected.")

def update_tokens(tokens_entry):
    """
    Updates the token subscription on-the-fly without pausing the stream.
    It unsubscribes from the old tokens and subscribes to the new ones.
    """
    global sws, current_tokens, is_running

    if not is_running or not sws:
        messagebox.showwarning("Warning", "WebSocket is not running. Cannot update tokens.")
        return

    new_tokens = [t.strip() for t in tokens_entry.get().split(",") if t.strip()]
    if not new_tokens:
        messagebox.showwarning("Input Error", "Please enter at least one token to update.")
        return

    # 1. Unsubscribe from the old tokens
    if current_tokens:
        sws.unsubscribe(
            correlation_id="sub1",
            mode=1,
            token_list=[{"exchangeType": current_exchange_type, "tokens": current_tokens}]
        )
        logger.info(f"Unsubscribed from old tokens: {current_tokens}")

    # 2. Update the global state
    current_tokens = new_tokens

    # 3. Subscribe to the new tokens
    sws.subscribe(
        correlation_id="sub1",
        mode=1,
        token_list=[{"exchangeType": current_exchange_type, "tokens": current_tokens}]
    )
    logger.info(f"Subscription updated to new tokens: {current_tokens}")
    messagebox.showinfo("Updated", f"Now streaming data for: {', '.join(current_tokens)}")

def gui():
    root = tk.Tk()
    root.title("SmartAPI WebSocket Stream Control")

    def on_connect():
        global ws_thread, current_tokens, current_exchange_type, is_running
        
        if is_running:
            messagebox.showwarning("Warning", "WebSocket is already running.")
            return

        tokens = [t.strip() for t in tokens_entry.get().split(",") if t.strip()]
        if not tokens:
            messagebox.showwarning("Input Error", "Please enter at least one token.")
            return
            
        current_tokens = tokens
        current_exchange_type = int(exchange_var.get().split()[0])
        
        ws_thread = threading.Thread(target=run_websocket_manager, daemon=True)
        ws_thread.start()
        messagebox.showinfo("Connecting", "WebSocket manager started in the background.")

    def on_closing():
        """Handles window close, stop button, and Ctrl+C for a graceful shutdown."""
        if is_running and not messagebox.askokcancel("Quit", "Do you want to stop the WebSocket and exit?"):
            return
        
        stop_websocket()
        if ws_thread and ws_thread.is_alive():
            ws_thread.join(timeout=2)
        root.destroy()

    # --- GUI Layout ---
    tk.Label(root, text="Exchange Type:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
    exchange_var = tk.StringVar(value="1")
    exchange_combo = ttk.Combobox(root, textvariable=exchange_var, values=["1 (NSE_CM)", "2 (NSE_FO)", "3 (BSE_CM)", "4 (BSE_FO)", "5 (MCX_FO)"], width=20, state="readonly")
    exchange_combo.grid(row=0, column=1, padx=5, pady=5, columnspan=3)
    exchange_combo.current(0)

    tk.Label(root, text="Tokens (comma separated):").grid(row=1, column=0, padx=5, pady=5, sticky="e")
    tokens_entry = tk.Entry(root, width=30)
    tokens_entry.grid(row=1, column=1, padx=5, pady=5, columnspan=3)

    connect_btn = tk.Button(root, text="Connect", command=on_connect, width=12)
    connect_btn.grid(row=2, column=0, padx=5, pady=10)

    disconnect_btn = tk.Button(root, text="Stop & Exit", command=on_closing, width=12)
    disconnect_btn.grid(row=2, column=1, padx=5, pady=10)

    update_btn = tk.Button(root, text="Update Tokens", command=lambda: update_tokens(tokens_entry), width=12)
    update_btn.grid(row=2, column=2, padx=5, pady=10)

    pause_btn = tk.Button(root, text="Pause", command=pause_webstream, width=12)
    pause_btn.grid(row=3, column=0, padx=5, pady=10)

    resume_btn = tk.Button(root, text="Resume", command=lambda: resume_webstream(tokens_entry), width=12)
    resume_btn.grid(row=3, column=1, padx=5, pady=10)

    # --- Graceful Shutdown Handling ---
    root.protocol("WM_DELETE_WINDOW", on_closing)
    
    try:
        root.mainloop()
    except KeyboardInterrupt:
        print("\nCtrl+C detected, closing application.")
        on_closing()

if __name__ == "__main__":
    gui()
