import tkinter as tk
import threading
import time

class TradingVisualIndicator:
    def __init__(self, initial_capital=100000):
        self.initial_capital = initial_capital
        self.current_equity = initial_capital
        self.position_active = False
        self.position_entry_price = 0
        self.current_price = 0
        self.position_size = 0
        self.root = tk.Tk()
        self.root.title("Trading Bot Status")
        self.root.geometry("100x100")
        self.root.resizable(False, False)
        self.root.attributes('-topmost', True)
        screen_width = self.root.winfo_screenwidth()
        self.root.geometry(f"100x100+{screen_width-120}+20")
        self.canvas = tk.Canvas(self.root, width=100, height=100, bg='gray', highlightthickness=0)
        self.canvas.pack(fill='both', expand=True)
        self.square = self.canvas.create_rectangle(10, 10, 90, 90, fill='gray', outline='black', width=2)
        self.text = self.canvas.create_text(50, 50, text="WAIT", fill='white', font=('Arial', 12, 'bold'))
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
        if not self.position_active:
            self.canvas.itemconfig(self.square, fill='gray')
            self.canvas.itemconfig(self.text, text="WAIT", fill='white')
        else:
            if self.position_size > 0:
                pnl = (self.current_price - self.position_entry_price) * self.position_size
            else:
                pnl = (self.position_entry_price - self.current_price) * abs(self.position_size)
            total_pnl = self.current_equity - self.initial_capital
            pnl_percent = (total_pnl / self.initial_capital) * 100
            if pnl >= 0:
                self.canvas.itemconfig(self.square, fill='green')
                self.canvas.itemconfig(self.text, text=f"+{pnl_percent:.1f}%", fill='white')
            else:
                self.canvas.itemconfig(self.square, fill='red')
                self.canvas.itemconfig(self.text, text=f"{pnl_percent:.1f}%", fill='white')
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
        self.canvas.itemconfig(self.text, text=message, fill='white')
    def close(self):
        self.is_running = False
        self.root.quit()
        self.root.destroy()
    def run(self):
        self.root.mainloop()
_visual_indicator = None
def get_visual_indicator(initial_capital=100000):
    global _visual_indicator
    if _visual_indicator is None:
        _visual_indicator = TradingVisualIndicator(initial_capital)
    return _visual_indicator
def start_visual_indicator(initial_capital=100000):
    indicator = get_visual_indicator(initial_capital)
    indicator_thread = threading.Thread(target=indicator.run, daemon=True)
    indicator_thread.start()
    return indicator
def update_visual_position(position_size, entry_price, current_price, current_equity):
    indicator = get_visual_indicator()
    if indicator:
        indicator.update_position(position_size, entry_price, current_price, current_equity)
def clear_visual_position():
    indicator = get_visual_indicator()
    if indicator:
        indicator.clear_position()
def update_visual_equity(current_equity):
    indicator = get_visual_indicator()
    if indicator:
        indicator.update_equity(current_equity)
def show_visual_message(message, color='blue'):
    indicator = get_visual_indicator()
    if indicator:
        indicator.show_message(message, color)
def close_visual_indicator():
    global _visual_indicator
    if _visual_indicator:
        _visual_indicator.close()
        _visual_indicator = None
