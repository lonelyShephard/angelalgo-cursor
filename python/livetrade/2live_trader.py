import time
import threading
from tabulate import tabulate
from logzero import logger, logfile

# Import your classes
from strategy import ModularIntradayStrategy
from websocket_stream import WebSocketStreamer

class LiveTradingBot:
    """
    Encapsulates the entire live trading logic.
    Can be instantiated and run from a GUI or a simple script.
    """
    def __init__(self, instrument_token, strategy_params):
        self.instrument_token = instrument_token
        self.strategy_params = strategy_params
        self.strategy = None
        self.streamer = None
        self._stop_event = threading.Event()

    def run(self):
        """Sets up and runs the live trading strategy and status monitor."""
        logfile("live_trader.log", maxBytes=1e6, backupCount=3)
        logger.info("--- Live Trading Bot Initializing ---")

        self.strategy = ModularIntradayStrategy(params=self.strategy_params)
        logger.info(f"Strategy instance created with parameters: {self.strategy_params}")

        logger.info("Setting up WebSocket data streamer...")
        self.streamer = WebSocketStreamer(
            instrument_keys=[self.instrument_token],
            on_tick_callback=self.strategy.on_tick
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
        if not self.strategy or not self.strategy._bar_history_list:
            return

        bars_collected = len(self.strategy._bar_history_list)
        min_bars_needed = self.strategy.min_bars_for_signals

        if self.strategy.position_size > 0:
            status_msg = (
                f"STATUS: In Position | Size={self.strategy.position_size}, "
                f"Entry={self.strategy.position_entry_price:.2f}, "
                f"Current SL={self.strategy.get_effective_stop_price():.2f}"
            )
            logger.info(status_msg)
        elif bars_collected < min_bars_needed:
            status_msg = (
                f"STATUS: Collecting initial bar data... "
                f"({bars_collected}/{min_bars_needed} bars collected)"
            )
            logger.info(status_msg)
        else:
            latest_bar = self.strategy._bar_history_list[-1]
            st_trend = "Bull" if latest_bar.get('supertrend') == 1 else "Bear"
            ema_cross = "Bull" if latest_bar.get('ema_bull') else "Bear"
            rsi_val = f"{latest_bar.get('rsi', 'N/A'):.1f}" if isinstance(latest_bar.get('rsi'), float) else "N/A"
            htf_trend = "Bull" if latest_bar.get('htf_bullish') else "Bear"
            vwap_bull = "Bull" if self.strategy.current_vwap_bull else "Bear"
            
            status_msg = (
                f"STATUS: Awaiting signal | Supertrend: {st_trend}, EMA: {ema_cross}, "
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

                if not results['trades_df'].empty:
                    print("\n--- All Trades ---")
                    print(tabulate(results['trades_df'], headers='keys', tablefmt='psql'))
        
        logger.info("--- Bot has been shut down gracefully. ---")

if __name__ == "__main__":
    # This block allows for direct execution for testing without the GUI.
    instrument_token = "26000" # NIFTY 50 Index
    strategy_params = {
        'initial_capital': 200000, 'base_sl_points': 20, 'tp1_points': 30, 'tp2_points': 60,
        'use_vwap': True, 'use_supertrend': True, 'use_ema_crossover': True, 'use_rsi_filter': True
    }
    bot = LiveTradingBot(instrument_token, strategy_params)
    bot.run()
