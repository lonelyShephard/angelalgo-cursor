import time
import threading
from tabulate import tabulate
import pandas as pd
import os
# Import your classes
from .log_utils import logger # Import pre-configured logger
from .strategy import ModularIntradayStrategy
from .websocket_stream import WebSocketStreamer

class LiveTradingBot:
    """
    Encapsulates the entire live trading logic.
    Can be instantiated and run from a GUI or a simple script.
    """
    def __init__(self, instrument_token, strategy_params, exchange_type=1, feed_mode=2, log_ticks=False, symbol=None):
        self.instrument_token = instrument_token
        self.strategy_params = strategy_params
        self.exchange_type = exchange_type
        self.feed_mode = feed_mode
        self.log_ticks = log_ticks
        self.symbol = str(symbol) if symbol else f"Token_{instrument_token}"  # Ensure symbol is always a string
        self.strategy = None
        self.streamer = None
        self._stop_event = threading.Event()
        self.tick_data_buffer = [] # Buffer to store live tick data

    def _on_live_tick(self, timestamp, price, volume):
        """Wrapper callback to process live ticks and pass to strategy."""
        self.tick_data_buffer.append({
            'timestamp': timestamp,
            'price': price,
            'volume': volume
        })
        if self.strategy:
            self.strategy.on_tick(timestamp, price, volume)

    def run(self):
        """Sets up and runs the live trading strategy and status monitor."""
        logger.info("--- Live Trading Bot Initializing ---")

        self.strategy = ModularIntradayStrategy(params=self.strategy_params)
        logger.info(f"Strategy instance created with parameters: {self.strategy_params}")

        logger.info("Setting up WebSocket data streamer...")
        self.streamer = WebSocketStreamer(
            instrument_keys=[self.instrument_token],
            on_tick_callback=self._on_live_tick, # Use the wrapper callback
            exchange_type=self.exchange_type,
            feed_mode=self.feed_mode,
            log_ticks=self.log_ticks
        )

        self.streamer.connect()
        print(f"\n*** Bot is now live for token {self.instrument_token}. ***\n")
        print("*** Check live_trader.log for detailed status updates. ***\n")

        try:
            while not self._stop_event.is_set() and self.streamer.is_running:
                self.log_status()
                time.sleep(15) # Log status every 15 seconds

            if not self.streamer.is_running:
                logger.warning("WebSocket connection appears to have been lost.")

        except KeyboardInterrupt:
            logger.info("\n--- Shutdown signal received (CTRL+C) ---")
        finally:
            self.stop(is_manual_stop=True)

    def log_status(self):
        """Logs the current status of the strategy."""
        if not self.strategy:
            return

        # Get bar history from indicator manager
        bar_history = self.strategy.indicator_manager.get_bar_history()
        if not bar_history:
            return

        bars_collected = len(bar_history)
        min_bars_needed = self.strategy.min_bars_for_signals

        if self.strategy.position_size > 0:
            logger.info(f"STATUS: In Position | Symbol={self.symbol}, Size={self.strategy.position_size}, Entry={self.strategy.position_entry_price:.2f}, Current SL={self.strategy.get_effective_stop_price():.2f}")
        elif bars_collected < min_bars_needed:
            status_msg = (
                f"STATUS: Collecting initial bar data... "
                f"({bars_collected}/{min_bars_needed} bars collected) | Symbol={self.symbol}"
            )
            print(f"DEBUG: bars_collected={bars_collected}, min_bars_needed={min_bars_needed}, symbol={self.symbol!r}")
            try:
                logger.info(status_msg)
            except Exception as e:
                print(f"Logging error: {e}, status_msg={status_msg!r}")
        else:
            latest_bar = bar_history[-1]
            st_trend = "Bull" if latest_bar.get('supertrend') == 1 else "Bear"
            ema_cross = "Bull" if latest_bar.get('ema_bull') else "Bear"
            rsi_val = f"{latest_bar.get('rsi', 'N/A'):.1f}" if isinstance(latest_bar.get('rsi'), float) else "N/A"
            htf_trend = "Bull" if latest_bar.get('htf_bullish') else "Bear"
            
            # Get VWAP status from indicator manager
            vwap_value = self.strategy.indicator_manager.get_indicator_value('vwap')
            current_price = latest_bar.get('close', 0)
            vwap_bull = "Bull" if current_price > vwap_value else "Bear"
            
            status_msg = (
                f"STATUS: Awaiting signal | Symbol={self.symbol}, Supertrend: {st_trend}, EMA: {ema_cross}, "
                f"RSI: {rsi_val}, VWAP: {vwap_bull}, HTF: {htf_trend}"
            )
            logger.info(status_msg)

    def stop(self, is_manual_stop=False):
        """Stops the bot and generates a final report."""
        if self._stop_event.is_set():
            return # Already stopping

        if is_manual_stop:
            logger.info("--- Shutdown signal received ---")
        self._stop_event.set()

        if self.streamer:
            logger.info("Stopping data stream...")
            self.streamer.stop()

        if self.strategy:
            logger.info("--- Generating Final Trade Report ---")
            results = self.strategy.generate_results()

            if "error" in results:
                logger.error(f"Could not generate report: {results['error']}")
            else:
                print("\n--- Performance Summary ---")
                summary = {
                    "Total Return": f"{results['total_return']:.2f}%", "Final Equity": f"₹{results['final_equity']:,.2f}",
                    "Total PnL": f"₹{results['total_pnl']:,.2f}", "Total Trades": results['total_trades'],
                    "Win Rate": f"{results['win_rate']:.2f}%", "Profit Factor": f"{results['profit_factor']:.2f}",
                    "Max Drawdown": f"{results['max_drawdown']:.2f}%"
                }
                for key, value in summary.items():
                    print(f"{key:<20}: {value}")

                trades_df = results.get('trades_df')
                if trades_df is not None and isinstance(trades_df, pd.DataFrame) and not trades_df.empty:
                    print("\n--- All Trades ---")
                    print(tabulate(trades_df, headers='keys', tablefmt='psql'))
        if self.tick_data_buffer:
            try:
                # Construct the path to the 'data' folder within the 'smartapi' directory
                script_dir = os.path.dirname(__file__)
                data_folder_path = os.path.join(script_dir, "data")
                os.makedirs(data_folder_path, exist_ok=True) # Create the directory if it doesn't exist

                df_ticks = pd.DataFrame(self.tick_data_buffer)
                csv_filename = os.path.join(data_folder_path, f"live_ticks_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv")
                df_ticks.to_csv(csv_filename, index=False)
                logger.info(f"Raw tick data saved to {csv_filename}")
            except Exception as e:
                logger.error(f"Failed to save raw tick data to CSV: {e}")
        logger.info("--- Bot has been shut down gracefully. ---")

    def pause_stream(self):
        """Pauses the WebSocket data stream."""
        if self.streamer and self.streamer.is_running:
            logger.info("GUI requested stream pause.")
            self.streamer.pause_stream()

    def resume_stream(self):
        """Resumes the WebSocket data stream."""
        if self.streamer and self.streamer.is_running:
            logger.info("GUI requested stream resume.")
            self.streamer.resume_stream()


if __name__ == "__main__":
    # This block allows for direct execution for testing without the GUI.
    instrument_token = "26000" # NIFTY 50 Index
    exchange_type = 1  # 1 for NSE_CM
    feed_mode = 2      # Use Quote mode for VWAP calculation
    strategy_params = {
        'initial_capital': 200000, 'base_sl_points': 20, 'tp1_points': 30, 'tp2_points': 60,
        'use_vwap': True, 'use_supertrend': True, 'use_ema_crossover': True, 'use_rsi_filter': True
    }
    bot = LiveTradingBot(
        instrument_token=instrument_token, strategy_params=strategy_params, 
        exchange_type=exchange_type, feed_mode=feed_mode,
        log_ticks=True # Set to True for direct script execution testing
    )
    bot.run()
