# live_trader.py (Corrected and Integrated)
import time
import os
import json
from datetime import datetime
import pytz
from tabulate import tabulate
from logzero import logger, logfile

# 1. Import your refactored/corrected classes and the login function
from websocket import ModularIntradayStrategy
from websocket_stream import WebSocketStreamer
from login import login

def main():
    """
    Main function to set up and run the live trading strategy.
    This script authenticates, connects the data stream, and runs the strategy.
    """
    # Setup logging to a file
    logfile("live_trader.log", maxBytes=1e6, backupCount=3)
    logger.info("--- Live Trading Bot Initializing ---")

    # --- 1. AUTHENTICATION & CONFIGURATION ---
    logger.info("Performing login to get session tokens...")
    try:
        # The login() function handles authentication and returns necessary objects
        smart_api, auth_token, _ = login()
        if not smart_api or not auth_token:
            logger.error("Authentication failed. Exiting.")
            return

        # Retrieve the feed_token and client_id required for the WebSocket
        feed_token = smart_api.getfeedToken()
        
        # The client_id is often stored by the login function, let's retrieve it
        # Note: This path should be adjusted if your login script saves it elsewhere
        client_id = smart_api.client_code

        if not feed_token or not client_id:
            logger.error(f"Failed to get feed_token or client_id. Exiting.")
            return
            
        api_key = smart_api.api_key
        logger.info("Login successful. Tokens retrieved.")

    except Exception as e:
        logger.error(f"An error occurred during the login process: {e}")
        return

    # Instrument configuration
    # IMPORTANT: Replace with the actual token for your instrument (e.g., NIFTY BANK index token is '26009')
    INSTRUMENT_TO_TRADE = ["26009"] 

    # --- 2. STRATEGY SETUP ---
    # Create an instance of your trading strategy from 4websocket.py
    # You can override default strategy parameters here if you wish.
    strategy_params = {
        'initial_capital': 200000,
        'base_sl_points': 20,
        'tp1_points': 30,
        'tp2_points': 60,
    }
    strategy = ModularIntradayStrategy(params=strategy_params)
    logger.info("Strategy instance created with custom parameters.")

    # --- 3. LINK STRATEGY AND DATA STREAM ---
    # This is the critical connection. We pass the live tokens and the strategy's
    # on_tick method as the callback function.
    logger.info("Setting up WebSocket data streamer...")
    streamer = WebSocketStreamer(
        api_key=api_key,
        client_id=client_id,
        auth_token=auth_token,
        feed_token=feed_token,
        instrument_keys=INSTRUMENT_TO_TRADE,
        on_tick_callback=strategy.on_tick  # <-- THE CRITICAL LINK
    )

    # --- 4. RUN THE BOT ---
    streamer.connect() # Starts the connection in a background thread
    print("\n*** Bot is now live and listening for ticks. Press CTRL+C to stop. ***\n")

    try:
        # This loop keeps the main program alive while the WebSocket thread runs.
        while streamer.is_running:
            time.sleep(15) # Check status every 15 seconds
            if strategy.position_size > 0:
                status_msg = (
                    f"STATUS: In Position | Size={strategy.position_size:.2f}, "
                    f"Entry={strategy.position_entry_price:.2f}, "
                    f"Current SL={strategy.get_effective_stop_price():.2f}"
                )
                logger.info(status_msg)
            else:
                logger.info("STATUS: Awaiting signal...")
        
        # If the loop exits, it means the websocket disconnected.
        logger.warning("WebSocket connection lost. Shutting down.")

    except KeyboardInterrupt:
        logger.info("\n--- Shutdown signal received (CTRL+C) ---")
    finally:
        # --- 5. CLEANUP AND FINAL REPORT ---
        logger.info("Stopping data stream...")
        streamer.stop() # Gracefully close the WebSocket connection
        
        logger.info("--- Generating Final Trade Report ---")
        results = strategy.generate_results()

        if "error" in results:
            logger.error(f"Could not generate report: {results['error']}")
        else:
            # Print summary to console
            print("\n--- Performance Summary ---")
            summary = {
                "Total Return": f"{results['total_return']:.2f}%",
                "Final Equity": f"₹{results['final_equity']:,.2f}",
                "Total PnL": f"₹{results['total_pnl']:,.2f}",
                "Total Trades": results['total_trades'],
                "Win Rate": f"{results['win_rate']:.2f}%",
                "Profit Factor": f"{results['profit_factor']:.2f}",
                "Max Drawdown": f"{results['max_drawdown']:.2f}%"
            }
            for key, value in summary.items():
                print(f"{key:<20}: {value}")

            if not results['trades_df'].empty:
                print("\n--- All Trades ---")
                print(tabulate(results['trades_df'], headers='keys', tablefmt='psql'))
        
        logger.info("--- Bot has been shut down gracefully. ---")


if __name__ == "__main__":
    main()
