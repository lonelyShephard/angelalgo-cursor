# c:\Users\user\projects\angelalgo\smartapi\live_trader.py (With Enhanced Logging)
import time
import os
from tabulate import tabulate
from logzero import logger, logfile

# Import your classes
from strategy import ModularIntradayStrategy
from websocket_stream import WebSocketStreamer

def main():
    """
    Main function to set up and run the live trading strategy.
    """
    logfile("live_trader.log", maxBytes=1e6, backupCount=3)
    logger.info("--- Live Trading Bot Initializing ---")

    # Instrument configuration
    INSTRUMENT_TO_TRADE = ["26000"] 

    # --- 1. STRATEGY SETUP ---
    strategy_params = {
        'initial_capital': 200000,
        'base_sl_points': 20,
        'tp1_points': 30,
        'tp2_points': 60,
    }
    strategy = ModularIntradayStrategy(params=strategy_params)
    logger.info("Strategy instance created with custom parameters.")

    # --- 2. LINK STRATEGY AND DATA STREAM ---
    logger.info("Setting up WebSocket data streamer...")
    streamer = WebSocketStreamer(
        instrument_keys=INSTRUMENT_TO_TRADE,
        on_tick_callback=strategy.on_tick
    )

    # --- 3. RUN THE BOT ---
    streamer.connect() 
    print("\n*** Bot is now live and listening for ticks. Press CTRL+C to stop. ***\n")

    try:
        # This loop keeps the main program alive and provides detailed status updates.
        while streamer.is_running:
            time.sleep(15) # Check status every 15 seconds

            # --- ENHANCED STATUS LOGGING ---
            bars_collected = len(strategy._bar_history_list)
            min_bars_needed = strategy.min_bars_for_signals # Using the new property

            if strategy.position_size > 0:
                # Status when in a position
                status_msg = (
                    f"STATUS: In Position | Size={strategy.position_size}, "
                    f"Entry={strategy.position_entry_price:.2f}, "
                    f"Current SL={strategy.get_effective_stop_price():.2f}"
                )
                logger.info(status_msg)
            elif bars_collected < min_bars_needed:
                # Status during the initial data collection "warm-up" phase
                status_msg = (
                    f"STATUS: Collecting initial bar data... "
                    f"({bars_collected}/{min_bars_needed} bars collected)"
                )
                logger.info(status_msg)
            else:
                # Status when ready and awaiting a signal
                # Get the latest indicator values for logging
                latest_bar = strategy._bar_history_list[-1]
                st_trend = "Bull" if latest_bar.get('supertrend') == 1 else "Bear"
                ema_cross = "Bull" if latest_bar.get('ema_bull') else "Bear"
                rsi_val = f"{latest_bar.get('rsi', 'N/A'):.1f}" if isinstance(latest_bar.get('rsi'), float) else "N/A"
                htf_trend = "Bull" if latest_bar.get('htf_bullish') else "Bear"
                
                status_msg = (
                    f"STATUS: Awaiting signal | Supertrend: {st_trend}, "
                    f"EMA Cross: {ema_cross}, RSI: {rsi_val}, HTF Trend: {htf_trend}"
                )
                logger.info(status_msg)
        
        logger.warning("WebSocket connection lost. Shutting down.")

    except KeyboardInterrupt:
        logger.info("\n--- Shutdown signal received (CTRL+C) ---")
    finally:
        # --- 4. CLEANUP AND FINAL REPORT ---
        logger.info("Stopping data stream...")
        streamer.stop()
        
        logger.info("--- Generating Final Trade Report ---")
        results = strategy.generate_results()

        if "error" in results:
            logger.error(f"Could not generate report: {results['error']}")
        else:
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
