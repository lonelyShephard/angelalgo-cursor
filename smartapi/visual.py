import os
import tkinter as tk
from tkinter import ttk, messagebox
import pandas as pd
import matplotlib.pyplot as plt

DATA_FOLDER = 'data'

def get_csv_files():
    """Return a list of CSV files in the data folder."""
    if not os.path.exists(DATA_FOLDER):
        return []
    return [f for f in os.listdir(DATA_FOLDER) if f.lower().endswith('.csv')]

class AutocompleteCombobox(ttk.Combobox):
    """Combobox with autocompletion."""
    def set_completion_list(self, completion_list):
        self._completion_list = sorted(completion_list, key=str.lower)
        self['values'] = self._completion_list
        self.bind('<KeyRelease>', self._handle_keyrelease)

    def _handle_keyrelease(self, event):
        value = self.get()
        if value == '':
            self['values'] = self._completion_list
        else:
            filtered = [item for item in self._completion_list if value.lower() in item.lower()]
            self['values'] = filtered

class CSVGraphApp:
    def __init__(self, root):
        self.root = root
        self.root.title("CSV Closing Price Grapher")

        # File selection
        ttk.Label(root, text="Select CSV file:").grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.combo = AutocompleteCombobox(root, width=40)
        self.csv_files = get_csv_files()
        self.combo.set_completion_list(self.csv_files)
        self.combo.grid(row=0, column=1, padx=10, pady=5)
        self.combo.bind("<<ComboboxSelected>>", self.on_file_select)

        # From Date and To Date
        ttk.Label(root, text="From Date:").grid(row=1, column=0, padx=10, pady=5, sticky="w")
        self.from_date_spin = ttk.Combobox(root, width=12, state="readonly")
        self.from_date_spin.grid(row=1, column=1, padx=10, pady=5, sticky="w")

        ttk.Label(root, text="To Date:").grid(row=2, column=0, padx=10, pady=5, sticky="w")
        self.to_date_spin = ttk.Combobox(root, width=12, state="readonly")
        self.to_date_spin.grid(row=2, column=1, padx=10, pady=5, sticky="w")

        # From Time and To Time
        ttk.Label(root, text="From Time (HH:MM):").grid(row=3, column=0, padx=10, pady=5, sticky="w")
        self.from_hour_spin = tk.Spinbox(root, from_=0, to=23, width=3, format="%02.0f")
        self.from_minute_spin = tk.Spinbox(root, from_=0, to=59, width=3, format="%02.0f")
        self.from_hour_spin.grid(row=3, column=1, sticky="w")
        self.from_minute_spin.grid(row=3, column=1, padx=40, sticky="w")

        ttk.Label(root, text="To Time (HH:MM):").grid(row=4, column=0, padx=10, pady=5, sticky="w")
        self.to_hour_spin = tk.Spinbox(root, from_=0, to=23, width=3, format="%02.0f")
        self.to_minute_spin = tk.Spinbox(root, from_=0, to=59, width=3, format="%02.0f")
        self.to_hour_spin.grid(row=4, column=1, sticky="w")
        self.to_minute_spin.grid(row=4, column=1, padx=40, sticky="w")

        # Set default times
        self.from_hour_spin.delete(0, tk.END)
        self.from_hour_spin.insert(0, "09")
        self.from_minute_spin.delete(0, tk.END)
        self.from_minute_spin.insert(0, "15")
        self.to_hour_spin.delete(0, tk.END)
        self.to_hour_spin.insert(0, "15")
        self.to_minute_spin.delete(0, tk.END)
        self.to_minute_spin.insert(0, "30")

        # Submit button
        ttk.Button(root, text="Plot Closing Price", command=self.plot_graph).grid(row=5, column=0, columnspan=2, pady=15)

        # DataFrame cache
        self.df = None

    def on_file_select(self, event=None):
        filename = self.combo.get()
        if not filename:
            return
        filepath = os.path.join(DATA_FOLDER, filename)
        try:
            df = pd.read_csv(filepath)
            # Parse timestamp
            df['timestamp'] = pd.to_datetime(df['timestamp'], format='%Y%m%d %H:%M')
            self.df = df
            # Populate date spinboxes with unique dates
            unique_dates = sorted(df['timestamp'].dt.date.unique())
            self.from_date_spin['values'] = [str(d) for d in unique_dates]
            self.to_date_spin['values'] = [str(d) for d in unique_dates]
            if unique_dates:
                self.from_date_spin.set(str(unique_dates[0]))
                self.to_date_spin.set(str(unique_dates[-1]))
        except Exception as e:
            messagebox.showerror("Error", f"Could not load file: {e}")
            self.df = None

    def plot_graph(self):
        if self.df is None:
            messagebox.showwarning("No file", "Please select a CSV file first.")
            return
        try:
            from_date = self.from_date_spin.get()
            to_date = self.to_date_spin.get()
            from_hour = int(self.from_hour_spin.get())
            from_minute = int(self.from_minute_spin.get())
            to_hour = int(self.to_hour_spin.get())
            to_minute = int(self.to_minute_spin.get())

            from_dt = pd.to_datetime(f"{from_date} {from_hour:02d}:{from_minute:02d}")
            to_dt = pd.to_datetime(f"{to_date} {to_hour:02d}:{to_minute:02d}")

            df_range = self.df[(self.df['timestamp'] >= from_dt) & (self.df['timestamp'] <= to_dt)]
            if df_range.empty:
                messagebox.showinfo("No Data", "No data for selected range.")
                return

            import matplotlib.dates as mdates

            fig, ax = plt.subplots(figsize=(12,5))
            # Plot as a line, no markers
            line, = ax.plot(df_range['timestamp'], df_range['close'], label='Close Price', marker='')

            plt.title(f"Close Price from {from_dt} to {to_dt}")
            plt.xlabel("Timestamp")
            plt.ylabel("Close Price")
            plt.legend()
            plt.tight_layout()

            # Tooltip annotation
            annot = ax.annotate("", xy=(0,0), xytext=(20,20), textcoords="offset points",
                                bbox=dict(boxstyle="round", fc="w"),
                                arrowprops=dict(arrowstyle="->"))
            annot.set_visible(False)

            xdata = df_range['timestamp'].reset_index(drop=True)
            ydata = df_range['close'].reset_index(drop=True)
            xvals = mdates.date2num(xdata)

            def hover(event):
                if event.inaxes == ax and event.xdata is not None:
                    mouse_val = event.xdata
                    idx = min(range(len(xvals)), key=lambda i: abs(xvals[i] - mouse_val))
                    x, y = xdata.iloc[idx], ydata.iloc[idx]
                    annot.xy = (x, y)
                    text = f"{x.strftime('%Y-%m-%d %H:%M')}\nPrice: {y:.2f}"
                    annot.set_text(text)
                    annot.set_visible(True)
                    fig.canvas.draw_idle()
                else:
                    annot.set_visible(False)
                    fig.canvas.draw_idle()

            fig.canvas.mpl_connect("motion_notify_event", hover)
            plt.show()
        except Exception as e:
            messagebox.showerror("Error", f"Could not plot graph: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = CSVGraphApp(root)
    root.mainloop()