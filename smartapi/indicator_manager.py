import pandas as pd
import numpy as np
from datetime import datetime
from typing import Optional, List, Dict, Any, Union
from .indicators import (
    SupertrendIndicator, EMAIndicator, RSIIndicator, VWAPIndicator,
    ATRIndicator, HTFTrendIndicator
)


class IndicatorManager:
    """Manages all indicators and their calculations."""
    
    def __init__(self, strategy_params: Dict[str, Any]):
        """Initialize the indicator manager with strategy parameters."""
        self.indicators: Dict[str, Any] = {}
        self.bar_history: List[Dict[str, Any]] = []
        self.current_bar_data: Dict[str, Any] = {
            'open': None, 'high': None, 'low': None, 'close': None, 
            'volume': 0, 'timestamp': None
        }
        self.last_processed_minute: Optional[datetime] = None
        self.max_bar_history_length = 100
        
        # Initialize indicators based on strategy parameters
        self._initialize_indicators(strategy_params)
    
    def _initialize_indicators(self, params: Dict[str, Any]) -> None:
        """Initialize indicators based on strategy parameters."""
        # Supertrend indicator
        if params.get('use_supertrend', True):
            self.indicators['supertrend'] = SupertrendIndicator(
                atr_length=params.get('atr_len', 10),
                atr_multiplier=params.get('atr_mult', 3.0),
                enabled=True
            )
        
        # VWAP indicator (tick-based)
        if params.get('use_vwap', True):
            self.indicators['vwap'] = VWAPIndicator(enabled=True)
        
        # EMA indicators
        if params.get('use_ema_crossover', True):
            self.indicators['ema_fast'] = EMAIndicator(
                period=params.get('fast_ema', 9),
                enabled=True
            )
            self.indicators['ema_slow'] = EMAIndicator(
                period=params.get('slow_ema', 21),
                enabled=True
            )
        
        # RSI indicator
        if params.get('use_rsi_filter', True):
            self.indicators['rsi'] = RSIIndicator(
                length=params.get('rsi_length', 14),
                enabled=True
            )
        
        # HTF Trend indicator
        self.indicators['htf_trend'] = HTFTrendIndicator(
            period=20,
            enabled=True
        )
        
        # ATR indicator (for reference)
        self.indicators['atr'] = ATRIndicator(
            length=params.get('atr_len', 10),
            enabled=True
        )
    
    def update_current_bar(self, timestamp: datetime, price: float, volume: int) -> None:
        """Update the current bar being formed."""
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
    
    def close_current_bar(self, bar_timestamp: datetime) -> None:
        """Close the current bar and add it to history."""
        if self.current_bar_data['open'] is None:
            return
        
        completed_bar = self.current_bar_data.copy()
        completed_bar['timestamp'] = bar_timestamp
        self.bar_history.append(completed_bar)
        
        # Maintain history length
        if len(self.bar_history) > self.max_bar_history_length:
            self.bar_history.pop(0)
        
        # Reset current bar
        self.current_bar_data = {
            'open': None, 'high': None, 'low': None, 'close': None, 
            'volume': 0, 'timestamp': None
        }
        
        # Calculate bar-based indicators
        self._calculate_bar_indicators()
    
    def _calculate_bar_indicators(self) -> None:
        """Calculate all bar-based indicators on the latest completed bar."""
        if not self.bar_history:
            return
        
        # Calculate each bar-based indicator
        for name, indicator in self.indicators.items():
            if hasattr(indicator, 'can_calculate') and indicator.can_calculate(self.bar_history):
                value = indicator.calculate(self.bar_history)
                # Store the value in the latest bar
                self.bar_history[-1][name] = value
    
    def update_tick_indicators(self, timestamp: datetime, price: float, volume: int) -> float:
        """Update tick-based indicators."""
        tick_data = {
            'price': price,
            'volume': volume,
            'timestamp': timestamp
        }
        
        # Update VWAP
        if 'vwap' in self.indicators:
            vwap_value = self.indicators['vwap'].calculate(tick_data)
            return vwap_value
        
        return np.nan
    
    def get_indicator_value(self, indicator_name: str) -> float:
        """Get the current value of a specific indicator."""
        if indicator_name in self.indicators:
            return self.indicators[indicator_name].get_value()
        return np.nan
    
    def get_latest_bar_data(self) -> Dict[str, Any]:
        """Get the latest completed bar data with all indicator values."""
        if self.bar_history:
            return self.bar_history[-1].copy()
        return {}
    
    def get_bar_history(self) -> List[Dict[str, Any]]:
        """Get the complete bar history."""
        return self.bar_history.copy()
    
    def get_bar_history_df(self) -> pd.DataFrame:
        """Get bar history as a pandas DataFrame."""
        if not self.bar_history:
            return pd.DataFrame(columns=['open', 'high', 'low', 'close', 'volume'])
        
        df = pd.DataFrame(self.bar_history)
        if 'timestamp' in df.columns:
            df.set_index('timestamp', inplace=True)
            df.index = pd.to_datetime(df.index)
        return df
    
    def has_enough_history(self, min_bars: int) -> bool:
        """Check if we have enough bar history."""
        return len(self.bar_history) >= min_bars
    
    def reset_all_indicators(self) -> None:
        """Reset all indicators to their initial state."""
        for indicator in self.indicators.values():
            if hasattr(indicator, 'reset_state'):
                indicator.reset_state()
        
        self.bar_history = []
        self.current_bar_data = {
            'open': None, 'high': None, 'low': None, 'close': None, 
            'volume': 0, 'timestamp': None
        }
        self.last_processed_minute = None
    
    def get_enabled_indicators(self) -> List[str]:
        """Get list of enabled indicators."""
        return [name for name, indicator in self.indicators.items() if indicator.is_enabled()]
    
    def enable_indicator(self, indicator_name: str) -> None:
        """Enable a specific indicator."""
        if indicator_name in self.indicators:
            self.indicators[indicator_name].enable()
    
    def disable_indicator(self, indicator_name: str) -> None:
        """Disable a specific indicator."""
        if indicator_name in self.indicators:
            self.indicators[indicator_name].disable()
    
    def add_indicator(self, name: str, indicator: Any) -> None:
        """Add a new indicator to the manager."""
        self.indicators[name] = indicator
    
    def remove_indicator(self, name: str) -> None:
        """Remove an indicator from the manager."""
        if name in self.indicators:
            del self.indicators[name]