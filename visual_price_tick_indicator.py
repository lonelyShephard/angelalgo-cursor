import tkinter as tk
import threading
import time
import os
import re

PRICE_TICK_LOG = "smartapi/price_ticks.log"
APP_LOG_PATH = os.path.join('logs', time.strftime('%Y-%m-%d').replace('-', ''), 'app.log')
# Fallback: try logs/YYYY-MM-DD/app.log, else logs/YYYYMMDD/app.log, else logs/2025-07-04/app.log

LIVE_TRADER_LOG_PATH = "smartapi/live_trader.log"

print("Script started")

print("Looking for log file at:", os.path.abspath(PRICE_TICK_LOG))
print("Exists?", os.path.exists(PRICE_TICK_LOG))

class VisualPriceTickIndicator:
    def __init__(self, initial_capital=100000, log_path='smartapi/price_ticks.log', app_log_path=None):
        self.initial_capital = initial_capital
        self.current_equity = initial_capital
        self.position_active = False
        self.position_entry_price = 0
        self.current_price = 0
        self.position_size = 0
        self.stop_loss = None
        self.log_path = log_path
        self.app_log_path = app_log_path or os.path.join('logs', time.strftime('%Y-%m-%d').replace('-', ''), 'app.log')
        self.latest_tick = ""
        self.root = tk.Tk()
        self.root.title("Bot Status & Price Tick")
        self.root.geometry("400x180")
        self.root.resizable(True, True)
        self.root.attributes('-topmost', True)
        screen_width = self.root.winfo_screenwidth()
        self.root.geometry(f"400x180+{screen_width-420}+20")
        # Remove canvas and use a single label for all info
        self.info_label = tk.Label(
            self.root, text="", font=("Consolas", 16, "bold"), anchor='center', justify='center',
            width=32, height=6, bg='gray', fg='white', relief='flat', borderwidth=0
        )
        self.info_label.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.root.bind('<Configure>', self._on_resize)
        self.current_font_size = 16
        self.is_running = True
        self.update_thread = threading.Thread(target=self._update_loop, daemon=True)
        self.update_thread.start()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
    def _update_loop(self):
        while self.is_running:
            try:
                self.root.after(0, self._update_display)
                time.sleep(1)
            except:
                break
    def _parse_app_log(self):
        # Try to find the latest status line in the app log
        log_path = self.app_log_path
        if not os.path.exists(log_path):
            # fallback to logs/2025-07-04/app.log
            fallback = os.path.join('logs', '2025-07-04', 'app.log')
            if os.path.exists(fallback):
                log_path = fallback
            else:
                return None
        try:
            with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()[-200:]
            for line in reversed(lines):
                if 'STATUS:' in line:
                    if 'In Position' in line:
                        # Example: STATUS: In Position | Size=142, Entry=137.20, Current SL=130.20
                        m = re.search(r'Size=(\d+), Entry=([\d.]+), Current SL=([\d.]+)', line)
                        if m:
                            size = int(m.group(1))
                            entry = float(m.group(2))
                            sl = float(m.group(3))
                            return {'status': 'IN POSITION', 'size': size, 'entry': entry, 'sl': sl}
                    elif 'Awaiting signal' in line:
                        return {'status': 'AWAITING SIGNAL'}
            return None
        except Exception as e:
            return None
    def _update_display(self):
        # Get latest status from live_trader.log
        status_info = parse_live_trader_log()
        # Get latest price tick info
        latest_tick = self._get_latest_tick()
        # Extract price and volume from latest_tick
        price = '-'
        volume = '-'
        try:
            for line in latest_tick.split('\n'):
                if line.startswith('Price:'):
                    price = float(line.split(':', 1)[1].strip())
                if line.startswith('Volume:'):
                    volume = line.split(':', 1)[1].strip()
        except Exception:
            pass
        # Compose info
        if status_info is None:
            status = "AWAITING SIGNAL"
            symbol = '-'
            entry = '-'
            sl = '-'
            bg_color = 'gray'
            self.position_active = False
        elif status_info['status'] == 'API DOWN':
            status = "API DOWN"
            symbol = status_info.get('symbol', '-')
            entry = '-'
            sl = '-'
            bg_color = 'yellow'
            self.position_active = False
        elif status_info['status'] == 'IN POSITION':
            status = "IN POSITION"
            symbol = status_info.get('symbol', '-')
            entry = status_info['entry']
            sl = status_info['sl']
            self.position_active = True
            self.position_entry_price = float(entry)
            self.stop_loss = float(sl)
            try:
                current_price = float(price)
            except Exception:
                current_price = self.position_entry_price
            self.current_price = current_price
            in_profit = self.current_price > self.position_entry_price
            bg_color = 'green' if in_profit else 'red'
        elif status_info['status'] == 'COLLECTING DATA':
            status = "COLLECTING DATA"
            symbol = status_info.get('symbol', '-')
            entry = '-'
            sl = '-'
            bg_color = 'orange'
            self.position_active = False
        else:
            status = "AWAITING SIGNAL"
            symbol = status_info.get('symbol', '-')
            entry = '-'
            sl = '-'
            bg_color = 'gray'
            self.position_active = False
        # Transposed table: Parameter | Value
        table = (
            f"+-------------------+-------------------+\n"
            f"| {'Parameter':<17} | {'Value':<17} |\n"
            f"+-------------------+-------------------+\n"
            f"| {'Status':<17} | {str(status):<17} |\n"
            f"| {'Symbol':<17} | {str(symbol):<17} |\n"
            f"| {'Entry':<17} | {str(entry):<17} |\n"
            f"| {'SL':<17} | {str(sl):<17} |\n"
            f"| {'Price':<17} | {str(price):<17} |\n"
            f"| {'Volume':<17} | {str(volume):<17} |\n"
            f"+-------------------+-------------------+"
        )
        self.info_label.config(text=table, bg=bg_color, font=("Consolas", self.current_font_size, "bold"))
        self.root.config(bg=bg_color)
    def _on_resize(self, event):
        # Use the label's height for font size calculation, but scale more moderately
        label_height = self.info_label.winfo_height()
        new_size = max(12, min(36, int(label_height / 12)))
        if new_size != self.current_font_size:
            self.current_font_size = new_size
            self.info_label.config(font=("Consolas", self.current_font_size, "bold"))
    def _get_latest_tick(self):
        try:
            if os.path.exists(self.log_path):
                with open(self.log_path, "r", encoding="utf-8", errors="ignore") as f:
                    f.seek(0, os.SEEK_END)
                    filesize = f.tell()
                    blocksize = 1024
                    if filesize == 0:
                        return "No price data"
                    seekpos = max(filesize - blocksize, 0)
                    f.seek(seekpos)
                    lines = f.read().splitlines()
                    # Find the last non-empty line
                    for last in reversed(lines):
                        if last.strip():
                            break
                    else:
                        return "No price data"
                    parts = [p.strip() for p in last.split(',')]
                    dt = parts[0] if len(parts) > 0 else "N/A"
                    price = parts[1] if len(parts) > 1 else "N/A"
                    volume = parts[2] if len(parts) > 2 else "N/A"
                    # Split dt into date and time if possible
                    if 'T' in dt:
                        date_part, time_part = dt.split('T', 1)
                        # Remove timezone suffix like +5:30 if present
                        if '+' in time_part:
                            time_part = time_part.split('+')[0]
                        elif '-' in time_part and time_part.count(':') > 1:
                            # Handles cases like 12:34:56-05:00
                            time_part = time_part.split('-')[0]
                    else:
                        date_part, time_part = dt, ''
                    return f"Date: {date_part}\nTime: {time_part}\nPrice: {price}\nVolume: {volume}"
        except Exception as e:
            return f"Log error: {e}"
        return "No price data"
    def update_position(self, position_size, entry_price, current_price, current_equity):
        self.position_size = position_size
        self.position_entry_price = entry_price
        self.current_price = current_price
        self.current_equity = current_equity
        self.position_active = position_size != 0
    def clear_position(self):
        self.position_active = False
        self.position_size = 0
        self.position_entry_price = 0
    def update_equity(self, current_equity):
        self.current_equity = current_equity
    def show_message(self, message, color='blue'):
        self.info_label.config(text=message, bg=color)
        self.root.config(bg=color)
    def close(self):
        self.is_running = False
        self.root.quit()
        self.root.destroy()
    def run(self):
        self.root.mainloop()
_visual_indicator = None
def get_visual_price_tick_indicator(initial_capital=100000, log_path='smartapi/price_ticks.log'):
    global _visual_indicator
    if _visual_indicator is None:
        _visual_indicator = VisualPriceTickIndicator(initial_capital, log_path)
    return _visual_indicator
def start_visual_price_tick_indicator(initial_capital=100000, log_path='smartapi/price_ticks.log'):
    indicator = get_visual_price_tick_indicator(initial_capital, log_path)
    indicator_thread = threading.Thread(target=indicator.run, daemon=True)
    indicator_thread.start()
    return indicator
def update_visual_position(position_size, entry_price, current_price, current_equity):
    indicator = get_visual_price_tick_indicator()
    if indicator:
        indicator.update_position(position_size, entry_price, current_price, current_equity)
def clear_visual_position():
    indicator = get_visual_price_tick_indicator()
    if indicator:
        indicator.clear_position()
def update_visual_equity(current_equity):
    indicator = get_visual_price_tick_indicator()
    if indicator:
        indicator.update_equity(current_equity)
def show_visual_message(message, color='blue'):
    indicator = get_visual_price_tick_indicator()
    if indicator:
        indicator.show_message(message, color)
def close_visual_indicator():
    global _visual_indicator
    if _visual_indicator:
        _visual_indicator.close()
        _visual_indicator = None

def parse_live_trader_log(log_path=None):
    """
    Parse the live trader log to get current status.
    Robustly determine websocket connection status by comparing the most recent 'WebSocket Connection Opened' and 'WebSocket Connection Closed' events.
    If the most recent event is 'Opened', consider the websocket connected.
    If neither event is found but there are recent ticks, consider the API up.
    Only show API DOWN if the most recent event is 'Closed' and there are no recent ticks.
    """
    import re
    from datetime import datetime
    # Try to find the current daily log file first
    current_date = time.strftime('%Y-%m-%d')
    daily_log_path = os.path.join('logs', current_date, 'app.log')
    
    # If daily log doesn't exist, try the fallback path
    if not os.path.exists(daily_log_path):
        daily_log_path = os.path.join('logs', current_date.replace('-', ''), 'app.log')
    
    # If still doesn't exist, use the original live_trader.log
    if not os.path.exists(daily_log_path):
        daily_log_path = log_path or LIVE_TRADER_LOG_PATH
    
    if not os.path.exists(daily_log_path):
        return None
    
    try:
        with open(daily_log_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()[-200:]  # Only check last 200 lines for speed
        
        # Find the most recent WebSocket Connection Opened/Closed events
        last_opened_time = None
        last_closed_time = None
        for line in reversed(lines):
            if 'WebSocket Connection Opened' in line:
                if '[' in line and ']' in line:
                    timestamp_str = line[line.find('[')+1:line.find(']')]
                    try:
                        log_time = datetime.strptime(timestamp_str, '%y%m%d %H:%M:%S')
                        if last_opened_time is None or log_time > last_opened_time:
                            last_opened_time = log_time
                    except:
                        continue
            elif 'WebSocket Connection Closed' in line:
                if '[' in line and ']' in line:
                    timestamp_str = line[line.find('[')+1:line.find(']')]
                    try:
                        log_time = datetime.strptime(timestamp_str, '%y%m%d %H:%M:%S')
                        if last_closed_time is None or log_time > last_closed_time:
                            last_closed_time = log_time
                    except:
                        continue
        # Determine websocket_connected by comparing last_opened_time and last_closed_time
        websocket_connected = False
        if last_opened_time and (not last_closed_time or last_opened_time > last_closed_time):
            websocket_connected = True
        elif last_closed_time and (not last_opened_time or last_closed_time > last_opened_time):
            websocket_connected = False
        # If neither event is found, leave websocket_connected as False for now
        # Check for recent activity (if no ticks in last 2 minutes, API might be down)
        current_time = time.time()
        last_tick_time = None
        # Check price_ticks.log for recent activity
        if os.path.exists(PRICE_TICK_LOG):
            try:
                with open(PRICE_TICK_LOG, 'r', encoding='utf-8', errors='ignore') as f:
                    f.seek(0, os.SEEK_END)
                    filesize = f.tell()
                    if filesize > 0:
                        # Read last few lines to find last tick
                        f.seek(max(filesize - 2048, 0))
                        last_lines = f.read().splitlines()
                        for line in reversed(last_lines):
                            if line.strip() and ',' in line:
                                try:
                                    timestamp_str = line.split(',')[0]
                                    if 'T' in timestamp_str:
                                        tick_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                                        last_tick_time = tick_time.timestamp()
                                        break
                                except:
                                    continue
            except:
                pass
        # If there are recent ticks (within 2 minutes), consider API UP regardless of websocket_connected
        if last_tick_time and (current_time - last_tick_time) <= 120:
            websocket_connected = True
        # If neither websocket is connected nor recent ticks, consider API down
        if not websocket_connected:
            reason = 'No Recent Data' if not last_tick_time or (current_time - last_tick_time) > 120 else 'Connection Lost'
            return {'status': 'API DOWN', 'symbol': 'Unknown', 'reason': reason}
        # Parse normal status messages
        for line in reversed(lines):
            if 'STATUS:' in line:
                if 'In Position' in line:
                    # Extract symbol, size, entry, and SL
                    symbol_match = re.search(r'Symbol=([^,]+)', line)
                    size_match = re.search(r'Size=(\d+)', line)
                    entry_match = re.search(r'Entry=([\d.]+)', line)
                    sl_match = re.search(r'Current SL=([\d.]+)', line)
                    if size_match and entry_match and sl_match:
                        size = int(size_match.group(1))
                        entry = float(entry_match.group(1))
                        sl = float(sl_match.group(1))
                        symbol = symbol_match.group(1) if symbol_match else 'Unknown'
                        return {'status': 'IN POSITION', 'symbol': symbol, 'size': size, 'entry': entry, 'sl': sl}
                elif 'Awaiting signal' in line:
                    # Extract symbol from awaiting signal message
                    symbol_match = re.search(r'Symbol=([^,]+)', line)
                    symbol = symbol_match.group(1) if symbol_match else 'Unknown'
                    return {'status': 'AWAITING SIGNAL', 'symbol': symbol}
                elif 'Collecting initial bar data' in line:
                    # Extract symbol from collecting data message
                    symbol_match = re.search(r'Symbol=([^,]+)', line)
                    symbol = symbol_match.group(1) if symbol_match else 'Unknown'
                    return {'status': 'COLLECTING DATA', 'symbol': symbol}
        # If no status found but we have recent ticks, assume awaiting signal
        if last_tick_time and (current_time - last_tick_time) <= 120:
            return {'status': 'AWAITING SIGNAL', 'symbol': 'Unknown'}
        return None
    except Exception as e:
        print(f"Error parsing log file {daily_log_path}: {e}")
        return None

if __name__ == "__main__":
    import sys
    initial_capital = 100000
    log_path = "smartapi/price_ticks.log"
    if len(sys.argv) > 1:
        try:
            initial_capital = int(sys.argv[1])
        except Exception:
            pass
    if len(sys.argv) > 2:
        log_path = sys.argv[2]
    indicator = VisualPriceTickIndicator(initial_capital=initial_capital, log_path=log_path)
    indicator.run() 