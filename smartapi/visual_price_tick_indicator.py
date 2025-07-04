import tkinter as tk
import threading
import time
import os

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
        self.root.geometry("200x120")
        self.root.resizable(False, False)
        self.root.attributes('-topmost', True)
        screen_width = self.root.winfo_screenwidth()
        self.root.geometry(f"200x120+{screen_width-220}+20")
        self.canvas = tk.Canvas(self.root, width=100, height=100, bg='gray', highlightthickness=0)
        self.canvas.place(x=10, y=10)
        self.square = self.canvas.create_rectangle(10, 10, 90, 90, fill='gray', outline='black', width=2)
        self.pnl_text = self.canvas.create_text(50, 50, text="WAIT", fill='white', font=('Arial', 12, 'bold'))
        self.tick_label = tk.Label(self.root, text="", font=("Consolas", 10), anchor='w', width=22, bg='white', fg='black')
        self.tick_label.place(x=110, y=40)
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
        # Update color square and PnL
        if not self.position_active:
            self.canvas.itemconfig(self.square, fill='gray')
            self.canvas.itemconfig(self.pnl_text, text="WAIT", fill='white')
        else:
            if self.position_size > 0:
                pnl = (self.current_price - self.position_entry_price) * self.position_size
            else:
                pnl = (self.position_entry_price - self.current_price) * abs(self.position_size)
            total_pnl = self.current_equity - self.initial_capital
            pnl_percent = (total_pnl / self.initial_capital) * 100
            if pnl >= 0:
                self.canvas.itemconfig(self.square, fill='green')
                self.canvas.itemconfig(self.pnl_text, text=f"+{pnl_percent:.1f}%", fill='white')
            else:
                self.canvas.itemconfig(self.square, fill='red')
                self.canvas.itemconfig(self.pnl_text, text=f"{pnl_percent:.1f}%", fill='white')
        # Update latest price tick
        latest_tick = self._get_latest_tick()
        self.tick_label.config(text=latest_tick)
    def _get_latest_tick(self):
        try:
            if os.path.exists(self.log_path):
                with open(self.log_path, 'rb') as f:
                    f.seek(0, os.SEEK_END)
                    filesize = f.tell()
                    blocksize = 1024
                    if filesize == 0:
                        return ""
                    seekpos = max(filesize - blocksize, 0)
                    f.seek(seekpos)
                    lines = f.read().decode(errors='ignore').splitlines()
                    if lines:
                        return lines[-1]
        except Exception as e:
            return f"Log error: {e}"
        return ""
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
        self.canvas.itemconfig(self.square, fill=color)
        self.canvas.itemconfig(self.pnl_text, text=message, fill='white')
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