import tkinter as tk
import threading
import time
import os

PRICE_TICK_LOG = "smartapi/price_ticks.log"

print("Script started")

print("Looking for log file at:", os.path.abspath(PRICE_TICK_LOG))
print("Exists?", os.path.exists(PRICE_TICK_LOG))

class VisualPriceTickIndicator:
    def __init__(self, initial_capital=100000, log_path='smartapi/price_ticks.log'):
        self.initial_capital = initial_capital
        self.current_equity = initial_capital
        self.position_active = False
        self.position_entry_price = 0
        self.current_price = 0
        self.position_size = 0
        self.log_path = log_path
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
    def _update_display(self):
        # Determine background color and info text
        if not self.position_active:
            bg_color = 'gray'
            pnl_text = "WAIT"
        else:
            if self.position_size > 0:
                pnl = (self.current_price - self.position_entry_price) * self.position_size
            else:
                pnl = (self.position_entry_price - self.current_price) * abs(self.position_size)
            total_pnl = self.current_equity - self.initial_capital
            pnl_percent = (total_pnl / self.initial_capital) * 100
            if pnl >= 0:
                bg_color = 'green'
                pnl_text = f"+{pnl_percent:.1f}%"
            else:
                bg_color = 'red'
                pnl_text = f"{pnl_percent:.1f}%"
        # Get latest price tick info
        latest_tick = self._get_latest_tick()
        # Compose info text
        info = f"Status: {pnl_text}\n{latest_tick}"
        self.info_label.config(text=info, bg=bg_color)
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

if __name__ == "__main__":
    indicator = VisualPriceTickIndicator()
    indicator.run() 