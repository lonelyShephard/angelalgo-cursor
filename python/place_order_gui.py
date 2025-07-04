import json
import tkinter as tk
from tkinter import ttk, messagebox
import time
from login import login
from logzero import logger

# Load stock symbols from stocks.json.
def load_stocks(json_file):
    try:
        with open(json_file, "r") as file:
            data = json.load(file)

        # Create dictionary {symbol: {token, exchange}}
        stock_dict = {entry["symbol"]: {"token": entry["token"], "exchange": entry["exchange"]} for entry in data}
        return stock_dict

    except Exception as e:
        print(f"❌ Error loading stocks: {e}")
        return {}

# Update token and exchange fields when a symbol is selected
def update_stock_details(event=None):
    selected_symbol = symbol_var.get().upper()
    if selected_symbol in stock_dict:
        token_var.set(stock_dict[selected_symbol]["token"])
        exchange_var.set(stock_dict[selected_symbol]["exchange"])
    else:
        token_var.set("")
        exchange_var.set("")

# **Autocomplete Function (Restored)**
def filter_symbols(event):
    typed_value = symbol_var.get().upper()
    matching_symbols = [s for s in stock_dict.keys() if typed_value in s]

    # Update dropdown values dynamically
    symbol_menu["values"] = matching_symbols

# Place order function
def place_order():
    smart_api, auth_token, refresh_token = login()
    
    if smart_api:
        try:
            # Get user input
            tradingsymbol = symbol_var.get().upper()
            symboltoken = token_var.get()
            transactiontype = transaction_var.get()
            exchange = exchange_var.get()
            ordertype = order_type_var.get()
            producttype = product_type_var.get()
            quantity = quantity_entry.get()
            price = price_entry.get() or "0"

            if not symboltoken:
                messagebox.showerror("Error", "Invalid stock selection!")
                return

            # Define order parameters
            order_params = {
                "variety": "NORMAL",
                "tradingsymbol": tradingsymbol,
                "symboltoken": symboltoken,
                "transactiontype": transactiontype,
                "exchange": exchange,
                "ordertype": ordertype,
                "producttype": producttype,
                "duration": "DAY",
                "price": price,
                "squareoff": "0",
                "stoploss": "0",
                "quantity": quantity
            }

            # Place order
            order_id = smart_api.placeOrder(order_params)
            logger.info(f"✅ Order Placed! Order ID: {order_id}")
            messagebox.showinfo("Order Placed", f"Order ID: {order_id}")

            # Check order status immediately
            check_order_status(smart_api, order_id, delay=0)

            # Schedule a second check after 10 seconds
            root.after(10000, lambda: check_order_status(smart_api, order_id, delay=30))

        except Exception as e:
            logger.exception(f"❌ Order placement failed: {e}")
            messagebox.showerror("Error", f"Order placement failed: {e}")

# Function to check order status
def check_order_status(smart_api, order_id, delay):
    try:
        order_book = smart_api.orderBook()
        if order_book["status"]:
            for order in order_book["data"]:
                if order["orderid"] == order_id:
                    status_message = f"[After {delay} sec] Order {order_id} Status: {order['status']}"
                    logger.info(status_message)
                    status_text.set(status_message)  # Update GUI
                    return
        status_text.set(f"⚠️ Order {order_id} not found.")
    except Exception as e:
        logger.exception(f"❌ Error fetching order status: {e}")
        status_text.set("Error fetching order status.")

# Load stock data
stock_dict = load_stocks("stocks.json")

# GUI Setup
root = tk.Tk()
root.title("SmartAPI Order Placement")

# Symbol Dropdown with Autocomplete (Fixed)
symbol_var = tk.StringVar()
ttk.Label(root, text="Stock Symbol:").pack()
symbol_menu = ttk.Combobox(root, textvariable=symbol_var, values=list(stock_dict.keys()))
symbol_menu.pack()
symbol_menu.bind("<KeyRelease>", filter_symbols)  # Autocomplete while typing (Restored)
symbol_menu.bind("<<ComboboxSelected>>", update_stock_details)  # Auto-fill token & exchange

# Stock Token Field (Auto-filled)
token_var = tk.StringVar()
ttk.Label(root, text="Stock Token:").pack()
token_entry = ttk.Entry(root, textvariable=token_var, state="readonly")
token_entry.pack()

# Exchange Field (Auto-filled)
exchange_var = tk.StringVar()
ttk.Label(root, text="Exchange:").pack()
exchange_entry = ttk.Entry(root, textvariable=exchange_var, state="readonly")
exchange_entry.pack()

# Transaction Type Dropdown
transaction_var = tk.StringVar()
ttk.Label(root, text="Transaction Type:").pack()
transaction_menu = ttk.Combobox(root, textvariable=transaction_var, values=["BUY", "SELL"])
transaction_menu.pack()

# Order Type Dropdown
order_type_var = tk.StringVar()
ttk.Label(root, text="Order Type:").pack()
order_type_menu = ttk.Combobox(root, textvariable=order_type_var, values=["MARKET", "LIMIT", "SL", "SLM"])
order_type_menu.pack()

# Product Type Dropdown
product_type_var = tk.StringVar()
ttk.Label(root, text="Product Type:").pack()
product_type_menu = ttk.Combobox(root, textvariable=product_type_var, values=["INTRADAY", "DELIVERY"])
product_type_menu.pack()

# Quantity Input
ttk.Label(root, text="Quantity:").pack()
quantity_entry = ttk.Entry(root)
quantity_entry.pack()

# Price Input
ttk.Label(root, text="Price (leave empty for MARKET order):").pack()
price_entry = ttk.Entry(root)
price_entry.pack()

# Submit Button
submit_button = ttk.Button(root, text="Place Order", command=place_order)
submit_button.pack()

# Order Status Label
status_text = tk.StringVar()
status_label = ttk.Label(root, textvariable=status_text, font=("Arial", 10, "bold"), foreground="blue")
status_label.pack()

# Run GUI
root.mainloop()