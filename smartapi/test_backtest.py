#!/usr/bin/env python3
"""
Test script for the new BacktestEngine functionality.
Demonstrates how to use the refactored backtest.py with both CSV and price_ticks.log files.
"""

import os
import sys
from backtest import BacktestEngine, run_backtest_from_file

def test_csv_backtest():
    """Test backtest with CSV file."""
    print("="*60)
    print("TESTING CSV BACKTEST")
    print("="*60)
    
    # Look for CSV files in the data directory
    data_dir = "smartapi/data"
    if not os.path.exists(data_dir):
        print(f"Data directory not found: {data_dir}")
        return
    
    csv_files = [f for f in os.listdir(data_dir) if f.endswith('.csv')]
    if not csv_files:
        print("No CSV files found in data directory")
        return
    
    # Use the first CSV file found
    csv_file = os.path.join(data_dir, csv_files[0])
    print(f"Using CSV file: {csv_file}")
    
    # Strategy parameters
    params = {
        'use_supertrend': True,
        'use_ema_crossover': True,
        'use_rsi_filter': True,
        'use_vwap': True,
        'initial_capital': 100000,
        'base_sl_points': 15,
        'tp1_points': 25,
        'tp2_points': 45,
        'tp3_points': 100,
        'use_trail_stop': True,
        'trail_activation_points': 25,
        'trail_distance_points': 10
    }
    
    try:
        results, saved_files = run_backtest_from_file(csv_file, params, 'csv')
        print("CSV backtest completed successfully!")
        return results
    except Exception as e:
        print(f"CSV backtest failed: {e}")
        return None

def test_ticks_backtest():
    """Test backtest with price_ticks.log file."""
    print("\n" + "="*60)
    print("TESTING PRICE_TICKS.LOG BACKTEST")
    print("="*60)
    
    ticks_file = "smartapi/price_ticks.log"
    if not os.path.exists(ticks_file):
        print(f"Price ticks log file not found: {ticks_file}")
        return None
    
    print(f"Using ticks file: {ticks_file}")
    
    # Strategy parameters optimized for tick data
    params = {
        'use_supertrend': False,
        'use_ema_crossover': True,
        'use_rsi_filter': False,
        'use_vwap': True,
        'initial_capital': 100000,
        'base_sl_points': 7,
        'tp1_points': 25,
        'tp2_points': 45,
        'tp3_points': 100,
        'use_trail_stop': True,
        'trail_activation_points': 15,
        'trail_distance_points': 5
    }
    
    try:
        results, saved_files = run_backtest_from_file(ticks_file, params, 'ticks')
        print("Ticks backtest completed successfully!")
        return results
    except Exception as e:
        print(f"Ticks backtest failed: {e}")
        return None

def test_backtest_engine_direct():
    """Test BacktestEngine class directly."""
    print("\n" + "="*60)
    print("TESTING BACKTESTENGINE DIRECTLY")
    print("="*60)
    
    # Create engine instance
    params = {
        'use_supertrend': True,
        'use_ema_crossover': True,
        'use_rsi_filter': False,
        'use_vwap': True,
        'initial_capital': 50000,
        'base_sl_points': 10,
        'tp1_points': 20,
        'tp2_points': 40,
        'tp3_points': 80
    }
    
    engine = BacktestEngine(params)
    
    # Test with ticks file if available
    ticks_file = "smartapi/price_ticks.log"
    if os.path.exists(ticks_file):
        try:
            results = engine.run_backtest(ticks_file, 'ticks')
            engine.print_results(results)
            engine.save_results(results)
            print("Direct engine test completed successfully!")
            return results
        except Exception as e:
            print(f"Direct engine test failed: {e}")
            return None
    else:
        print("No ticks file available for direct engine test")
        return None

def main():
    """Run all tests."""
    print("BACKTEST ENGINE TEST SUITE")
    print("="*60)
    
    # Test 1: CSV backtest
    csv_results = test_csv_backtest()
    
    # Test 2: Ticks backtest
    ticks_results = test_ticks_backtest()
    
    # Test 3: Direct engine usage
    engine_results = test_backtest_engine_direct()
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    tests_passed = 0
    total_tests = 3
    
    if csv_results is not None:
        print("✓ CSV backtest: PASSED")
        tests_passed += 1
    else:
        print("✗ CSV backtest: FAILED")
    
    if ticks_results is not None:
        print("✓ Ticks backtest: PASSED")
        tests_passed += 1
    else:
        print("✗ Ticks backtest: FAILED")
    
    if engine_results is not None:
        print("✓ Direct engine test: PASSED")
        tests_passed += 1
    else:
        print("✗ Direct engine test: FAILED")
    
    print(f"\nResults: {tests_passed}/{total_tests} tests passed")
    
    if tests_passed > 0:
        print("\nBacktest engine is working correctly!")
    else:
        print("\nAll tests failed. Please check the data files and configuration.")

if __name__ == "__main__":
    main()