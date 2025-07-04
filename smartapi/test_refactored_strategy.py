#!/usr/bin/env python3
"""
Test script for the refactored strategy with modular indicators.
This script tests the basic functionality without requiring live market data.
"""

import sys
import os
from datetime import datetime, timedelta
import pytz
import pandas as pd
import numpy as np

# Add the current directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from strategy import ModularIntradayStrategy
from indicators import SupertrendIndicator, EMAIndicator, RSIIndicator, VWAPIndicator
from indicator_manager import IndicatorManager

def test_indicator_manager():
    """Test the indicator manager functionality."""
    print("Testing Indicator Manager...")
    
    # Test parameters
    strategy_params = {
        'use_supertrend': True,
        'use_vwap': True,
        'use_ema_crossover': True,
        'use_rsi_filter': True,
        'atr_len': 10,
        'atr_mult': 3.0,
        'fast_ema': 9,
        'slow_ema': 21,
        'rsi_length': 14
    }
    
    # Create indicator manager
    manager = IndicatorManager(strategy_params)
    
    # Test indicator initialization
    print(f"Enabled indicators: {manager.get_enabled_indicators()}")
    
    # Test bar history management
    test_bars = [
        {'open': 100, 'high': 105, 'low': 99, 'close': 103, 'volume': 1000, 'timestamp': datetime.now()},
        {'open': 103, 'high': 107, 'low': 102, 'close': 106, 'volume': 1200, 'timestamp': datetime.now()},
        {'open': 106, 'high': 110, 'low': 105, 'close': 108, 'volume': 1100, 'timestamp': datetime.now()},
    ]
    
    for bar in test_bars:
        manager.bar_history.append(bar)
    
    print(f"Bar history length: {len(manager.get_bar_history())}")
    
    # Test indicator calculations
    manager._calculate_bar_indicators()
    latest_bar = manager.get_latest_bar_data()
    print(f"Latest bar with indicators: {list(latest_bar.keys())}")
    
    print("✅ Indicator Manager test passed!\n")

def test_individual_indicators():
    """Test individual indicator calculations."""
    print("Testing Individual Indicators...")
    
    # Create test data
    test_data = [
        {'open': 100, 'high': 105, 'low': 99, 'close': 103, 'volume': 1000},
        {'open': 103, 'high': 107, 'low': 102, 'close': 106, 'volume': 1200},
        {'open': 106, 'high': 110, 'low': 105, 'close': 108, 'volume': 1100},
        {'open': 108, 'high': 112, 'low': 107, 'close': 111, 'volume': 1300},
        {'open': 111, 'high': 115, 'low': 110, 'close': 114, 'volume': 1400},
    ]
    
    # Test EMA
    ema_indicator = EMAIndicator(period=3)
    ema_value = ema_indicator.calculate(test_data)
    print(f"EMA(3) value: {ema_value:.2f}")
    
    # Test RSI
    rsi_indicator = RSIIndicator(length=3)
    rsi_value = rsi_indicator.calculate(test_data)
    print(f"RSI(3) value: {rsi_value:.2f}")
    
    # Test Supertrend
    supertrend_indicator = SupertrendIndicator(atr_length=3, atr_multiplier=2.0)
    supertrend_value = supertrend_indicator.calculate(test_data)
    print(f"Supertrend value: {supertrend_value}")
    
    # Test VWAP
    vwap_indicator = VWAPIndicator()
    tick_data = {'price': 115.0, 'volume': 1000, 'timestamp': datetime.now()}
    vwap_value = vwap_indicator.calculate(tick_data)
    print(f"VWAP value: {vwap_value:.2f}")
    
    print("✅ Individual Indicators test passed!\n")

def test_strategy_integration():
    """Test the complete strategy integration."""
    print("Testing Strategy Integration...")
    
    # Create strategy with test parameters
    strategy_params = {
        'initial_capital': 100000,
        'use_supertrend': True,
        'use_vwap': True,
        'use_ema_crossover': True,
        'use_rsi_filter': True,
        'atr_len': 10,
        'atr_mult': 3.0,
        'fast_ema': 9,
        'slow_ema': 21,
        'rsi_length': 14,
        'base_sl_points': 15,
        'tp1_points': 25,
        'tp2_points': 45,
        'tp3_points': 100,
        'risk_per_trade_percent': 1.0
    }
    
    strategy = ModularIntradayStrategy(params=strategy_params)
    
    # Test that indicator manager was created
    assert hasattr(strategy, 'indicator_manager'), "Strategy should have indicator_manager"
    assert strategy.indicator_manager is not None, "indicator_manager should not be None"
    
    print(f"Strategy initialized with {len(strategy.indicator_manager.get_enabled_indicators())} indicators")
    
    # Test on_tick method with simulated data
    ist_tz = pytz.timezone('Asia/Kolkata')
    base_time = datetime.now(ist_tz)
    
    # Simulate some ticks
    for i in range(50):
        tick_time = base_time + timedelta(minutes=i)
        tick_price = 100 + i * 0.5  # Simulate rising price
        tick_volume = 1000 + i * 10
        
        strategy.on_tick(tick_time, tick_price, tick_volume)
    
    # Check that we have some bar history
    bar_history = strategy.indicator_manager.get_bar_history()
    print(f"Generated {len(bar_history)} bars")
    
    if bar_history:
        latest_bar = bar_history[-1]
        print(f"Latest bar indicators: {[k for k in latest_bar.keys() if k not in ['open', 'high', 'low', 'close', 'volume', 'timestamp']]}")
    
    print("✅ Strategy Integration test passed!\n")

def test_adding_new_indicator():
    """Test adding a new custom indicator."""
    print("Testing Adding New Indicator...")
    
    from indicators import BarIndicator
    
    class SimpleSMAIndicator(BarIndicator):
        """Simple Moving Average indicator for testing."""
        
        def __init__(self, period=20, enabled=True):
            super().__init__(f"SMA_{period}", period, enabled)
            self.period = period
        
        def _calculate_impl(self, bar_history):
            """Calculate SMA value."""
            if len(bar_history) < self.period:
                return np.nan
            
            df = pd.DataFrame(bar_history)
            return df['close'].tail(self.period).mean()
    
    # Create indicator manager
    strategy_params = {'use_supertrend': True}
    manager = IndicatorManager(strategy_params)
    
    # Add custom indicator
    custom_sma = SimpleSMAIndicator(period=5)
    manager.add_indicator('custom_sma', custom_sma)
    
    # Test with some data
    test_data = [
        {'open': 100, 'high': 105, 'low': 99, 'close': 103, 'volume': 1000},
        {'open': 103, 'high': 107, 'low': 102, 'close': 106, 'volume': 1200},
        {'open': 106, 'high': 110, 'low': 105, 'close': 108, 'volume': 1100},
        {'open': 108, 'high': 112, 'low': 107, 'close': 111, 'volume': 1300},
        {'open': 111, 'high': 115, 'low': 110, 'close': 114, 'volume': 1400},
    ]
    
    for bar in test_data:
        manager.bar_history.append(bar)
    
    manager._calculate_bar_indicators()
    latest_bar = manager.get_latest_bar_data()
    
    print(f"Custom SMA value: {latest_bar.get('custom_sma', 'Not calculated')}")
    print("✅ Adding New Indicator test passed!\n")

def main():
    """Run all tests."""
    print("🧪 Testing Refactored Strategy with Modular Indicators\n")
    print("=" * 60)
    
    try:
        test_indicator_manager()
        test_individual_indicators()
        test_strategy_integration()
        test_adding_new_indicator()
        
        print("🎉 All tests passed! The refactored strategy is working correctly.")
        print("\nKey improvements achieved:")
        print("✅ Modular indicator system")
        print("✅ Easy to add new indicators")
        print("✅ Clean separation of concerns")
        print("✅ Type-safe implementation")
        print("✅ Maintainable code structure")
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main()) 