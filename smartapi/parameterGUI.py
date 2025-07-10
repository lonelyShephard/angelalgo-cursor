import tkinter as tk
from tkinter import ttk, messagebox
from tabulate import tabulate
from datetime import datetime
import pandas as pd
import os

class StrategyParameterGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Strategy Parameters")

        # Indicator toggles
        self.use_supertrend = tk.BooleanVar(value=True)
        self.use_ema_crossover = tk.BooleanVar(value=True)
        self.use_rsi_filter = tk.BooleanVar(value=True)
        self.use_vwap = tk.BooleanVar(value=False)

        # Indicator parameters
        self.atr_len = tk.IntVar(value=10)
        self.atr_mult = tk.DoubleVar(value=3.0)
        self.fast_ema = tk.IntVar(value=9)
        self.slow_ema = tk.IntVar(value=21)
        self.rsi_length = tk.IntVar(value=14)
        self.rsi_overbought = tk.IntVar(value=70)
        self.rsi_oversold = tk.IntVar(value=30)

        # Stop loss and targets
        self.base_sl_points = tk.IntVar(value=15)
        self.tp1_points = tk.IntVar(value=25)
        self.tp2_points = tk.IntVar(value=45)
        self.tp3_points = tk.IntVar(value=100)

        # Other parameters
        self.initial_capital = tk.IntVar(value=100000)
        self.exit_before_close = tk.IntVar(value=20)

        # Data file selection
        self.data_file = tk.StringVar()
        self.data_files = self.load_data_files()

        row = 0

        # Data file selection
        ttk.Label(root, text="Data File:").grid(row=row, column=0, sticky="e")
        self.data_file_dropdown = ttk.Combobox(root, textvariable=self.data_file, values=self.data_files, width=30)
        self.data_file_dropdown.grid(row=row, column=1)
        if self.data_files:
            self.data_file.set(self.data_files[0])  # Set default value if files are available
        self.data_file_dropdown.bind("<KeyRelease>", self.autocomplete)  # Bind autocomplete
        row += 1
        
        # Add option to use price_ticks.log
        ttk.Label(root, text="Or use price_ticks.log:").grid(row=row, column=0, sticky="e")
        self.use_ticks_log = tk.BooleanVar(value=False)
        ttk.Checkbutton(root, text="Use price_ticks.log instead", variable=self.use_ticks_log).grid(row=row, column=1, sticky="w")
        row += 1

        # Indicator toggles
        ttk.Label(root, text="Indicators:").grid(row=row, column=0, sticky="w")
        row += 1
        ttk.Checkbutton(root, text="Supertrend", variable=self.use_supertrend).grid(row=row, column=0, sticky="w")
        row += 1
        ttk.Checkbutton(root, text="EMA Crossover", variable=self.use_ema_crossover).grid(row=row, column=0, sticky="w")
        row += 1
        ttk.Checkbutton(root, text="RSI Filter", variable=self.use_rsi_filter).grid(row=row, column=0, sticky="w")
        row += 1
        ttk.Checkbutton(root, text="VWAP", variable=self.use_vwap).grid(row=row, column=0, sticky="w")
        row += 1

        # Indicator parameters
        ttk.Label(root, text="Supertrend ATR Length:").grid(row=row, column=0, sticky="e")
        ttk.Entry(root, textvariable=self.atr_len, width=6).grid(row=row, column=1)
        row += 1
        ttk.Label(root, text="Supertrend Multiplier:").grid(row=row, column=0, sticky="e")
        ttk.Entry(root, textvariable=self.atr_mult, width=6).grid(row=row, column=1)
        row += 1
        ttk.Label(root, text="Fast EMA:").grid(row=row, column=0, sticky="e")
        ttk.Entry(root, textvariable=self.fast_ema, width=6).grid(row=row, column=1)
        row += 1
        ttk.Label(root, text="Slow EMA:").grid(row=row, column=0, sticky="e")
        ttk.Entry(root, textvariable=self.slow_ema, width=6).grid(row=row, column=1)
        row += 1
        ttk.Label(root, text="RSI Length:").grid(row=row, column=0, sticky="e")
        ttk.Entry(root, textvariable=self.rsi_length, width=6).grid(row=row, column=1)
        row += 1
        ttk.Label(root, text="RSI Overbought:").grid(row=row, column=0, sticky="e")
        ttk.Entry(root, textvariable=self.rsi_overbought, width=6).grid(row=row, column=1)
        row += 1
        ttk.Label(root, text="RSI Oversold:").grid(row=row, column=0, sticky="e")
        ttk.Entry(root, textvariable=self.rsi_oversold, width=6).grid(row=row, column=1)
        row += 1

        # Stop loss and targets
        ttk.Label(root, text="Stop Loss Points:").grid(row=row, column=0, sticky="e")
        ttk.Entry(root, textvariable=self.base_sl_points, width=6).grid(row=row, column=1)
        row += 1
        ttk.Label(root, text="TP1 Points:").grid(row=row, column=0, sticky="e")
        ttk.Entry(root, textvariable=self.tp1_points, width=6).grid(row=row, column=1)
        row += 1
        ttk.Label(root, text="TP2 Points:").grid(row=row, column=0, sticky="e")
        ttk.Entry(root, textvariable=self.tp2_points, width=6).grid(row=row, column=1)
        row += 1
        ttk.Label(root, text="TP3 Points:").grid(row=row, column=0, sticky="e")
        ttk.Entry(root, textvariable=self.tp3_points, width=6).grid(row=row, column=1)
        row += 1

        # Other parameters
        ttk.Label(root, text="Initial Capital:").grid(row=row, column=0, sticky="e")
        ttk.Entry(root, textvariable=self.initial_capital, width=10).grid(row=row, column=1)
        row += 1
        ttk.Label(root, text="Exit Before Close (min):").grid(row=row, column=0, sticky="e")
        ttk.Entry(root, textvariable=self.exit_before_close, width=6).grid(row=row, column=1)
        row += 1

        ttk.Button(root, text="Run Backtest", command=self.run_backtest).grid(row=row, column=0, columnspan=2, pady=10)

    def load_data_files(self):
        data_dir = os.path.join(os.path.dirname(__file__), "data")
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
            return []  # Return empty list if the directory doesn't exist

        files = [f for f in os.listdir(data_dir) if f.endswith(".csv")]
        return files

    def autocomplete(self, event):
        """Enables autocomplete for the file selection dropdown."""
        value = self.data_file.get().lower()
        if value == "":
            self.data_file_dropdown['values'] = self.data_files
        else:
            new_values = [f for f in self.data_files if value in f.lower()]
            self.data_file_dropdown['values'] = new_values

    def run_backtest(self):
        from backtest import run_backtest_from_file

        params = {
            "use_supertrend": self.use_supertrend.get(),
            "use_ema_crossover": self.use_ema_crossover.get(),
            "use_rsi_filter": self.use_rsi_filter.get(),
            "use_vwap": self.use_vwap.get(),
            "atr_len": self.atr_len.get(),
            "atr_mult": self.atr_mult.get(),
            "fast_ema": self.fast_ema.get(),
            "slow_ema": self.slow_ema.get(),
            "rsi_length": self.rsi_length.get(),
            "rsi_overbought": self.rsi_overbought.get(),
            "rsi_oversold": self.rsi_oversold.get(),
            "base_sl_points": self.base_sl_points.get(),
            "tp1_points": self.tp1_points.get(),
            "tp2_points": self.tp2_points.get(),
            "tp3_points": self.tp3_points.get(),
            "initial_capital": self.initial_capital.get(),
            "exit_before_close": self.exit_before_close.get(),
        }

        # Check if user wants to use price_ticks.log
        if self.use_ticks_log.get():
            ticks_log_path = os.path.join(os.path.dirname(__file__), "price_ticks.log")
            if not os.path.exists(ticks_log_path):
                messagebox.showerror("Error", "price_ticks.log not found in smartapi directory.")
                return
            
            try:
                # Run backtest using price_ticks.log
                results, saved_files = run_backtest_from_file(ticks_log_path, params, 'ticks')
            except Exception as e:
                messagebox.showerror("Error", f"Error running backtest on price_ticks.log: {e}")
                return
        else:
            # Use selected CSV file
            selected_file = self.data_file.get()
            if not selected_file:
                messagebox.showerror("Error", "Please select a data file or check 'Use price_ticks.log'.")
                return

            # Determine file path and type
            csv_path = os.path.join(os.path.dirname(__file__), "data", selected_file)
            
            # Check if file exists
            if not os.path.exists(csv_path):
                messagebox.showerror("Error", f"File not found: {selected_file}")
                return

            try:
                # Run backtest using the new engine
                results, saved_files = run_backtest_from_file(csv_path, params, 'csv')
            except Exception as e:
                messagebox.showerror("Error", f"Error running backtest: {e}")
                return

        # Show results
        if "error" not in results:
            # --- Prepare directory for saving results ---
            script_dir = os.path.dirname(__file__)
            results_dir = os.path.join(script_dir, "results")
            os.makedirs(results_dir, exist_ok=True) # Create 'results' folder if it doesn't exist

            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # 1. Save the detailed trades log
            trades_df = results['trades_df']
            if isinstance(trades_df, pd.DataFrame) and not trades_df.empty:
                trades_filename = os.path.join(results_dir, f"trades_{timestamp_str}.csv")
                trades_df.to_csv(trades_filename, index=False)
                print(f"\n[SUCCESS] Detailed trades saved to: {trades_filename}")

            # 2. Save the summary statistics
            stats = [
                ["Total Trades", results['total_trades']],
                ["Win Rate (%)", f"{results['win_rate']:.2f}"],
                ["Total P&L", f"{results['total_pnl']:.2f}"],
                ["Total Return (%)", f"{results['total_return']:.2f}"],
                ["Max Drawdown (%)", f"{results['max_drawdown']:.2f}"],
                ["Profit Factor", f"{results['profit_factor']:.2f}"],
                ["Avg Win", f"{results['avg_win']:.2f}"],
                ["Avg Loss", f"{results['avg_loss']:.2f}"],
            ]
            summary_filename = os.path.join(results_dir, f"summary_{timestamp_str}.csv")
            summary_df = pd.DataFrame(stats, columns=pd.Index(["Metric", "Value"]))
            summary_df.to_csv(summary_filename, index=False)
            print(f"[SUCCESS] Summary statistics saved to: {summary_filename}")
            
            # --- Display results in GUI and Terminal ---
            msg = (
                f"Total Trades: {results['total_trades']}\n"
                f"Win Rate: {results['win_rate']:.2f}%\n"
                f"Total P&L: {results['total_pnl']:.2f}\n"
                f"Total Return: {results['total_return']:.2f}%\n"
                f"Max Drawdown: {results['max_drawdown']:.2f}%\n\n"
                f"Results saved to CSV files in the 'results' folder."
            )
            messagebox.showinfo("Backtest Results", msg)

            # Print summary stats as a table in the terminal
            print("\n=== STRATEGY RESULTS ===")
            print(tabulate(stats, tablefmt="github"))

            # Print sample trades as a table in the terminal
            if isinstance(results['trades_df'], pd.DataFrame) and len(results['trades_df']) > 0:
                print("\n=== SAMPLE TRADES ===")
                print(tabulate(
                    results['trades_df'][['entry_price', 'exit_price', 'pnl',
                                          'trade_duration', 'reason']].head(),
                    headers="keys", tablefmt="github"
                ))

            # Tabulate ENTRY/EXIT logs
            if hasattr(results, "action_logs") and results.get('action_logs'):
                print("\n=== TRADE ACTION LOGS ===")
                headers = ["Action", "Timestamp", "Price", "Size/Qty%", "PnL", "Reason"]
                print(tabulate(results['action_logs'], headers=headers, tablefmt="github"))
        else:
            messagebox.showerror("Backtest Error", results["error"])

if __name__ == "__main__":
    root = tk.Tk()
    app = StrategyParameterGUI(root)
    root.mainloop()
