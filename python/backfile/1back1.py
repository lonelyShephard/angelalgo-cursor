import pandas as pd
import numpy as np
from datetime import datetime, time, timedelta
import pytz
import warnings
warnings.filterwarnings('ignore')
from tabulate import tabulate

class ModularIntradayStrategy:
    def __init__(self, params=None):
        # === STRATEGY PARAMETERS ===
        self.start_date = "2025-01-01"
        self.end_date = "2025-12-31"
        self.initial_capital = 100000

        # === INPUT TOGGLES ===
        self.use_supertrend = True
        self.use_vwap = False
        self.use_ema_crossover = True
        self.use_rsi_filter = True

        # === TRADE SESSION OPTIONS ===
        self.is_intraday = True
        self.intraday_start_hour = 9
        self.intraday_start_min = 15
        self.intraday_end_hour = 15
        self.intraday_end_min = 15

        # === INTRADAY SPECIFIC PARAMETERS ===
        self.rsi_length = 14
        self.rsi_overbought = 70
        self.rsi_oversold = 30

        # === STRATEGY PARAMETERS ===
        self.atr_len = 10
        self.atr_mult = 3.0
        self.fast_ema = 9
        self.slow_ema = 21

        # === DUAL STOP LOSS SYSTEM ===
        # 1. BASE STOP LOSS (Non-negotiable, fixed on entry)
        self.base_sl_points = 15
        self.base_stop_price = 0  # Fixed at entry, NEVER changes
        
        # 2. TRAIL STOP LOSS (Profit protection, moves with price)
        self.use_trail_stop = True
        self.trail_stop_price = 0  # Dynamic, moves up with profits
        self.trail_activation_points = 25  # Start trailing after this profit
        self.trail_distance_points = 10   # Trail this many points behind high
        
        # 3. TAKE PROFIT LEVELS
        self.use_tiered_tp = True
        self.tp1_points = 25
        self.tp2_points = 45
        self.tp3_points = 100
        
        # 4. SESSION END (Mandatory exit)
        self.exit_before_close = 20  # minutes before session end
        
        # Deprecated parameters (keeping for compatibility)
        self.use_breakeven_trail = False  # Replaced by trail system
        self.trail_after_tp1 = False      # Replaced by trail system
        self.trail_tightness = 0.3        # Not used anymore

        # Additional parameters
        self.use_end_day_momentum = False
        self.momentum_length = 5

        # === POSITION TRACKING VARIABLES ===
        self.position_size = 0
        self.position_entry_price = 0
        self.position_entry_time = None
        self.position_high_price = 0  # Track highest price for trailing
        self.tp1_filled = 0.0
        self.tp2_filled = 0.0
        self.trailing_active = False

        # === RE-ENTRY TRACKING ===
        self.last_exit_price = None
        self.last_entry_price = None
        self.last_exit_reason = ""
        self.last_exit_bar = 0
        self.last_time_exit_date = None

        # === TIMEZONE ===
        import pytz
        self.ist_tz = pytz.timezone('Asia/Kolkata')

        # === RESULTS TRACKING ===
        self.trades = []
        self.equity_curve = []
        self.current_equity = self.initial_capital

        # === OVERRIDE WITH PARAMS ===
        if params:
            for k, v in params.items():
                setattr(self, k, v)
        
        # === ACTION LOGGING ===
        self.action_logs = []
    
    def calculate_atr(self, df, period=10):
        """Calculate Average True Range"""
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        
        true_range = np.maximum(high_low, np.maximum(high_close, low_close))
        atr = true_range.rolling(window=period).mean()
        return atr
    
    def calculate_supertrend(self, df, atr_period=10, atr_mult=3.0):
        """Calculate Supertrend indicator"""
        atr = self.calculate_atr(df, atr_period)
        hlc3 = (df['high'] + df['low'] + df['close']) / 3
        
        up = hlc3 - atr_mult * atr
        dn = hlc3 + atr_mult * atr
        
        trend = pd.Series(index=df.index, dtype=int)
        trend.iloc[0] = 1
        
        for i in range(1, len(df)):
            if df['close'].iloc[i] > dn.iloc[i-1]:
                trend.iloc[i] = 1
            elif df['close'].iloc[i] < up.iloc[i-1]:
                trend.iloc[i] = -1
            else:
                trend.iloc[i] = trend.iloc[i-1]
                
        return trend
    
    def calculate_vwap(self, df):
        """Calculate Volume Weighted Average Price"""
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        vwap = (typical_price * df['volume']).cumsum() / df['volume'].cumsum()
        return vwap
    
    def calculate_rsi(self, series, period=14):
        """Calculate RSI"""
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def calculate_ema(self, series, period):
        """Calculate Exponential Moving Average"""
        return series.ewm(span=period).mean()
    
    def is_in_session(self, timestamp):
        """Check if timestamp is within trading session"""
        if not self.is_intraday:
            return True

        if timestamp.tzinfo is None:
            timestamp = self.ist_tz.localize(timestamp)
        ist_time = timestamp.time()
        start_time = time(self.intraday_start_hour, self.intraday_start_min)
        end_time = time(self.intraday_end_hour, self.intraday_end_min)

        return start_time <= ist_time <= end_time
    
    def get_current_hour_minute_ist(self, timestamp):
        """Get current hour and minute in IST"""
        if timestamp.tzinfo is None:
            timestamp = self.ist_tz.localize(timestamp)
        return timestamp.hour, timestamp.minute
    
    def is_near_session_end(self, timestamp):
        """Check if we're near session end"""
        if not self.is_intraday:
            return False
            
        current_hour, current_min = self.get_current_hour_minute_ist(timestamp)
        current_minutes = current_hour * 60 + current_min
        end_minutes = self.intraday_end_hour * 60 + self.intraday_end_min
        
        time_to_end = end_minutes - current_minutes
        return 0 < time_to_end <= self.exit_before_close
    
    def is_end_of_session(self, timestamp):
        """Check if session has ended"""
        if not self.is_intraday:
            return False
            
        current_hour, current_min = self.get_current_hour_minute_ist(timestamp)
        current_minutes = current_hour * 60 + current_min
        end_minutes = self.intraday_end_hour * 60 + self.intraday_end_min
        
        return current_minutes >= end_minutes
    
    def should_allow_new_entries(self, timestamp):
        """Check if new entries are allowed"""
        if not self.is_intraday:
            return True
            
        current_hour, current_min = self.get_current_hour_minute_ist(timestamp)
        current_minutes = current_hour * 60 + current_min
        end_minutes = self.intraday_end_hour * 60 + self.intraday_end_min
        
        time_to_end = end_minutes - current_minutes
        return time_to_end > (self.exit_before_close + 30)
    
    def calculate_signal_strength(self, supertrend_dir, vwap_bull, ema_bull, row_idx):
        """Calculate signal strength based on active indicators"""
        strength = 0
        
        if self.use_supertrend and supertrend_dir == 1:
            strength += 1
        if self.use_vwap and vwap_bull:
            strength += 1
        if self.use_ema_crossover and ema_bull:
            strength += 1
            
        return strength
    
    def can_reenter(self, current_price, signal_strength, bars_from_exit, timestamp=None):
        """Check if re-entry is allowed based on previous exit reason"""
        if self.last_exit_price is None:
            return True
        
        # Block re-entry only if last time exit was today
        if self.last_exit_reason == "time" and self.last_time_exit_date == timestamp.date():
            return False
        
        # For stop, trail, or profit exits: need price 5 points above previous entry + 2 indicators
        if self.last_entry_price is not None:
            price_condition = current_price > (self.last_entry_price + 5)
            signal_condition = signal_strength >= 2
            return price_condition and signal_condition
            
        return False
    
    def enter_position(self, price, timestamp, reason="Buy Signal"):
        """Enter a long position and set up dual stop loss system"""
        if self.position_size == 0:
            self.position_size = self.current_equity / price
            self.position_entry_price = price
            self.position_entry_time = timestamp
            self.position_high_price = price  # Initialize high price tracker
            
            # 1. BASE STOP LOSS - Fixed and non-negotiable
            self.base_stop_price = price - self.base_sl_points
            
            # 2. TRAIL STOP LOSS - Initially disabled
            self.trail_stop_price = 0
            self.trailing_active = False
            
            # Reset profit tracking
            self.tp1_filled = 0.0
            self.tp2_filled = 0.0
            
            log = ["ENTRY", timestamp, f"{price:.2f}", f"{self.position_size:.2f}", 
                   f"Base SL: {self.base_stop_price:.2f}", reason]
            self.action_logs.append(log)
            print(f"ENTRY: {timestamp} - Price: {price:.2f} - Size: {self.position_size:.2f}")
            print(f"  └─ BASE STOP (Fixed): {self.base_stop_price:.2f}")
            print(f"  └─ TRAIL STOP: Inactive (activates at +{self.trail_activation_points} points)")
    
    def update_trailing_stop(self, current_price, timestamp):
        """Update trailing stop loss based on current price"""
        if not self.use_trail_stop or self.position_size <= 0:
            return
            
        # Update position high
        if current_price > self.position_high_price:
            self.position_high_price = current_price
            
        # Check if trailing should be activated
        profit_points = current_price - self.position_entry_price
        
        if not self.trailing_active and profit_points >= self.trail_activation_points:
            # Activate trailing stop
            self.trailing_active = True
            self.trail_stop_price = self.position_high_price - self.trail_distance_points
            print(f"TRAIL ACTIVATED: {timestamp} - Trail Stop: {self.trail_stop_price:.2f}")
            
        elif self.trailing_active:
            # Update trailing stop (only move up)
            new_trail_stop = self.position_high_price - self.trail_distance_points
            if new_trail_stop > self.trail_stop_price:
                old_trail = self.trail_stop_price
                self.trail_stop_price = new_trail_stop
                print(f"TRAIL UPDATED: {old_trail:.2f} -> {self.trail_stop_price:.2f} (High: {self.position_high_price:.2f})")
    
    def get_effective_stop_price(self):
        """Get the effective stop price (higher of base stop and trail stop)"""
        if not self.trailing_active or self.trail_stop_price <= 0:
            return self.base_stop_price
        else:
            # Base stop overrides trail stop if base stop is higher
            return max(self.base_stop_price, self.trail_stop_price)
    
    def check_stop_loss_hit(self, current_price):
        """Check if any stop loss has been hit and return reason"""
        effective_stop = self.get_effective_stop_price()
        
        if current_price <= effective_stop:
            # Determine which stop was hit
            if current_price <= self.base_stop_price:
                return True, "Base Stop Loss"
            elif self.trailing_active and current_price <= self.trail_stop_price:
                return True, "Trail Stop Loss"
            else:
                return True, "Stop Loss"  # Fallback
        
        return False, ""

    def exit_position(self, price, timestamp, qty_percent=100, reason="Exit"):
        """Exit position (partial or full)"""
        if self.position_size > 0:
            exit_qty = self.position_size * (qty_percent / 100)
            exit_value = exit_qty * price
            entry_value = exit_qty * self.position_entry_price
            pnl = exit_value - entry_value
            self.current_equity += pnl
            self.position_size -= exit_qty
            
            log = ["EXIT", timestamp, f"{price:.2f}", f"{qty_percent}%", f"{pnl:.2f}", reason]
            self.action_logs.append(log)
            print(f"EXIT: {timestamp} - Price: {price:.2f} - Qty%: {qty_percent}% - PnL: {pnl:.2f} - Reason: {reason}")
            
            trade = {
                'entry_time': self.position_entry_time,
                'exit_time': timestamp,
                'entry_price': self.position_entry_price,
                'exit_price': price,
                'quantity': exit_qty,
                'pnl': pnl,
                'reason': reason
            }
            self.trades.append(trade)

            # Reset position tracking if fully exited
            if self.position_size <= 0.001:
                self.last_exit_price = price
                self.last_entry_price = self.position_entry_price
                self.position_size = 0
                self.position_entry_time = None
                self.position_high_price = 0
                # Reset stop loss system
                self.base_stop_price = 0
                self.trail_stop_price = 0
                self.trailing_active = False
                self.tp1_filled = 0.0
                self.tp2_filled = 0.0
    
    def classify_exit_reason(self, exit_price, entry_price):
        """Classify why the trade was exited"""
        trade_points = exit_price - entry_price
        
        if trade_points <= -(self.base_sl_points * 0.9):
            return "stop"
        elif trade_points >= (self.tp2_points * 0.8):
            return "profit"
        elif trade_points >= (self.tp1_points * 0.8):
            return "trail"
        else:
            return "other"
    
    def run_strategy(self, df):
        """Main strategy execution function"""
        print("Starting strategy execution...")
        print(f"Stop Loss System: Base={self.base_sl_points}pts, Trail={self.trail_distance_points}pts (activates at +{self.trail_activation_points}pts)")

        # Ensure datetime index
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)

        # Make index tz-naive to avoid tz-aware/naive comparison errors
        df.index = df.index.tz_localize(None)

        # Calculate indicators
        print("Calculating indicators...")
        df['atr'] = self.calculate_atr(df, self.atr_len)
        df['supertrend'] = self.calculate_supertrend(df, self.atr_len, self.atr_mult)
        df['vwap'] = self.calculate_vwap(df)
        df['rsi'] = self.calculate_rsi(df['close'], self.rsi_length)
        df['ema_fast'] = self.calculate_ema(df['close'], self.fast_ema)
        df['ema_slow'] = self.calculate_ema(df['close'], self.slow_ema)
        
        # Calculate derived signals
        df['vwap_bull'] = df['close'] > df['vwap']
        df['ema_crossover'] = (df['ema_fast'] > df['ema_slow']) & (df['ema_fast'].shift() <= df['ema_slow'].shift())
        df['ema_bull'] = df['ema_crossover']
        
        # Higher timeframe trend (simplified - using same timeframe EMA50)
        df['htf_trend'] = self.calculate_ema(df['close'], 50)
        df['htf_bullish'] = df['close'] > df['htf_trend']
        
        print("Running strategy logic...")
        
        for i, (timestamp, row) in enumerate(df.iterrows()):
            # Skip initial rows with NaN values
            if i < max(self.atr_len, self.rsi_length, self.slow_ema):
                continue
            
            # Date range filter
            if timestamp.tzinfo is not None:
                timestamp = timestamp.tz_convert(None)
            if pd.Timestamp(self.start_date).tzinfo is not None:
                start_date = pd.Timestamp(self.start_date).tz_convert(None)
            else:
                start_date = pd.Timestamp(self.start_date)
            if pd.Timestamp(self.end_date).tzinfo is not None:
                end_date = pd.Timestamp(self.end_date).tz_convert(None)
            else:
                end_date = pd.Timestamp(self.end_date)
            if timestamp < start_date or timestamp > end_date:
                continue
            
            # Session filter
            in_session = self.is_in_session(timestamp)
            if not in_session:
                continue
            
            # Current values
            current_price = row['close']
            supertrend_dir = row['supertrend']
            vwap_bull = row['vwap_bull']
            ema_bull = row['ema_bull']
            rsi_val = row['rsi']
            htf_bullish = row['htf_bullish']
            
            # Filters
            rsi_filter = not self.use_rsi_filter or (rsi_val > self.rsi_oversold and rsi_val < self.rsi_overbought)
            market_structure_filter = htf_bullish
            
            # Buy signal logic
            buy_signal = (
                (not self.use_supertrend or supertrend_dir == 1) and
                (not self.use_vwap or vwap_bull) and
                (not self.use_ema_crossover or ema_bull)
            )
            
            intraday_buy_signal = buy_signal and rsi_filter and market_structure_filter
            
            # Signal strength for re-entry
            signal_strength = self.calculate_signal_strength(supertrend_dir, vwap_bull, ema_bull, i)
            bars_from_exit = i - self.last_exit_bar
            
            # Re-entry logic
            can_reenter = self.can_reenter(current_price, signal_strength, bars_from_exit, timestamp)
            
            # Entry conditions
            allow_new_entries = self.should_allow_new_entries(timestamp)
            late_entry_check = self.is_intraday and timestamp.hour >= 14 and timestamp.minute >= 30
            
            # ENTRY LOGIC
            if (intraday_buy_signal and can_reenter and self.position_size == 0 and 
                allow_new_entries and not late_entry_check):
                self.enter_position(current_price, timestamp)
            
            # POSITION MANAGEMENT
            if self.position_size > 0:
                # 1. MANDATORY SESSION END CHECK (Highest Priority)
                if self.is_near_session_end(timestamp) or self.is_end_of_session(timestamp):
                    self.exit_position(current_price, timestamp, 100, "MANDATORY: Session End")
                    self.last_exit_reason = "time"
                    self.last_exit_bar = i
                    self.last_time_exit_date = timestamp.date()
                    continue
                
                # 2. UPDATE TRAILING STOP
                self.update_trailing_stop(current_price, timestamp)
                
                # 3. CHECK STOP LOSS (Base overrides Trail)
                stop_hit, stop_reason = self.check_stop_loss_hit(current_price)
                if stop_hit:
                    self.exit_position(current_price, timestamp, 100, f"MANDATORY: {stop_reason}")
                    self.last_exit_reason = self.classify_exit_reason(current_price, self.position_entry_price)
                    self.last_exit_bar = i
                    continue
                
                # 4. TAKE PROFIT LEVELS (Optional exits)
                if self.use_tiered_tp:
                    entry_price = self.position_entry_price
                    tp1_price = entry_price + self.tp1_points
                    tp2_price = entry_price + self.tp2_points
                    tp3_price = entry_price + self.tp3_points
                    
                    # TP1: Take 50% profit
                    if self.tp1_filled == 0 and current_price >= tp1_price:
                        self.exit_position(current_price, timestamp, 50, "TP1-Quick")
                        self.tp1_filled = tp1_price
                    
                    # TP2: Take additional 30% (60% of remaining)
                    if self.tp2_filled == 0 and current_price >= tp2_price and self.tp1_filled > 0:
                        self.exit_position(current_price, timestamp, 60, "TP2-Medium")  
                        self.tp2_filled = tp2_price
                    
                    # TP3: Exit remaining position
                    elif self.tp2_filled > 0 and current_price >= tp3_price:
                        self.exit_position(current_price, timestamp, 100, "TP3-Runner")
                        self.last_exit_reason = "profit"
                        self.last_exit_bar = i
            
            # Track equity curve
            current_equity = self.current_equity
            if self.position_size > 0:
                unrealized_pnl = (current_price - self.position_entry_price) * self.position_size
                current_equity += unrealized_pnl
            
            self.equity_curve.append({
                'timestamp': timestamp,
                'equity': current_equity,
                'position_size': self.position_size
            })
        
        print("Strategy execution completed!")
        return self.generate_results()
    
    def generate_results(self):
        """Generate strategy results and statistics"""
        if not self.trades:
            return {"error": "No trades executed"}
        
        trades_df = pd.DataFrame(self.trades)
        # Calculate trade duration
        if not trades_df.empty:
            trades_df['trade_duration'] = trades_df['exit_time'] - trades_df['entry_time']

        equity_df = pd.DataFrame(self.equity_curve)
        
        # Calculate statistics
        total_trades = len(trades_df)
        winning_trades = len(trades_df[trades_df['pnl'] > 0])
        losing_trades = len(trades_df[trades_df['pnl'] < 0])
        win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0
        
        total_pnl = trades_df['pnl'].sum()
        avg_win = trades_df[trades_df['pnl'] > 0]['pnl'].mean() if winning_trades > 0 else 0
        avg_loss = trades_df[trades_df['pnl'] < 0]['pnl'].mean() if losing_trades > 0 else 0
        
        max_equity = equity_df['equity'].max()
        min_equity = equity_df['equity'].min()
        max_drawdown = ((max_equity - min_equity) / max_equity) * 100 if max_equity > 0 else 0
        
        final_equity = equity_df['equity'].iloc[-1] if len(equity_df) > 0 else self.initial_capital
        total_return = ((final_equity - self.initial_capital) / self.initial_capital) * 100
        
        results = {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': abs(avg_win / avg_loss) if avg_loss != 0 else float('inf'),
            'max_drawdown': max_drawdown,
            'total_return': total_return,
            'final_equity': final_equity,
            'trades_df': trades_df,
            'equity_df': equity_df
        }
        
        return results