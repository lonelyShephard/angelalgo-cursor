#!/usr/bin/env python3
"""
Test script to verify status parsing from log files.
"""

import os
import time
import re
from visual_price_tick_indicator import parse_live_trader_log

def test_status_parsing():
    """Test the status parsing function."""
    print("Testing Status Parsing")
    print("="*50)
    
    # Test the parsing function
    status_info = parse_live_trader_log()
    
    if status_info is None:
        print("❌ No status information found")
        print("This could mean:")
        print("  - No log files exist")
        print("  - No STATUS messages in log files")
        print("  - Log file format is different")
        return False
    
    print("✅ Status information found:")
    print(f"  Status: {status_info['status']}")
    print(f"  Symbol: {status_info.get('symbol', 'N/A')}")
    
    if status_info['status'] == 'IN POSITION':
        print(f"  Size: {status_info.get('size', 'N/A')}")
        print(f"  Entry: {status_info.get('entry', 'N/A')}")
        print(f"  Stop Loss: {status_info.get('sl', 'N/A')}")
    
    return True

def check_log_files():
    """Check what log files exist."""
    print("\nChecking Log Files")
    print("="*50)
    
    # Check live_trader.log
    live_trader_log = "smartapi/live_trader.log"
    if os.path.exists(live_trader_log):
        print(f"✅ {live_trader_log} exists")
        with open(live_trader_log, 'r') as f:
            lines = f.readlines()
            status_lines = [line for line in lines if 'STATUS:' in line]
            print(f"   Contains {len(status_lines)} STATUS lines")
    else:
        print(f"❌ {live_trader_log} not found")
    
    # Check daily log files
    current_date = time.strftime('%Y-%m-%d')
    daily_log = os.path.join('logs', current_date, 'app.log')
    if os.path.exists(daily_log):
        print(f"✅ {daily_log} exists")
        with open(daily_log, 'r') as f:
            lines = f.readlines()
            status_lines = [line for line in lines if 'STATUS:' in line]
            print(f"   Contains {len(status_lines)} STATUS lines")
            
            # Show last few status lines
            if status_lines:
                print("   Last STATUS lines:")
                for line in status_lines[-3:]:
                    print(f"     {line.strip()}")
    else:
        print(f"❌ {daily_log} not found")
        
        # Try alternative format
        alt_daily_log = os.path.join('logs', current_date.replace('-', ''), 'app.log')
        if os.path.exists(alt_daily_log):
            print(f"✅ {alt_daily_log} exists")
            with open(alt_daily_log, 'r') as f:
                lines = f.readlines()
                status_lines = [line for line in lines if 'STATUS:' in line]
                print(f"   Contains {len(status_lines)} STATUS lines")
                
                # Show last few status lines
                if status_lines:
                    print("   Last STATUS lines:")
                    for line in status_lines[-3:]:
                        print(f"     {line.strip()}")
        else:
            print(f"❌ {alt_daily_log} not found")

def main():
    """Run all tests."""
    print("STATUS PARSING TEST SUITE")
    print("="*50)
    
    # Check log files first
    check_log_files()
    
    # Test status parsing
    print("\n" + "="*50)
    success = test_status_parsing()
    
    if success:
        print("\n✅ Status parsing is working correctly!")
        print("The visual indicator should now show the correct status.")
    else:
        print("\n❌ Status parsing failed!")
        print("Please check the log files and their format.")

if __name__ == "__main__":
    main() 