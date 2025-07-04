import json
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkcalendar import DateEntry
from datetime import datetime
import pandas as pd
from login import login
from logzero import logger

class AutocompleteCombobox(ttk.Combobox):
    """Combobox with autocomplete showing top 5 matches"""
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self._all_values = self['values']
        self.bind('<KeyRelease>', self._on_keyrelease)

    def _on_keyrelease(self, event):
        """Update dropdown list based on typed text"""
        typed = self.get().upper()
        if typed == '':
            self['values'] = self._all_values
        else:
            matches = [item for item in self._all_values 
                      if item.upper().startswith(typed)]
            if matches and len(matches) <= 5:
                self['values'] = matches
            else:
                self['values'] = matches[:20]

def load_symbols():
    """Load symbols from stocks.json"""
    try:
        with open("stocks.json", "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading symbols: {e}")
        return []

def main():
    root = tk.Tk()
    root.title("Historical Data Fetcher")

    # Load symbols - make it available to all functions
    global symbols_list
    symbols_list = load_symbols()
    symbol_names = [item["symbol"] for item in symbols_list]

    # Symbol dropdown with autocomplete
    ttk.Label(root, text="Symbol:").pack()
    symbol_var = tk.StringVar()
    symbol_combo = AutocompleteCombobox(
        root,
        textvariable=symbol_var,
        values=symbol_names
    )
    symbol_combo.pack()

    # Token entry (read-only)
    ttk.Label(root, text="Token:").pack()
    token_var = tk.StringVar()
    token_entry = ttk.Entry(root, textvariable=token_var, state='readonly')
    token_entry.pack()

    # Exchange entry (read-only)
    ttk.Label(root, text="Exchange:").pack()
    exchange_var = tk.StringVar()
    exchange_entry = ttk.Entry(root, textvariable=exchange_var, state='readonly')
    exchange_entry.pack()

    def on_symbol_select(*args):
        """Update token and exchange when symbol is selected"""
        selected = symbol_var.get()
        for item in symbols_list:
            if item["symbol"] == selected:
                token_var.set(item["token"])
                exchange_var.set(item["exchange"])
                break

    symbol_var.trace('w', on_symbol_select)

    # Fetch LTP data
    def fetch_ltp():
        smart_api, auth_token, refresh_token = login()
        if smart_api:
            try:
                stock_params = {
                    "exchange": exchange_var.get(),
                    "tradingsymbol": symbol_var.get(),
                    "symboltoken": token_var.get()
                }
                ltp_data = smart_api.ltpData(**stock_params)
                logger.info(f"LTP Data: {ltp_data}")
                ltp_result.set(f"LTP: {ltp_data['data']['ltp']}")
            except Exception as e:
                logger.exception(f"Fetching LTP failed: {e}")
                messagebox.showerror("Error", "Failed to fetch LTP data.")

    # Fetch Historical Data
    def fetch_historical_data():
        selected_symbol = symbol_var.get()
        symbol_data = next((item for item in symbols_list if item["symbol"] == selected_symbol), None)
        
        if not selected_symbol or not symbol_data:
            messagebox.showerror("Error", "Please select a valid symbol")
            return

        smart_api, auth_token, refresh_token = login()
        if smart_api is None:
            messagebox.showerror("Login Failed", "Unable to login.")
            return
            
        try:
            # Get date portions from the DateEntry widgets.
            date_from = from_date_entry.get_date()
            date_to   = to_date_entry.get_date()
            
            # Format the time strings
            from_time = f"{from_hour.get()}:{from_minute.get()}"
            to_time = f"{to_hour.get()}:{to_minute.get()}"
            
            from_date_str = f"{date_from.strftime('%Y-%m-%d')} {from_time}"
            to_date_str   = f"{date_to.strftime('%Y-%m-%d')} {to_time}"
            
            # Debug prints for verification.
            print(f"Final fromdate: {from_date_str}")
            print(f"Final todate: {to_date_str}")
            
            historic_params = {
                "exchange": symbol_data["exchange"],
                "symboltoken": symbol_data["token"],
                "interval": interval_var.get().strip().upper(),
                "fromdate": from_date_str,
                "todate": to_date_str
            }

            logger.info(f"📡 Sending Historical Data Request: {historic_params}")
            historical_data = smart_api.getCandleData(historic_params)

            # Convert the data to pandas DataFrame
            if historical_data and 'data' in historical_data:
                df = pd.DataFrame(historical_data['data'], 
                                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                
                # Convert timestamp to desired format
                df['timestamp'] = pd.to_datetime(df['timestamp']).dt.strftime('%Y%m%d %H:%M')
                
                if output_var.get() == "display":
                    # Display in GUI
                    history_result.set(df.to_string())
                else:
                    # Save to CSV
                    file_path = filedialog.asksaveasfilename(
                        defaultextension='.csv',
                        filetypes=[("CSV files", "*.csv")],
                        initialfile=f"{symbol_var.get()}_{interval_var.get()}.csv"
                    )
                    if file_path:
                        df.to_csv(file_path, index=False, header=True)
                        history_result.set(f"Data saved to {file_path}")
                        
            else:
                messagebox.showerror("Error", "No data received from API")
                
        except Exception as e:
            logger.exception("Historical Data fetch failed: %s", e)
            messagebox.showerror("Error", f"Failed to fetch historical data: {e}")

    # Fetch LTP Button & Display
    ltp_result = tk.StringVar()
    ltp_label = ttk.Label(root, textvariable=ltp_result, font=("Arial", 10, "bold"))
    ltp_label.pack()
    fetch_ltp_button = ttk.Button(root, text="Fetch LTP", command=fetch_ltp)
    fetch_ltp_button.pack()

    # Interval Dropdown (Default: ONE_DAY)
    interval_var = tk.StringVar(value="ONE_DAY")
    ttk.Label(root, text="Interval:").pack()
    interval_menu = ttk.Combobox(root, textvariable=interval_var, 
                             values=["ONE_MINUTE", "FIVE_MINUTE", "ONE_DAY"])
    interval_menu.pack()

    # **Dropdown Calendar for Date Selection**
    ttk.Label(root, text="From Date:").pack()
    from_date_entry = DateEntry(root, width=12, background='darkblue', foreground='white', borderwidth=2)
    from_date_entry.pack()

    ttk.Label(root, text="To Date:").pack()
    to_date_entry = DateEntry(root, width=12, background='darkblue', foreground='white', borderwidth=2)
    to_date_entry.pack()

    # Time Entries for Non-DAY Interval
    ttk.Label(root, text="From Time (HH:MM):").pack()
    from_time_frame = ttk.Frame(root)
    from_time_frame.pack()

    from_hour = ttk.Spinbox(
        from_time_frame,
        from_=0,
        to=23,
        width=2,
        format="%02.0f",
        values=[9]  # Default to 9
    )
    from_hour.set("09")  # Set default
    from_hour.pack(side=tk.LEFT)

    ttk.Label(from_time_frame, text=":").pack(side=tk.LEFT)

    from_minute = ttk.Spinbox(
        from_time_frame,
        from_=0,
        to=59,
        width=2,
        format="%02.0f",
        values=[15]  # Default to 15
    )
    from_minute.set("15")  # Set default
    from_minute.pack(side=tk.LEFT)

    # To Time spinboxes with default 15:30
    ttk.Label(root, text="To Time (HH:MM):").pack()
    to_time_frame = ttk.Frame(root)
    to_time_frame.pack()

    to_hour = ttk.Spinbox(
        to_time_frame,
        from_=0,
        to=23,
        width=2,
        format="%02.0f",
        values=[15]  # Default to 15
    )
    to_hour.set("15")  # Set default
    to_hour.pack(side=tk.LEFT)

    ttk.Label(to_time_frame, text=":").pack(side=tk.LEFT)

    to_minute = ttk.Spinbox(
        to_time_frame,
        from_=0,
        to=59,
        width=2,
        format="%02.0f",
        values=[30]  # Default to 30
    )
    to_minute.set("30")  # Set default
    to_minute.pack(side=tk.LEFT)

    # Output option
    output_var = tk.StringVar(value="display")
    ttk.Label(root, text="Output:").pack()
    ttk.Radiobutton(root, text="Display", variable=output_var, value="display").pack()
    ttk.Radiobutton(root, text="Save to CSV", variable=output_var, value="csv").pack()

    # Fetch Historical Data Button & Display
    history_result = tk.StringVar()
    history_label = ttk.Label(root, textvariable=history_result, wraplength=500)
    history_label.pack()
    fetch_history_button = ttk.Button(root, text="Fetch Historical Data", command=fetch_historical_data)
    fetch_history_button.pack()

    # Run GUI
    root.mainloop()

if __name__ == "__main__":
    main()

