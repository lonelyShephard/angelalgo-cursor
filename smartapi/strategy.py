# c:\Users\user\projects\angelalgo\smartapi\strategy.py
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
        self.use_vwap = True
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
        self.base_sl_points = 15
        self.base_stop_price = 0
        
        self.use_trail_stop = True
        self.trail_stop_price = 0
        self.trail_activation_points = 25
        self.trail_distance_points = 10
        
        # === TAKE PROFIT LEVELS ===
        self.use_tiered_tp = True
        self.tp1_points = 25
        self.tp2_points = 45
        self.tp3_points = 100
        
        # === SESSION END (Mandatory exit) ===
        self.exit_before_close = 20  # minutes before session end
        
        # === RISK MANAGEMENT ===
        self.risk_per_trade_percent = 1.0 # Risk 1% of current equity per trade

        # === POSITION TRACKING VARIABLES ===
        self.position_size = 0
        self.position_entry_price = 0
        self.position_entry_time = None
        self.position_high_price = 0
        self.tp1_filled = 0.0
        self.tp2_filled = 0.0
        self.trailing_active = False

        # === RE-ENTRY TRACKING ===
        self.last_exit_price = None
        self.last_entry_price = None
        self.last_exit_reason = ""
        self.last_exit_bar_idx = -1
        self.last_time_exit_date = None

        # === RE-ENTRY PARAMETERS ===
        self.reentry_price_buffer = 5
        self.reentry_momentum_lookback = 3
        self.reentry_min_green_candles = 1

        # === TIMEZONE ===
        self.ist_tz = pytz.timezone('Asia/Kolkata')

        # === RESULTS TRACKING ===
        self.trades = []
        self.equity_curve = []
        self.current_equity = self.initial_capital
        self.equity_curve.append({'timestamp': None, 'equity': self.initial_capital})

        # === OVERRIDE WITH PARAMS ===
        if params:
            for k, v in params.items():
                setattr(self, k, v)
        
        # === ACTION LOGGING ===
        self.action_logs = []

        # === REAL-TIME DATA MANAGEMENT ===
        self.max_bar_history_length = max(
            self.atr_len, self.rsi_length, self.slow_ema, 20,
            self.reentry_momentum_lookback
        ) * 2
        
        self.min_bars_for_signals = max(self.atr_len, self.rsi_length, self.slow_ema, 20, self.reentry_momentum_lookback)
        
        self._bar_history_list = [] 
        self.current_bar_data = {
            'open': None, 'high': None, 'low': None, 'close': None, 'volume': 0, 'timestamp': None
        }
        self.last_processed_minute = None

        # Real-time VWAP tracking
        self.daily_vwap_sum_tpv = 0.0
        self.daily_vwap_sum_volume = 0.0
        self.last_vwap_day = None
        self.current_vwap = np.nan
        self.current_vwap_bull = False

        # Supertrend state
        self.supertrend_trend = 1
        self.supertrend_final_upperband = None
        self.supertrend_final_lowerband = None

    def _get_bar_history_df(self):
        """Converts the list of bar data to a DataFrame for calculations."""
        if not self._bar_history_list:
            return pd.DataFrame(columns=['open', 'high', 'low', 'close', 'volume'])
        
        df = pd.DataFrame(self._bar_history_list)
        df.set_index('timestamp', inplace=True)
        df.index = pd.to_datetime(df.index)
        return df

    def _calculate_atr_latest(self):
        """Calculate ATR for the latest bar in history."""
        temp_df = self._get_bar_history_df()
        if len(temp_df) < self.atr_len + 1:
            return np.nan

        high_low = temp_df['high'] - temp_df['low']
        high_close = np.abs(temp_df['high'] - temp_df['close'].shift())
        low_close = np.abs(temp_df['low'] - temp_df['close'].shift())
        
        true_range = np.maximum(high_low, np.maximum(high_close, low_close))
        atr = true_range.rolling(window=self.atr_len).mean().iloc[-1]
        return atr

    def _calculate_supertrend_latest(self):
        """Calculate Supertrend for the latest bar, updating internal state."""
        temp_df = self._get_bar_history_df()
        if len(temp_df) < self.atr_len + 1:
            return self.supertrend_trend

        current_bar = temp_df.iloc[-1]
        atr = self._calculate_atr_latest()
        if pd.isna(atr):
            return self.supertrend_trend

        hlc3 = (current_bar['high'] + current_bar['low'] + current_bar['close']) / 3
        upperband = hlc3 + self.atr_mult * atr
        lowerband = hlc3 - self.atr_mult * atr

        if self.supertrend_final_upperband is None or self.supertrend_final_lowerband is None:
            self.supertrend_final_upperband = upperband
            self.supertrend_final_lowerband = lowerband

        if current_bar['close'] > self.supertrend_final_upperband:
            self.supertrend_final_upperband = lowerband
        else:
            self.supertrend_final_upperband = min(upperband, self.supertrend_final_upperband)

        if current_bar['close'] < self.supertrend_final_lowerband:
            self.supertrend_final_lowerband = upperband
        else:
            self.supertrend_final_lowerband = max(lowerband, self.supertrend_final_lowerband)

        if self.supertrend_trend == 1 and current_bar['close'] < self.supertrend_final_lowerband:
            self.supertrend_trend = -1
        elif self.supertrend_trend == -1 and current_bar['close'] > self.supertrend_final_upperband:
            self.supertrend_trend = 1

        return self.supertrend_trend

    def _calculate_vwap_latest(self, current_price, current_volume, current_timestamp):
        """Calculate real-time VWAP for the current day."""
        current_day = current_timestamp.date()
        if self.last_vwap_day is None or current_day != self.last_vwap_day:
            self.daily_vwap_sum_tpv = 0.0
            self.daily_vwap_sum_volume = 0.0
            self.last_vwap_day = current_day
            self.supertrend_final_upperband = None
            self.supertrend_final_lowerband = None

        self.daily_vwap_sum_tpv += current_price * current_volume
        self.daily_vwap_sum_volume += current_volume

        if self.daily_vwap_sum_volume > 0:
            return self.daily_vwap_sum_tpv / self.daily_vwap_sum_volume
        return np.nan
    
    def _calculate_rsi_latest(self):
        """Calculate RSI for the latest bar in history."""
        temp_df = self._get_bar_history_df()
        if len(temp_df) < self.rsi_length + 1:
            return np.nan
        
        series = temp_df['close'].tail(self.rsi_length * 2)
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_length).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_length).mean()
        
        rs = gain / loss if (loss != 0).all() else pd.Series(np.inf, index=gain.index)
        rsi = 100 - (100 / (1 + rs))
        return rsi.iloc[-1]

    def _calculate_ema_latest(self, period):
        """Calculate EMA for the latest bar in history."""
        temp_df = self._get_bar_history_df()
        if len(temp_df) < period:
            return np.nan
        
        series = temp_df['close'].tail(period * 2)
        return series.ewm(span=period, adjust=False).mean().iloc[-1]

    def is_in_session(self, timestamp):
        """Check if timestamp is within trading session"""
        if not self.is_intraday: return True
        ist_time = timestamp.astimezone(self.ist_tz).time()
        start_time = time(self.intraday_start_hour, self.intraday_start_min)
        end_time = time(self.intraday_end_hour, self.intraday_end_min)
        return start_time <= ist_time <= end_time
    
    def is_near_session_end(self, timestamp):
        """Check if we're near session end"""
        if not self.is_intraday: return False
        t = timestamp.astimezone(self.ist_tz)
        end_time = t.replace(hour=self.intraday_end_hour, minute=self.intraday_end_min, second=0, microsecond=0)
        time_to_end = (end_time - t).total_seconds() / 60
        return 0 < time_to_end <= self.exit_before_close
    
    def should_allow_new_entries(self, timestamp):
        """Check if new entries are allowed"""
        if not self.is_intraday: return True
        t = timestamp.astimezone(self.ist_tz)
        end_time = t.replace(hour=self.intraday_end_hour, minute=self.intraday_end_min, second=0, microsecond=0)
        time_to_end = (end_time - t).total_seconds() / 60
        return time_to_end > (self.exit_before_close + 30)
    
    def _check_reentry_momentum(self, bar_history_df):
        """Checks for momentum in the last few candles for re-entry."""
        if len(bar_history_df) < self.reentry_momentum_lookback + 1:
            return False

        lookback_df = bar_history_df.iloc[-self.reentry_momentum_lookback:]
        price_increase_over_lookback = lookback_df.iloc[-1]['close'] > lookback_df.iloc[0]['close']
        green_candles_count = (lookback_df['close'] > lookback_df['open']).sum()
        
        return price_increase_over_lookback and green_candles_count >= self.reentry_min_green_candles

    def can_reenter(self, current_price, timestamp, current_bar_data):
        """Check if re-entry is allowed based on previous exit reason and new conditions."""
        if self.last_exit_price is None:
            return True

        if self.last_exit_reason == "time" and self.last_time_exit_date == timestamp.date():
            return False

        if self.last_entry_price is not None:
            if not (current_price > (self.last_entry_price + self.reentry_price_buffer)): return False
            if self.use_ema_crossover and not current_bar_data.get('ema_bull', False): return False

            # FIX: Use the real-time self.current_vwap_bull directly
            indicator_bullish_check = (self.use_vwap and self.current_vwap_bull) or \
                                      (self.use_supertrend and current_bar_data.get('supertrend') == 1)
            if not indicator_bullish_check: return False

            if not self._check_reentry_momentum(self._get_bar_history_df()): return False
            
            return True
        return False
    
    def enter_position(self, price, timestamp, reason="Buy Signal"):
        """Enter a long position and set up dual stop loss system"""
        if self.position_size == 0:
            capital_to_risk = self.current_equity * (self.risk_per_trade_percent / 100.0)
            position_size = int(capital_to_risk / self.base_sl_points)
            
            if position_size == 0:
                position_size = 1
            
            self.position_size = position_size
            self.position_entry_price = price
            self.position_entry_time = timestamp
            self.position_high_price = price
            self.base_stop_price = price - self.base_sl_points
            self.trail_stop_price = 0
            self.trailing_active = False
            self.tp1_filled = 0.0
            self.tp2_filled = 0.0
            
            log = ["ENTRY", timestamp, f"{price:.2f}", f"{self.position_size}", f"Base SL: {self.base_stop_price:.2f}", reason]
            self.action_logs.append(log)
            print(f"ENTRY: {timestamp} - Price: {price:.2f} - Size: {self.position_size}")
            print(f"  └─ BASE STOP (Fixed): {self.base_stop_price:.2f}")
            print(f"  └─ TRAIL STOP: Inactive (activates at +{self.trail_activation_points} points)")
    
    def update_trailing_stop(self, current_price, timestamp):
        """Update trailing stop loss based on current price"""
        if not self.use_trail_stop or self.position_size <= 0: return
            
        if current_price > self.position_high_price:
            self.position_high_price = current_price
            
        profit_points = current_price - self.position_entry_price
        
        if not self.trailing_active and profit_points >= self.trail_activation_points:
            self.trailing_active = True
            self.trail_stop_price = self.position_high_price - self.trail_distance_points
            print(f"TRAIL ACTIVATED: {timestamp} - Trail Stop: {self.trail_stop_price:.2f}")
        elif self.trailing_active:
            new_trail_stop = self.position_high_price - self.trail_distance_points
            if new_trail_stop > self.trail_stop_price:
                old_trail = self.trail_stop_price
                self.trail_stop_price = new_trail_stop
                print(f"TRAIL UPDATED: {old_trail:.2f} -> {self.trail_stop_price:.2f} (High: {self.position_high_price:.2f})")
    
    def get_effective_stop_price(self):
        """Get the higher of the base stop and the trail stop."""
        if not self.trailing_active or self.trail_stop_price <= 0:
            return self.base_stop_price
        return max(self.base_stop_price, self.trail_stop_price)
    
    def check_stop_loss_hit(self, current_price):
        """Check if any stop loss has been hit."""
        effective_stop = self.get_effective_stop_price()
        if current_price <= effective_stop:
            reason = "Trail Stop Loss" if self.trailing_active and self.trail_stop_price > self.base_stop_price else "Base Stop Loss"
            return True, reason
        return False, ""

    def _reset_position_state(self):
        """Helper to reset all position-related variables after a full exit."""
        self.position_size = 0
        self.position_entry_time = None
        self.position_high_price = 0
        self.base_stop_price = 0
        self.trail_stop_price = 0
        self.trailing_active = False
        self.tp1_filled = 0.0
        self.tp2_filled = 0.0

    def exit_position(self, price, timestamp, qty_percent=100, reason="Exit", exit_classification=None):
        """Exit position (partial or full) and log the trade."""
        if self.position_size > 0:
            exit_qty = self.position_size * (qty_percent / 100)
            if exit_qty > self.position_size: exit_qty = self.position_size
            
            pnl = (price - self.position_entry_price) * exit_qty
            self.current_equity += pnl
            self.position_size -= exit_qty
            
            log = ["EXIT", timestamp, f"{price:.2f}", f"{qty_percent}%", f"{pnl:.2f}", reason]
            self.action_logs.append(log)
            print(f"EXIT: {timestamp} - Price: {price:.2f} - Qty%: {qty_percent}% - PnL: {pnl:.2f} - Reason: {reason}")
            
            trade = {'entry_time': self.position_entry_time, 'exit_time': timestamp, 'entry_price': self.position_entry_price, 'exit_price': price, 'quantity': exit_qty, 'pnl': pnl, 'reason': reason}
            self.trades.append(trade)
            
            self.equity_curve.append({'timestamp': timestamp, 'equity': self.current_equity})

            if self.position_size <= 1e-9: # Effectively zero
                self.last_exit_price = price
                self.last_entry_price = self.position_entry_price
                if exit_classification: self.last_exit_reason = exit_classification
                self._reset_position_state()
    
    def _update_current_bar_data(self, timestamp, price, volume):
        """Updates the OHLCV for the current minute bar being formed."""
        if self.current_bar_data['open'] is None:
            self.current_bar_data['open'] = price
            self.current_bar_data['high'] = price
            self.current_bar_data['low'] = price
            self.current_bar_data['timestamp'] = timestamp.replace(second=0, microsecond=0)
        else:
            self.current_bar_data['high'] = max(self.current_bar_data['high'], price)
            self.current_bar_data['low'] = min(self.current_bar_data['low'], price)
        
        self.current_bar_data['close'] = price
        self.current_bar_data['volume'] += volume

    def _close_and_add_bar_to_history(self, bar_timestamp):
        """Finalizes the current bar and adds it to the history."""
        if self.current_bar_data['open'] is None: return

        completed_bar = self.current_bar_data.copy()
        completed_bar['timestamp'] = bar_timestamp
        self._bar_history_list.append(completed_bar)

        if len(self._bar_history_list) > self.max_bar_history_length:
            self._bar_history_list.pop(0)

        self.current_bar_data = {'open': None, 'high': None, 'low': None, 'close': None, 'volume': 0, 'timestamp': None}

    def _update_indicators_on_history(self):
        """Calculates all indicators on the latest completed bar in history."""
        if len(self._bar_history_list) < self.min_bars_for_signals: return

        latest_bar_dict = self._bar_history_list[-1]
        
        if self.use_supertrend: latest_bar_dict['supertrend'] = self._calculate_supertrend_latest()
        if self.use_rsi_filter: latest_bar_dict['rsi'] = self._calculate_rsi_latest()
        if self.use_ema_crossover:
            latest_bar_dict['ema_fast'] = self._calculate_ema_latest(self.fast_ema)
            latest_bar_dict['ema_slow'] = self._calculate_ema_latest(self.slow_ema)
            latest_bar_dict['ema_bull'] = latest_bar_dict['ema_fast'] > latest_bar_dict['ema_slow']
        
        latest_bar_dict['htf_trend'] = self._calculate_ema_latest(20)
        latest_bar_dict['htf_bullish'] = latest_bar_dict['close'] > latest_bar_dict['htf_trend']

    def on_tick(self, tick_timestamp, tick_price, tick_volume):
        """Main entry point for processing a new tick from the WebSocket stream."""
        if tick_timestamp.tzinfo is None:
            tick_timestamp = self.ist_tz.localize(tick_timestamp)

        # --- Bar Aggregation Logic (Improved for Robustness) ---
        current_minute = tick_timestamp.replace(second=0, microsecond=0)

        # Initialize the minute tracker on the very first tick.
        if self.last_processed_minute is None:
            self.last_processed_minute = current_minute

        # If a new minute has started, the previous bar is now complete.
        if current_minute > self.last_processed_minute:
            # 1. Finalize and add the completed bar (from the previous minute) to history.
            self._close_and_add_bar_to_history(self.last_processed_minute)
            
            # 2. Calculate indicators on the newly updated history.
            self._update_indicators_on_history()
            
            # 3. Update the minute tracker to the new minute.
            self.last_processed_minute = current_minute

        # Always update the current (forming) bar with the latest tick data.
        self._update_current_bar_data(tick_timestamp, tick_price, tick_volume)
        
        # --- Real-time Calculations & Position Management ---
        self.current_vwap = self._calculate_vwap_latest(tick_price, tick_volume, tick_timestamp)
        self.current_vwap_bull = tick_price > self.current_vwap if not pd.isna(self.current_vwap) else False

        current_bar_row = {}
        if self._bar_history_list:
            current_bar_row = self._bar_history_list[-1].copy()
        
        has_enough_history = len(self._bar_history_list) >= self.min_bars_for_signals

        # --- ENTRY LOGIC ---
        if self.position_size == 0 and self.should_allow_new_entries(tick_timestamp) and has_enough_history:
            buy_signal = True
            if self.use_supertrend and current_bar_row.get('supertrend') != 1: buy_signal = False
            # FIX: Use the real-time self.current_vwap_bull directly
            if self.use_vwap and not self.current_vwap_bull: buy_signal = False
            if self.use_ema_crossover and not current_bar_row.get('ema_bull'): buy_signal = False
            if self.use_rsi_filter and not (self.rsi_oversold < current_bar_row.get('rsi', 50) < self.rsi_overbought): buy_signal = False
            if not current_bar_row.get('htf_bullish'): buy_signal = False
            
            can_reenter_flag = self.can_reenter(tick_price, tick_timestamp, current_bar_row)
            
            if buy_signal and can_reenter_flag:
                self.enter_position(tick_price, tick_timestamp)
        
        # --- POSITION MANAGEMENT ---
        if self.position_size > 0:
            if self.is_near_session_end(tick_timestamp):
                self.exit_position(tick_price, tick_timestamp, 100, "MANDATORY: Session End", "time")
                self.last_time_exit_date = tick_timestamp.date()
                return

            self.update_trailing_stop(tick_price, tick_timestamp)
            
            stop_hit, stop_reason = self.check_stop_loss_hit(tick_price)
            if stop_hit:
                self.exit_position(tick_price, tick_timestamp, 100, f"MANDATORY: {stop_reason}", stop_reason)
                return
            
            if self.use_tiered_tp:
                entry_price = self.position_entry_price
                if self.tp1_filled == 0 and tick_price >= entry_price + self.tp1_points:
                    self.exit_position(tick_price, tick_timestamp, 50, "TP1-Quick")
                    self.tp1_filled = 1
                
                if self.tp2_filled == 0 and self.tp1_filled > 0 and self.position_size > 0 and tick_price >= entry_price + self.tp2_points:
                    self.exit_position(tick_price, tick_timestamp, 60, "TP2-Medium")
                    self.tp2_filled = 1
                
                if self.tp2_filled > 0 and self.position_size > 0 and tick_price >= entry_price + self.tp3_points:
                    self.exit_position(tick_price, tick_timestamp, 100, "TP3-Runner", "profit")
                    return

    def generate_results(self):
        """Generate strategy results and statistics"""
        if not self.trades:
            return {"error": "No trades executed"}
        
        trades_df = pd.DataFrame(self.trades)
        trades_df['trade_duration'] = trades_df['exit_time'] - trades_df['entry_time']

        equity_df = pd.DataFrame(self.equity_curve)
        
        total_trades = len(trades_df)
        winning_trades = len(trades_df[trades_df['pnl'] > 0])
        win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0
        
        total_pnl = trades_df['pnl'].sum()
        gross_profit = trades_df[trades_df['pnl'] > 0]['pnl'].sum()
        gross_loss = abs(trades_df[trades_df['pnl'] < 0]['pnl'].sum())
        
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        high_water_mark = equity_df['equity'].cummax()
        drawdown = (high_water_mark - equity_df['equity']) / high_water_mark
        max_drawdown = drawdown.max() * 100
        
        final_equity = self.current_equity
        total_return = ((final_equity - self.initial_capital) / self.initial_capital) * 100
        
        return {
            'total_trades': total_trades, 'win_rate': win_rate, 'total_pnl': total_pnl,
            'profit_factor': profit_factor, 'max_drawdown': max_drawdown, 
            'total_return': total_return, 'final_equity': final_equity,
            'trades_df': trades_df, 'equity_df': equity_df
        }
