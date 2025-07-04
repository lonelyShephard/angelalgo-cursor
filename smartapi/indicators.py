import pandas as pd
import numpy as np
from abc import ABC, abstractmethod
from datetime import datetime
import pytz


class Indicator(ABC):
    """Base abstract class for all indicators."""
    
    def __init__(self, name, enabled=True):
        self.name = name
        self.enabled = enabled
        self.value = np.nan
        self.last_update = None
    
    @abstractmethod
    def calculate(self, data):
        """Calculate the indicator value. Must be implemented by subclasses."""
        pass
    
    def get_value(self):
        """Get the current indicator value."""
        return self.value
    
    def is_enabled(self):
        """Check if the indicator is enabled."""
        return self.enabled
    
    def enable(self):
        """Enable the indicator."""
        self.enabled = True
    
    def disable(self):
        """Disable the indicator."""
        self.enabled = False


class BarIndicator(Indicator):
    """Base class for indicators that are calculated on historical bar data."""
    
    def __init__(self, name, min_bars_required, enabled=True):
        super().__init__(name, enabled)
        self.min_bars_required = min_bars_required
    
    def can_calculate(self, bar_history):
        """Check if we have enough bars to calculate this indicator."""
        return len(bar_history) >= self.min_bars_required
    
    def calculate(self, bar_history):
        """Calculate indicator on bar history data."""
        if not self.enabled or not self.can_calculate(bar_history):
            return np.nan
        
        self.value = self._calculate_impl(bar_history)
        self.last_update = datetime.now()
        return self.value
    
    @abstractmethod
    def _calculate_impl(self, bar_history):
        """Internal calculation method. Must be implemented by subclasses."""
        pass


class TickIndicator(Indicator):
    """Base class for indicators that are calculated on real-time tick data."""
    
    def __init__(self, name, enabled=True):
        super().__init__(name, enabled)
        self._state = {}
    
    def calculate(self, tick_data):
        """Calculate indicator on tick data."""
        if not self.enabled:
            return np.nan
        
        self.value = self._calculate_impl(tick_data)
        self.last_update = datetime.now()
        return self.value
    
    @abstractmethod
    def _calculate_impl(self, tick_data):
        """Internal calculation method. Must be implemented by subclasses."""
        pass
    
    def reset_state(self):
        """Reset the indicator's internal state."""
        self._state = {}


class SupertrendIndicator(BarIndicator):
    """Supertrend indicator implementation."""
    
    def __init__(self, atr_length=10, atr_multiplier=3.0, enabled=True):
        super().__init__("Supertrend", atr_length + 1, enabled)
        self.atr_length = atr_length
        self.atr_multiplier = atr_multiplier
        self.trend = 1
        self.final_upperband = None
        self.final_lowerband = None
    
    def _calculate_impl(self, bar_history):
        """Calculate Supertrend value."""
        if len(bar_history) < self.atr_length + 1:
            return self.trend
        
        # Convert to DataFrame for easier calculations
        df = pd.DataFrame(bar_history)
        current_bar = df.iloc[-1]
        
        # Calculate ATR
        atr = self._calculate_atr(df)
        if pd.isna(atr):
            return self.trend
        
        # Calculate Supertrend bands
        hlc3 = (current_bar['high'] + current_bar['low'] + current_bar['close']) / 3
        upperband = hlc3 + self.atr_multiplier * atr
        lowerband = hlc3 - self.atr_multiplier * atr
        
        # Initialize bands if needed
        if self.final_upperband is None or self.final_lowerband is None:
            self.final_upperband = upperband
            self.final_lowerband = lowerband
        
        # Update bands based on price action
        if current_bar['close'] > self.final_upperband:
            self.final_upperband = lowerband
        else:
            self.final_upperband = min(upperband, self.final_upperband)
        
        if current_bar['close'] < self.final_lowerband:
            self.final_lowerband = upperband
        else:
            self.final_lowerband = max(lowerband, self.final_lowerband)
        
        # Update trend
        if self.trend == 1 and current_bar['close'] < self.final_lowerband:
            self.trend = -1
        elif self.trend == -1 and current_bar['close'] > self.final_upperband:
            self.trend = 1
        
        return self.trend
    
    def _calculate_atr(self, df):
        """Calculate Average True Range."""
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        
        true_range = np.maximum(high_low, np.maximum(high_close, low_close))
        atr = true_range.rolling(window=self.atr_length).mean().iloc[-1]
        return atr
    
    def reset_state(self):
        """Reset Supertrend state."""
        self.trend = 1
        self.final_upperband = None
        self.final_lowerband = None


class EMAIndicator(BarIndicator):
    """Exponential Moving Average indicator."""
    
    def __init__(self, period, enabled=True):
        super().__init__(f"EMA_{period}", period, enabled)
        self.period = period
    
    def _calculate_impl(self, bar_history):
        """Calculate EMA value."""
        df = pd.DataFrame(bar_history)
        series = df['close'].tail(self.period * 2)
        return series.ewm(span=self.period, adjust=False).mean().iloc[-1]


class RSIIndicator(BarIndicator):
    """Relative Strength Index indicator."""
    
    def __init__(self, length=14, enabled=True):
        super().__init__(f"RSI_{length}", length + 1, enabled)
        self.length = length
    
    def _calculate_impl(self, bar_history):
        """Calculate RSI value."""
        df = pd.DataFrame(bar_history)
        series = df['close'].tail(self.length * 2)
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.length).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.length).mean()
        
        # Fix the RSI calculation to handle division by zero properly
        rs = gain / loss
        # Replace infinite values with 0 for RSI calculation
        rs = rs.replace([np.inf, -np.inf], 0)
        rsi = 100 - (100 / (1 + rs))
        return rsi.iloc[-1]


class VWAPIndicator(TickIndicator):
    """Volume Weighted Average Price indicator for real-time calculation."""
    
    def __init__(self, enabled=True):
        super().__init__("VWAP", enabled)
        self.daily_sum_tpv = 0.0
        self.daily_sum_volume = 0.0
        self.last_vwap_day = None
    
    def _calculate_impl(self, tick_data):
        """Calculate VWAP value."""
        current_price = tick_data['price']
        current_volume = tick_data['volume']
        current_timestamp = tick_data['timestamp']
        
        # Reset daily values if it's a new day
        current_day = current_timestamp.date()
        if self.last_vwap_day is None or current_day != self.last_vwap_day:
            self.daily_sum_tpv = 0.0
            self.daily_sum_volume = 0.0
            self.last_vwap_day = current_day
        
        # Update daily sums
        self.daily_sum_tpv += current_price * current_volume
        self.daily_sum_volume += current_volume
        
        # Calculate VWAP
        if self.daily_sum_volume > 0:
            return self.daily_sum_tpv / self.daily_sum_volume
        return np.nan
    
    def reset_state(self):
        """Reset VWAP state."""
        super().reset_state()
        self.daily_sum_tpv = 0.0
        self.daily_sum_volume = 0.0
        self.last_vwap_day = None


class ATRIndicator(BarIndicator):
    """Average True Range indicator."""
    
    def __init__(self, length=14, enabled=True):
        super().__init__(f"ATR_{length}", length + 1, enabled)
        self.length = length
    
    def _calculate_impl(self, bar_history):
        """Calculate ATR value."""
        df = pd.DataFrame(bar_history)
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        
        true_range = np.maximum(high_low, np.maximum(high_close, low_close))
        atr = true_range.rolling(window=self.length).mean().iloc[-1]
        return atr


class HTFTrendIndicator(BarIndicator):
    """Higher Timeframe Trend indicator (using EMA)."""
    
    def __init__(self, period=20, enabled=True):
        super().__init__(f"HTF_Trend_{period}", period, enabled)
        self.period = period
    
    def _calculate_impl(self, bar_history):
        """Calculate HTF trend value."""
        df = pd.DataFrame(bar_history)
        series = df['close'].tail(self.period * 2)
        return series.ewm(span=self.period, adjust=False).mean().iloc[-1]