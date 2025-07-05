import tkinter as tk
from tkinter import ttk, messagebox
import threading
import requests
import json
import os
from datetime import datetime, timedelta

# Import the refactored bot class and the strategy class to get defaults
from .live_trader import LiveTradingBot
from .strategy import ModularIntradayStrategy

class LiveTraderGUI:
    """
    A GUI for configuring and launching the ModularIntradayStrategy for live trading.
    """
    def __init__(self, root):
        self.root = root
        self.root.title("Live Trader Launcher v2")
        self.bot_thread = None
        self.bot_instance = None

        # Get default parameters from the strategy class itself
        default_strategy = ModularIntradayStrategy()

        # Cache file path for symbol-token mapping
        self.cache_file = "smartapi/symbol_cache.json"

        # Load symbol-token mapping from cache or online
        self.symbol_token_map = self._load_symbol_token_map()
        self.symbols_list = sorted(self.symbol_token_map.keys()) if self.symbol_token_map else []

        # --- GUI Variables ---
        self.instrument_token = tk.StringVar(value="26000") # Default to NIFTY 50
        self.symbol_var = tk.StringVar()
        self.exchange_type = tk.StringVar(value="NSE_CM")
        self.feed_type = tk.StringVar(value="Quote") # Default to Quote for VWAP
        self.log_ticks = tk.BooleanVar(value=False) # Default to not logging ticks

        # Indicator toggles
        self.use_supertrend = tk.BooleanVar(value=default_strategy.use_supertrend)
        self.use_ema_crossover = tk.BooleanVar(value=default_strategy.use_ema_crossover)
        self.use_rsi_filter = tk.BooleanVar(value=default_strategy.use_rsi_filter)
        self.use_vwap = tk.BooleanVar(value=default_strategy.use_vwap)

        # Indicator parameters
        self.atr_len = tk.IntVar(value=default_strategy.atr_len)
        self.atr_mult = tk.DoubleVar(value=default_strategy.atr_mult)
        self.fast_ema = tk.IntVar(value=default_strategy.fast_ema)
        self.slow_ema = tk.IntVar(value=default_strategy.slow_ema)
        self.rsi_length = tk.IntVar(value=default_strategy.rsi_length)
        self.rsi_overbought = tk.IntVar(value=default_strategy.rsi_overbought)
        self.rsi_oversold = tk.IntVar(value=default_strategy.rsi_oversold)

        # Stop loss and targets
        self.base_sl_points = tk.IntVar(value=default_strategy.base_sl_points)
        self.tp1_points = tk.IntVar(value=default_strategy.tp1_points)
        self.tp2_points = tk.IntVar(value=default_strategy.tp2_points)
        self.tp3_points = tk.IntVar(value=default_strategy.tp3_points)
        
        # Trail Stop
        self.use_trail_stop = tk.BooleanVar(value=default_strategy.use_trail_stop)
        self.trail_activation_points = tk.IntVar(value=default_strategy.trail_activation_points)
        self.trail_distance_points = tk.IntVar(value=default_strategy.trail_distance_points)

        # Other parameters
        self.initial_capital = tk.IntVar(value=default_strategy.initial_capital)
        self.risk_per_trade_percent = tk.DoubleVar(value=default_strategy.risk_per_trade_percent)
        self.exit_before_close = tk.IntVar(value=default_strategy.exit_before_close)

        self.create_widgets()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _load_symbol_token_map(self):
        """Load symbol-token mapping from cache or online JSON file."""
        # Check if cache exists
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r') as f:
                    cache_data = json.load(f)
                    symbol_token_map = cache_data.get('symbols', {})
                    print(f"Loaded {len(symbol_token_map)} symbols from cache")
                    return symbol_token_map
            except Exception as e:
                print(f"Error reading cache: {e}")
        
        # Cache doesn't exist, fetch from online
        return self._fetch_and_cache_symbols()

    def _fetch_and_cache_symbols(self):
        """Fetch symbols from online and save to cache."""
        try:
            url = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
            print("Fetching symbols from online source...")
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            
            # Parse the JSON data
            data = response.json()
            symbol_token_map = {}
            
            for item in data:
                symbol = item.get('symbol', '')
                token = item.get('token', '')
                if symbol and token:
                    symbol_token_map[symbol] = token
            
            # Save to cache
            self._save_cache(symbol_token_map)
            
            print(f"Loaded {len(symbol_token_map)} symbols from online source and cached")
            return symbol_token_map
            
        except Exception as e:
            print(f"Error fetching symbols: {e}")
            messagebox.showwarning("Warning", f"Could not load symbol list from online source: {e}\nYou can still manually enter the token.")
            return {}

    def _save_cache(self, symbol_token_map):
        """Save symbol-token mapping to cache file."""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
            
            cache_data = {
                'timestamp': datetime.now().isoformat(),
                'symbols': symbol_token_map
            }
            
            with open(self.cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)
                
        except Exception as e:
            print(f"Error saving cache: {e}")

    def refresh_symbol_cache(self):
        """Manually refresh the symbol cache from online source."""
        print("Manually refreshing symbol cache...")
        self.symbol_token_map = self._fetch_and_cache_symbols()
        self.symbols_list = sorted(self.symbol_token_map.keys()) if self.symbol_token_map else []
        
        # Update the combobox values
        if hasattr(self, 'symbol_combo'):
            self.symbol_combo['values'] = self.symbols_list
        
        messagebox.showinfo("Cache Refresh", f"Symbol cache refreshed. Loaded {len(self.symbol_token_map)} symbols.")

    def _on_symbol_select(self, event=None):
        """When a symbol is selected from dropdown, update the token field."""
        selected_symbol = self.symbol_var.get()
        if selected_symbol in self.symbol_token_map:
            token = self.symbol_token_map[selected_symbol]
            self.instrument_token.set(token)
            print(f"Selected symbol: {selected_symbol}, Token: {token}")

    def _filter_symbols(self, event=None):
        """Filter symbols based on user input for autocomplete."""
        current_text = self.symbol_var.get().upper()
        if current_text:
            filtered_symbols = [s for s in self.symbols_list if current_text in s.upper()]
            self.symbol_combo['values'] = filtered_symbols
        else:
            self.symbol_combo['values'] = self.symbols_list

    def create_widgets(self):
        notebook = ttk.Notebook(self.root)
        notebook.pack(pady=10, padx=10, fill="both", expand=True)

        f_main = ttk.Frame(notebook, padding="10")
        f_indicators = ttk.Frame(notebook, padding="10")
        f_risk = ttk.Frame(notebook, padding="10")

        notebook.add(f_main, text='Main Settings')
        notebook.add(f_indicators, text='Indicators')
        notebook.add(f_risk, text='Risk & TP/SL')

        # --- Main Settings Frame ---
        ttk.Label(f_main, text="Symbol:", font=('Helvetica', 10, 'bold')).grid(row=0, column=0, sticky="w", pady=5)
        self.symbol_combo = ttk.Combobox(f_main, textvariable=self.symbol_var, values=self.symbols_list, width=20)
        self.symbol_combo.grid(row=0, column=1, sticky="w", padx=(0, 5))
        self.symbol_combo.bind('<KeyRelease>', self._filter_symbols)
        self.symbol_combo.bind('<<ComboboxSelected>>', self._on_symbol_select)
        
        # Add refresh cache button
        ttk.Button(f_main, text="🔄 Refresh", command=self.refresh_symbol_cache, width=10).grid(row=0, column=2, sticky="w", padx=(0, 10))

        ttk.Label(f_main, text="Instrument Token:", font=('Helvetica', 10, 'bold')).grid(row=1, column=0, sticky="w", pady=5)
        ttk.Entry(f_main, textvariable=self.instrument_token, width=15).grid(row=1, column=1, sticky="w")

        ttk.Label(f_main, text="Exchange:", font=('Helvetica', 10, 'bold')).grid(row=2, column=0, sticky="w", pady=5)
        exchange_map = {"NSE_CM": 1, "NSE_FO": 2, "BSE_CM": 3, "BSE_FO": 4, "MCX_FO": 5, "NCDEX_FO": 7}
        self.exchange_combo = ttk.Combobox(f_main, textvariable=self.exchange_type, values=list(exchange_map.keys()), width=12)
        self.exchange_combo.grid(row=2, column=1, sticky="w")
        
        ttk.Label(f_main, text="Feed Type:", font=('Helvetica', 10, 'bold')).grid(row=3, column=0, sticky="w", pady=5)
        feed_map = {"LTP": 1, "Quote": 2, "SnapQuote": 3}
        self.feed_combo = ttk.Combobox(f_main, textvariable=self.feed_type, values=list(feed_map.keys()), width=12)
        self.feed_combo.grid(row=3, column=1, sticky="w")

        ttk.Label(f_main, text="Initial Capital:").grid(row=4, column=0, sticky="w", pady=2)
        ttk.Entry(f_main, textvariable=self.initial_capital, width=15).grid(row=4, column=1, sticky="w")

        ttk.Label(f_main, text="Exit Before Close (min):").grid(row=5, column=0, sticky="w", pady=2)
        ttk.Entry(f_main, textvariable=self.exit_before_close, width=15).grid(row=5, column=1, sticky="w")

        ttk.Checkbutton(f_main, text="Log Live Ticks to Console", variable=self.log_ticks).grid(row=6, column=0, columnspan=2, sticky="w", pady=10)

        # --- Indicator Frame ---
        ttk.Checkbutton(f_indicators, text="Use Supertrend", variable=self.use_supertrend).grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(f_indicators, text="Use EMA Crossover", variable=self.use_ema_crossover).grid(row=1, column=0, sticky="w")
        ttk.Checkbutton(f_indicators, text="Use RSI Filter", variable=self.use_rsi_filter).grid(row=2, column=0, sticky="w")
        ttk.Checkbutton(f_indicators, text="Use VWAP", variable=self.use_vwap).grid(row=3, column=0, sticky="w")
        
        ttk.Label(f_indicators, text="ATR Len:").grid(row=0, column=2, sticky="e", padx=5); ttk.Entry(f_indicators, textvariable=self.atr_len, width=8).grid(row=0, column=3, sticky="w")
        ttk.Label(f_indicators, text="ATR Mult:").grid(row=0, column=4, sticky="e", padx=5); ttk.Entry(f_indicators, textvariable=self.atr_mult, width=8).grid(row=0, column=5, sticky="w")
        
        ttk.Label(f_indicators, text="Fast EMA:").grid(row=1, column=2, sticky="e", padx=5); ttk.Entry(f_indicators, textvariable=self.fast_ema, width=8).grid(row=1, column=3, sticky="w")
        ttk.Label(f_indicators, text="Slow EMA:").grid(row=1, column=4, sticky="e", padx=5); ttk.Entry(f_indicators, textvariable=self.slow_ema, width=8).grid(row=1, column=5, sticky="w")

        ttk.Label(f_indicators, text="RSI Len:").grid(row=2, column=2, sticky="e", padx=5); ttk.Entry(f_indicators, textvariable=self.rsi_length, width=8).grid(row=2, column=3, sticky="w")
        ttk.Label(f_indicators, text="RSI High:").grid(row=2, column=4, sticky="e", padx=5); ttk.Entry(f_indicators, textvariable=self.rsi_overbought, width=8).grid(row=2, column=5, sticky="w")
        ttk.Label(f_indicators, text="RSI Low:").grid(row=2, column=6, sticky="e", padx=5); ttk.Entry(f_indicators, textvariable=self.rsi_oversold, width=8).grid(row=2, column=7, sticky="w")

        # --- Risk & TP/SL Frame ---
        ttk.Label(f_risk, text="Risk Per Trade (%):").grid(row=0, column=0, sticky="w", pady=2)
        ttk.Entry(f_risk, textvariable=self.risk_per_trade_percent, width=10).grid(row=0, column=1, sticky="w")
        
        ttk.Label(f_risk, text="Base SL (Points):").grid(row=1, column=0, sticky="w", pady=2)
        ttk.Entry(f_risk, textvariable=self.base_sl_points, width=10).grid(row=1, column=1, sticky="w")

        ttk.Label(f_risk, text="TP1 (Points):").grid(row=2, column=0, sticky="w", pady=2); ttk.Entry(f_risk, textvariable=self.tp1_points, width=10).grid(row=2, column=1, sticky="w")
        ttk.Label(f_risk, text="TP2 (Points):").grid(row=3, column=0, sticky="w", pady=2); ttk.Entry(f_risk, textvariable=self.tp2_points, width=10).grid(row=3, column=1, sticky="w")
        ttk.Label(f_risk, text="TP3 (Points):").grid(row=4, column=0, sticky="w", pady=2); ttk.Entry(f_risk, textvariable=self.tp3_points, width=10).grid(row=4, column=1, sticky="w")

        ttk.Separator(f_risk, orient='horizontal').grid(row=5, column=0, columnspan=4, sticky='ew', pady=10)

        ttk.Checkbutton(f_risk, text="Use Trailing Stop", variable=self.use_trail_stop).grid(row=6, column=0, sticky="w")
        ttk.Label(f_risk, text="Trail Activation (Pts):").grid(row=7, column=0, sticky="w", pady=2); ttk.Entry(f_risk, textvariable=self.trail_activation_points, width=10).grid(row=7, column=1, sticky="w")
        ttk.Label(f_risk, text="Trail Distance (Pts):").grid(row=8, column=0, sticky="w", pady=2); ttk.Entry(f_risk, textvariable=self.trail_distance_points, width=10).grid(row=8, column=1, sticky="w")

        # --- Action Buttons ---
        button_frame = ttk.Frame(self.root)
        button_frame.pack(pady=10)
        self.start_button = ttk.Button(button_frame, text="Start Live Trading", command=self.start_trading)
        self.start_button.pack(side="left", padx=5)

        self.pause_button = ttk.Button(button_frame, text="Pause Stream", command=self.pause_stream, state="disabled")
        self.pause_button.pack(side="left", padx=5)

        self.resume_button = ttk.Button(button_frame, text="Resume Stream", command=self.resume_stream, state="disabled")
        self.resume_button.pack(side="left", padx=5)

        self.stop_button = ttk.Button(button_frame, text="Stop Trading", command=self.stop_trading, state="disabled")
        self.stop_button.pack(side="left", padx=5)

    def get_params_from_gui(self):
        """Collects all parameters from the GUI fields into a dictionary."""
        return {
            "use_supertrend": self.use_supertrend.get(), "use_ema_crossover": self.use_ema_crossover.get(),
            "use_rsi_filter": self.use_rsi_filter.get(), "use_vwap": self.use_vwap.get(),
            "atr_len": self.atr_len.get(), "atr_mult": self.atr_mult.get(),
            "fast_ema": self.fast_ema.get(), "slow_ema": self.slow_ema.get(),
            "rsi_length": self.rsi_length.get(), "rsi_overbought": self.rsi_overbought.get(),
            "rsi_oversold": self.rsi_oversold.get(), "base_sl_points": self.base_sl_points.get(),
            "tp1_points": self.tp1_points.get(), "tp2_points": self.tp2_points.get(),
            "tp3_points": self.tp3_points.get(), "use_trail_stop": self.use_trail_stop.get(),
            "trail_activation_points": self.trail_activation_points.get(),
            "trail_distance_points": self.trail_distance_points.get(),
            "initial_capital": self.initial_capital.get(),
            "risk_per_trade_percent": self.risk_per_trade_percent.get(),
            "exit_before_close": self.exit_before_close.get(),
        }

    def start_trading(self):
        """Starts the live trading bot in a new thread."""
        instrument = self.instrument_token.get()
        if not instrument.isdigit():
            messagebox.showerror("Error", "Instrument Token must be a number.")
            return

        exchange_map = {"NSE_CM": 1, "NSE_FO": 2, "BSE_CM": 3, "BSE_FO": 4, "MCX_FO": 5, "NCDEX_FO": 7}
        exchange_type_val = exchange_map.get(self.exchange_type.get(), 1)
        
        feed_map = {"LTP": 1, "Quote": 2, "SnapQuote": 3}
        feed_type_val = feed_map.get(self.feed_type.get(), 2) # Default to Quote
        log_ticks_val = self.log_ticks.get()

        params = self.get_params_from_gui()
        
        # Get the selected symbol for status display
        selected_symbol = self.symbol_var.get()
        
        self.bot_instance = LiveTradingBot(
            instrument_token=instrument,
            strategy_params=params,
            exchange_type=exchange_type_val,
            feed_mode=feed_type_val,
            log_ticks=log_ticks_val,
            symbol=selected_symbol  # Pass the symbol to the bot
        )
        self.bot_thread = threading.Thread(target=self.bot_instance.run, daemon=True)
        self.bot_thread.start()

        self.start_button.config(state="disabled")
        self.stop_button.config(state="normal")
        self.pause_button.config(state="normal")
        self.resume_button.config(state="disabled")
        messagebox.showinfo("Status", "Live trading bot has been started!\nCheck the console and log file for details.")

    def stop_trading(self):
        """Stops the running trading bot."""
        if self.bot_instance:
            self.bot_instance.stop(is_manual_stop=True)
            if self.bot_thread and self.bot_thread.is_alive():
                self.bot_thread.join(timeout=5)
        
        self.start_button.config(state="normal")
        self.stop_button.config(state="disabled")
        self.pause_button.config(state="disabled")
        self.resume_button.config(state="disabled")
        messagebox.showinfo("Status", "Live trading bot has been stopped.")

    def pause_stream(self):
        """Pauses the data stream."""
        if self.bot_instance:
            self.bot_instance.pause_stream()
            self.pause_button.config(state="disabled")
            self.resume_button.config(state="normal")
            messagebox.showinfo("Status", "Data stream paused.")

    def resume_stream(self):
        """Resumes the data stream."""
        if self.bot_instance:
            self.bot_instance.resume_stream()
            self.pause_button.config(state="normal")
            self.resume_button.config(state="disabled")
            messagebox.showinfo("Status", "Data stream resumed.")

    def on_closing(self):
        """Handles the event of closing the GUI window."""
        if self.bot_thread and self.bot_thread.is_alive():
            if messagebox.askyesno("Confirm", "Trading bot is running. Are you sure you want to exit?"):
                self.stop_trading()
                self.root.destroy()
        else:
            self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = LiveTraderGUI(root)
    root.mainloop()
