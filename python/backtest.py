import pandas as pd
import numpy as np
import talib
from datetime import datetime, timedelta
from typing import Dict, Tuple

class LongOnlyIntradayStrategy:
    def __init__(self, config: Dict):
        """
        Initialize long-only intraday strategy parameters
        
        Config parameters:
        - atr_period: Period for ATR calculation (default: 10)
        - atr_multiplier: Multiplier for Supertrend (default: 3.0)
        - stop_loss_pct: Stop loss percentage (default: 2%)
        - target_pct: Take profit percentage (default: 3%)
        - max_trades_per_day: Maximum trades per day (default: 3)
        """
        self.config = config
        self.position = 0  # No position
        self.trades = []
        self.current_stop_loss = None
        self.current_target = None
        self.trades_today = 0
        self.current_day = None

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate technical indicators for long-only strategy"""
        # EMA
        df['ema20'] = talib.EMA(df['close'], timeperiod=20)
        df['ema50'] = talib.EMA(df['close'], timeperiod=50)
        
        # RSI
        df['rsi'] = talib.RSI(df['close'], timeperiod=14)
        
        # VWAP (calculated per day)
        df['vwap'] = df.groupby(df.index.date).apply(
            lambda x: (x['volume'] * (x['high'] + x['low'] + x['close']) / 3).cumsum() / 
            x['volume'].cumsum()).values
        
        # Supertrend
        df = self.calculate_supertrend(df)
        
        return df

    def generate_signals(self, df: pd.DataFrame, idx: int) -> Dict:
        """Generate long-only trading signals"""
        row = df.iloc[idx]
        current_time = df.index[idx]
        
        # Reset trades counter for new day
        if self.current_day != current_time.date():
            self.current_day = current_time.date()
            self.trades_today = 0
        
        signals = {
            'buy': False,
            'close': False
        }
        
        # Check if it's too late in the day (e.g., after 3:15 PM)
        if current_time.time() >= pd.Timestamp('15:15').time():
            signals['close'] = True
            return signals
            
        # Check if we've reached max trades for the day
        if self.trades_today >= self.config.get('max_trades_per_day', 3):
            return signals
            
        # Long entry conditions
        if (self.position == 0 and
            row['supertrend_direction'] == 1 and 
            row['close'] > row['ema20'] > row['ema50'] and
            row['rsi'] > 30 and row['rsi'] < 70 and
            row['close'] > row['vwap']):
            signals['buy'] = True
            
        return signals

    def run_backtest(self, data: pd.DataFrame) -> Dict:
        """Run backtest for long-only intraday strategy"""
        df = data.copy()
        df = self.calculate_indicators(df)
        
        for idx in range(1, len(df)):
            current_time = df.index[idx]
            current_price = df['close'].iloc[idx]
            
            # Check for position closure (stop loss/target)
            if self.position == 1:
                if (current_price <= self.current_stop_loss or 
                    current_price >= self.current_target):
                    self.close_position(df, idx, 'sl_or_target')
                    continue
            
            # Generate new signals
            signals = self.generate_signals(df, idx)
            
            # Execute trades based on signals
            if signals['buy']:
                self.enter_long_position(df, idx)
            elif signals['close'] and self.position == 1:
                self.close_position(df, idx, 'day_end')

        return {
            'trades': self.trades,
            'metrics': self.calculate_metrics()
        }

    def enter_long_position(self, df: pd.DataFrame, idx: int):
        """Enter a long position with proper risk management"""
        entry_price = df['close'].iloc[idx]
        self.trades.append({
            'entry_time': df.index[idx],
            'entry_price': entry_price,
            'type': 'buy'
        })
        self.position = 1
        self.trades_today += 1
        
        # Set stop loss and target
        stop_loss_pct = self.config.get('stop_loss_pct', 0.02)
        target_pct = self.config.get('target_pct', 0.03)
        self.current_stop_loss = entry_price * (1 - stop_loss_pct)
        self.current_target = entry_price * (1 + target_pct)

    def close_position(self, df: pd.DataFrame, idx: int, reason: str):
        """Close the current position"""
        self.trades.append({
            'exit_time': df.index[idx],
            'exit_price': df['close'].iloc[idx],
            'type': 'sell',
            'reason': reason
        })
        self.position = 0
        self.current_stop_loss = None
        self.current_target = None

    def calculate_metrics(self) -> Dict:
        """Calculate strategy performance metrics"""
        if len(self.trades) == 0:
            return {'total_profit': 0, 'num_trades': 0, 'win_rate': 0}
            
        profits = []
        for i in range(0, len(self.trades)-1, 2):
            entry = self.trades[i]
            exit = self.trades[i+1]
            profit = exit['exit_price'] - entry['entry_price']
            profits.append(profit)
            
        num_trades = len(profits)
        winning_trades = len([p for p in profits if p > 0])
        
        return {
            'total_profit': sum(profits),
            'num_trades': num_trades,
            'win_rate': winning_trades/num_trades if num_trades > 0 else 0,
            'avg_profit_per_trade': np.mean(profits) if profits else 0
        }

if __name__ == "__main__":
    # Example configuration
    config = {
        'atr_period': 10,
        'atr_multiplier': 3.0,
        'stop_loss_pct': 0.02,
        'target_pct': 0.03,
        'max_trades_per_day': 3
    }
    
    # Load historical data
    data = pd.read_csv(r"c:\Users\user\projects\angelalgo\historical_data.csv")
    data['timestamp'] = pd.to_datetime(data['timestamp'])
    data.set_index('timestamp', inplace=True)
    
    # Run backtest
    strategy = LongOnlyIntradayStrategy(config)
    results = strategy.run_backtest(data)
    
    # Print results
    print("\nBacktest Results:")
    print(f"Total Profit: {results['metrics']['total_profit']:.2f}")
    print(f"Number of Trades: {results['metrics']['num_trades']}")
    print(f"Win Rate: {results['metrics']['win_rate']*100:.1f}%")
    print(f"Average Profit per Trade: {results['metrics']['avg_profit_per_trade']:.2f}")