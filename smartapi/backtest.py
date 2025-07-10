import pandas as pd
import numpy as np
from datetime import datetime, time, timedelta
import pytz
import warnings
import os
warnings.filterwarnings('ignore')
from tabulate import tabulate
from .strategy import ModularIntradayStrategy

class BacktestEngine:
    """
    Backtesting engine that can process both CSV files and price_ticks.log files.
    Uses the same ModularIntradayStrategy as live trading for consistency.
    """
    def __init__(self, params=None):
        self.params = params or {}
        self.strategy = ModularIntradayStrategy(params=self.params)
        self.ist_tz = pytz.timezone('Asia/Kolkata')
        
    def load_csv_data(self, csv_path):
        """Load data from CSV file with standard OHLCV format."""
        try:
            df = pd.read_csv(
                csv_path,
                parse_dates=['timestamp'],
                date_parser=lambda x: pd.to_datetime(x, format='%Y%m%d %H:%M')
            )
            df.set_index('timestamp', inplace=True)
            return df
        except Exception as e:
            raise Exception(f"Error loading CSV data: {e}")
    
    def load_ticks_log(self, log_path):
        """Load data from price_ticks.log file and convert to OHLCV format."""
        if not os.path.exists(log_path):
            raise FileNotFoundError(f"Price ticks log file not found: {log_path}")
        
        print(f"Loading tick data from: {log_path}")
        
        # Read the log file
        ticks_data = []
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                    
                try:
                    # Parse: timestamp,price,volume
                    parts = line.split(',')
                    if len(parts) >= 2:
                        timestamp_str = parts[0]
                        price = float(parts[1])
                        volume = int(parts[2]) if len(parts) > 2 else 0
                        
                        # Parse timestamp (handle timezone)
                        if 'T' in timestamp_str:
                            # ISO format: 2025-07-03T09:22:58+05:30
                            timestamp = pd.to_datetime(timestamp_str)
                        else:
                            # Fallback format
                            timestamp = pd.to_datetime(timestamp_str)
                        
                        ticks_data.append({
                            'timestamp': timestamp,
                            'price': price,
                            'volume': volume
                        })
                        
                except Exception as e:
                    print(f"Warning: Skipping line {line_num}: {line} - Error: {e}")
                    continue
        
        if not ticks_data:
            raise Exception("No valid tick data found in log file")
        
        # Convert to DataFrame
        df_ticks = pd.DataFrame(ticks_data)
        df_ticks.set_index('timestamp', inplace=True)
        
        print(f"Loaded {len(df_ticks)} ticks from {df_ticks.index.min()} to {df_ticks.index.max()}")
        
        # Resample to 1-minute OHLCV bars
        df_ohlcv = df_ticks['price'].resample('1T').ohlc()
        df_volume = df_ticks['volume'].resample('1T').sum()
        
        # Combine OHLC and volume
        # Ensure both are DataFrames
        if not isinstance(df_ohlcv, pd.DataFrame):
            df_ohlcv = pd.DataFrame(df_ohlcv)
        if not isinstance(df_volume, pd.DataFrame):
            df_volume = pd.DataFrame(df_volume)
        df = pd.concat([df_ohlcv, df_volume], axis=1)
        df.columns = ['open', 'high', 'low', 'close', 'volume']
        
        # Forward fill any missing values
        df = df.fillna(method='ffill')
        
        # Remove any remaining NaN rows
        df = df.dropna()
        
        print(f"Converted to {len(df)} 1-minute OHLCV bars")
        return df
    
    def run_backtest(self, data_source, data_type='csv'):
        """
        Run backtest on the provided data source.
        
        Args:
            data_source: Path to CSV file or price_ticks.log file
            data_type: 'csv' or 'ticks'
        """
        print(f"Starting backtest with {data_type} data source: {data_source}")
        
        # Load data based on type
        if data_type == 'csv':
            df = self.load_csv_data(data_source)
        elif data_type == 'ticks':
            df = self.load_ticks_log(data_source)
        else:
            raise ValueError("data_type must be 'csv' or 'ticks'")
        
        # Ensure timezone is set
        if isinstance(df.index, pd.DatetimeIndex) and df.index.tz is None:
            df.index = df.index.tz_localize(self.ist_tz)
        
        print(f"Data loaded: {len(df)} bars from {df.index.min()} to {df.index.max()}")
        
        # Process each bar through the strategy
        print("Processing bars through strategy...")
        
        for i, (timestamp, row) in enumerate(df.iterrows()):
            # Convert bar data to tick format for strategy processing
            # We'll simulate ticks within the bar for more accurate processing
            bar_ticks = self._simulate_bar_ticks(row, timestamp)
            
            for tick_timestamp, tick_price, tick_volume in bar_ticks:
                self.strategy.on_tick(tick_timestamp, tick_price, tick_volume)
        
        print("Backtest completed!")
        return self.strategy.generate_results()
    
    def _simulate_bar_ticks(self, bar_data, bar_timestamp):
        """
        Simulate tick data within a bar for more accurate strategy processing.
        This helps with proper bar aggregation and indicator calculation.
        """
        ticks = []
        
        # Create 5 ticks within the bar (open, high, low, close, and one more)
        tick_times = [
            bar_timestamp,
            bar_timestamp + timedelta(seconds=12),
            bar_timestamp + timedelta(seconds=24),
            bar_timestamp + timedelta(seconds=36),
            bar_timestamp + timedelta(seconds=48)
        ]
        
        tick_prices = [
            bar_data['open'],
            bar_data['high'],
            bar_data['low'],
            bar_data['close'],
            bar_data['close']  # Last tick at close price
        ]
        
        # Distribute volume across ticks
        total_volume = bar_data['volume']
        tick_volumes = [total_volume // 5] * 5
        # Add remainder to last tick
        tick_volumes[-1] += total_volume % 5
        
        for i in range(5):
            ticks.append((tick_times[i], tick_prices[i], tick_volumes[i]))
        
        return ticks
    
    def save_results(self, results, output_dir="smartapi/results"):
        """Save backtest results to files."""
        if "error" in results:
            print(f"Error in results: {results['error']}")
            return
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save trades
        if 'trades_df' in results and not results['trades_df'].empty:
            trades_filename = os.path.join(output_dir, f"backtest_trades_{timestamp_str}.csv")
            results['trades_df'].to_csv(trades_filename, index=False)
            print(f"Trades saved to: {trades_filename}")
        
        # Save equity curve
        if 'equity_df' in results and not results['equity_df'].empty:
            equity_filename = os.path.join(output_dir, f"backtest_equity_{timestamp_str}.csv")
            results['equity_df'].to_csv(equity_filename, index=False)
            print(f"Equity curve saved to: {equity_filename}")
        
        # Save summary
        summary_data = [
            ["Total Trades", results['total_trades']],
            ["Win Rate (%)", f"{results['win_rate']:.2f}"],
            ["Total P&L", f"{results['total_pnl']:.2f}"],
            ["Total Return (%)", f"{results['total_return']:.2f}"],
            ["Max Drawdown (%)", f"{results['max_drawdown']:.2f}"],
            ["Profit Factor", f"{results['profit_factor']:.2f}"],
            ["Final Equity", f"{results['final_equity']:.2f}"]
        ]
        
        summary_filename = os.path.join(output_dir, f"backtest_summary_{timestamp_str}.csv")
        summary_df = pd.DataFrame(summary_data, columns=pd.Index(["Metric", "Value"]))
        summary_df.to_csv(summary_filename, index=False)
        print(f"Summary saved to: {summary_filename}")
        
        return {
            'trades_file': trades_filename if 'trades_df' in results else None,
            'equity_file': equity_filename if 'equity_df' in results else None,
            'summary_file': summary_filename
        }
    
    def print_results(self, results):
        """Print backtest results in a formatted table."""
        if "error" in results:
            print(f"Backtest Error: {results['error']}")
            return
        
        print("\n" + "="*60)
        print("BACKTEST RESULTS")
        print("="*60)
        
        # Summary statistics
        summary = [
            ["Total Trades", results['total_trades']],
            ["Win Rate", f"{results['win_rate']:.2f}%"],
            ["Total P&L", f"₹{results['total_pnl']:,.2f}"],
            ["Total Return", f"{results['total_return']:.2f}%"],
            ["Max Drawdown", f"{results['max_drawdown']:.2f}%"],
            ["Profit Factor", f"{results['profit_factor']:.2f}"],
            ["Final Equity", f"₹{results['final_equity']:,.2f}"]
        ]
        
        print(tabulate(summary, headers=["Metric", "Value"], tablefmt="grid"))
        
        # Sample trades
        if 'trades_df' in results and not results['trades_df'].empty:
            print(f"\nSample Trades (showing first 5 of {len(results['trades_df'])}):")
            sample_trades = results['trades_df'][['entry_time', 'exit_time', 'entry_price', 'exit_price', 'pnl', 'reason']].head()
            print(tabulate(sample_trades, headers="keys", tablefmt="grid"))
        
        # Action logs
        if hasattr(self.strategy, "action_logs") and self.strategy.action_logs:
            print(f"\nTrade Action Logs (showing last 10 of {len(self.strategy.action_logs)}):")
            headers = ["Action", "Timestamp", "Price", "Size/Qty%", "PnL", "Reason"]
            recent_logs = self.strategy.action_logs[-10:]
            print(tabulate(recent_logs, headers=headers, tablefmt="grid"))


def run_backtest_from_file(data_file, params=None, data_type='auto'):
    """
    Convenience function to run backtest from a file.
    
    Args:
        data_file: Path to the data file
        params: Strategy parameters dictionary
        data_type: 'csv', 'ticks', or 'auto' (auto-detect based on file extension)
    """
    # Auto-detect data type
    if data_type == 'auto':
        if data_file.endswith('.log'):
            data_type = 'ticks'
        elif data_file.endswith('.csv'):
            data_type = 'csv'
        else:
            raise ValueError("Cannot auto-detect data type. Please specify 'csv' or 'ticks'")
    
    # Create backtest engine
    engine = BacktestEngine(params=params)
    
    # Run backtest
    results = engine.run_backtest(data_file, data_type)
    
    # Print and save results
    engine.print_results(results)
    saved_files = engine.save_results(results)
    
    return results, saved_files


if __name__ == "__main__":
    # Example usage
    print("Backtest Engine - Example Usage")
    print("="*40)
    
    # Example 1: Backtest with CSV file
    print("\n1. Running backtest with CSV file...")
    try:
        csv_params = {
            'use_supertrend': True,
            'use_ema_crossover': True,
            'use_rsi_filter': True,
            'use_vwap': True,
            'initial_capital': 100000,
            'base_sl_points': 15,
            'tp1_points': 25,
            'tp2_points': 45,
            'tp3_points': 100
        }
        
        # Try to find a CSV file in the data directory
        data_dir = "smartapi/data"
        csv_files = [f for f in os.listdir(data_dir) if f.endswith('.csv')] if os.path.exists(data_dir) else []
        
        if csv_files:
            csv_file = os.path.join(data_dir, csv_files[0])
            print(f"Using CSV file: {csv_file}")
            results, files = run_backtest_from_file(csv_file, csv_params, 'csv')
        else:
            print("No CSV files found in data directory")
            
    except Exception as e:
        print(f"CSV backtest error: {e}")
    
    # Example 2: Backtest with price_ticks.log
    print("\n2. Running backtest with price_ticks.log...")
    try:
        ticks_params = {
            'use_supertrend': False,
            'use_ema_crossover': True,
            'use_rsi_filter': False,
            'use_vwap': True,
            'initial_capital': 100000,
            'base_sl_points': 7,
            'tp1_points': 25,
            'tp2_points': 45,
            'tp3_points': 100
        }
        
        ticks_file = "smartapi/price_ticks.log"
        if os.path.exists(ticks_file):
            print(f"Using ticks file: {ticks_file}")
            results, files = run_backtest_from_file(ticks_file, ticks_params, 'ticks')
        else:
            print("price_ticks.log not found")
            
    except Exception as e:
        print(f"Ticks backtest error: {e}")
    
    print("\nBacktest examples completed!")
