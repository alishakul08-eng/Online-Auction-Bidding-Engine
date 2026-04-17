import socket
import ssl
import threading
import os
import time
import csv
import tkinter as tk
from tkinter import scrolledtext

# --- AUTHENTICATION DATABASE ---
USER_DB_FILE = "users.csv"

def initialize_user_db():
    if not os.path.exists(USER_DB_FILE):
        with open(USER_DB_FILE, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["username", "password"])
            writer.writerow(["user1", "pass1"])
            writer.writerow(["user2", "pass2"])
            writer.writerow(["user3", "pass3"])
            writer.writerow(["user4", "pass4"])

initialize_user_db()

highest_bid = 0
winner_name = None 
active_bidders = []  
all_participants = [] 
client_count = 0
lock = threading.Lock()
timer_reset_event = threading.Event()
auction_active = True

items_catalog = [
    {"name": "Vincent Van Gogh's Starry Night", "image": "painting.jpg"},
    {"name": "The Persistence of Memory", "image": "painting2.jpg"},
    {"name": "Girl with a Pearl Earring", "image": "painting3.jpg"},
    {"name": "The Tiger", "image": "painting4.png"},
    {"name": "Mountain View", "image": "painting5.png"}
]
current_item_index = 0

def authenticate_user(username, password):
    try:
        with open(USER_DB_FILE, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["username"] == username and row["password"] == password:
                    return True
        return False
    except:
        return False

def log_to_csv(item_name, winner, price):
    file_exists = os.path.isfile("auction_history.csv")
    with open("auction_history.csv", "a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Timestamp", "Item Name", "Winner", "Final Price"])
        
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        writer.writerow([timestamp, item_name, winner, price])

def countdown_timer():
    global highest_bid, winner_name, auction_active
    
    calls = ["GOING ONCE...", "GOING TWICE...", "GOING THRICE... SOLD!"]
    
    for call in calls:
        new_bid_received = timer_reset_event.wait(timeout=5)
        
        if new_bid_received:
            timer_reset_event.clear()
            return 
            
        if not auction_active:
            return
            
        broadcast_live_update(f"\n[TIMER] {call}")
        server_gui.update_log(f"Timer sequence: {call}")

    end_auction_sequence()

def close_single_client(conn, name):
    try:
        conn.sendall(b"\n--- AUCTION ENDING ---\n")
        
        result_msg = f"\n[FINAL] The auction has ended! The bid goes to {winner_name} for {highest_bid}!!\n"
        conn.sendall(result_msg.encode())
        
        time.sleep(0.2)
        
        if name == winner_name:
            conn.sendall(b"SHOW_FIREWORKS\n")
            time.sleep(0.1)
            conn.sendall(f"CONGRATULATIONS {name.upper()}! You won the auction!\n".encode())
        else:
            conn.sendall(f"Thank you for participating, {name}. Better luck next time!\n".encode())
        
        time.sleep(10)
        
        if current_item_index < len(items_catalog) - 1:
            conn.sendall(b"NEXT_ROUND_PREP\n")
        else:
            conn.sendall(b"SHUTDOWN_NOW")
            conn.close()
    except:
        pass

def end_auction_sequence():
    global auction_active, winner_name, current_item_index, highest_bid, active_bidders
    
    with lock:
        if not auction_active:
            return
        auction_active = False
    
    item_name = items_catalog[current_item_index]["name"]
    server_gui.update_log(f"ROUND FINISHED: {winner_name} won {item_name}")
    
    log_to_csv(item_name, winner_name if winner_name else "No Winner", highest_bid)
    
    for item in all_participants:
        threading.Thread(target=close_single_client, args=(item[0], item[1])).start()
    
    time.sleep(11)

    if current_item_index < len(items_catalog) - 1:
        current_item_index += 1
        highest_bid = 0
        winner_name = None
        
        with lock:
            active_bidders = []
            for p in all_participants:
                active_bidders.append(p)
            auction_active = True
        
        server_gui.update_log(f"STARTING ROUND {current_item_index + 1}")
        
        new_item = items_catalog[current_item_index]
        broadcast_live_update(f"SET_ITEM|{new_item['name']}|{new_item['image']}\n")
        
        time.sleep(1.0)
        for p in all_participants:
            try:
                p[0].sendall(f"--- WELCOME BACK {p[1].upper()} ---\n".encode())
                p[0].sendall(f"Current High Bid: {highest_bid}\n".encode())
                p[0].sendall(b"Do you want to bid? (yes/no): ")
            except:
                continue
    else:
        server_gui.update_log("ALL ROUNDS COMPLETE. SHUTTING DOWN.")
        os._exit(0)

def broadcast_live_update(msg, exclude_name=None):
    with lock:
        for item in active_bidders:
            if item[1] != exclude_name:
                try:
                    item[0].sendall(f"\n{msg}\n".encode())
                except:
                    continue

def handle_client(conn, addr, client_id):
    global highest_bid, winner_name, active_bidders, auction_active
    
    try:
        authenticated = False
        client_name = ""
        
        while not authenticated:
            conn.sendall(b"AUTH_REQUEST")
            auth_data = conn.recv(1024).decode().strip()
            if not auth_data: break
            
            try:
                username, password = auth_data.split("|")
                if authenticate_user(username, password):
                    conn.sendall(b"AUTH_SUCCESS")
                    client_name = username
                    authenticated = True
                else:
                    conn.sendall(b"AUTH_FAILED")
            except:
                conn.sendall(b"AUTH_FAILED")

        if not authenticated:
            conn.close()
            return
        
        server_gui.update_log(f"User '{client_name}' (ID: {client_id}) connected from {addr}")
        
        with lock:
            active_bidders.append([conn, client_name])
            all_participants.append([conn, client_name])

        item = items_catalog[current_item_index]
        conn.sendall(f"SET_ITEM|{item['name']}|{item['image']}".encode())
        
        time.sleep(0.1)
        conn.sendall(f"--- WELCOME {client_name.upper()} ---\n".encode())
        conn.sendall(f"Current High Bid: {highest_bid}\n".encode())
        conn.sendall(b"Do you want to bid? (yes/no): ")

        while True:
            while not auction_active:
                time.sleep(1)

            raw_data = conn.recv(1024).decode().strip()
            
            if not raw_data or raw_data == "CLIENT_EXIT":
                break

            choice = raw_data.lower()
            
            if choice == 'yes':
                if not auction_active:
                    conn.sendall(b"Wait for the next round...\n")
                    continue
                
                timer_reset_event.set()
                broadcast_live_update(f"[NOTICE] {client_name} is preparing a bid!", client_name)
                server_gui.update_log(f"Alert: {client_name} is typing a bid.")
                
                conn.sendall(b"Enter your bid amount: ")
                bid_input = conn.recv(1024).decode().strip()
                
                try:
                    val = int(bid_input)
                    if val > highest_bid:
                        highest_bid = val
                        winner_name = client_name
                        conn.sendall(f">>> SUCCESS! {val} is the high bid.\n".encode())
                        broadcast_live_update(f"[LIVE] New High Bid: {highest_bid} ({winner_name})", client_name)
                        server_gui.update_log(f"Update: {client_name} bid {highest_bid}")
                        timer_reset_event.clear()
                        threading.Thread(target=countdown_timer, daemon=True).start()
                    else:
                        conn.sendall(f">>> NICE TRY! Low bid.\n".encode())
                        timer_reset_event.clear()
                        threading.Thread(target=countdown_timer, daemon=True).start()
                except ValueError:
                    conn.sendall(b">>> ERROR: Enter a number.\n")
                    timer_reset_event.clear()
                    threading.Thread(target=countdown_timer, daemon=True).start()
            
            elif choice == 'no':
                with lock:
                    for b in active_bidders:
                        if b[1] == client_name:
                            active_bidders.remove(b)
                            break
                    
                    if len(active_bidders) <= 1 and auction_active:
                        if len(active_bidders) == 1:
                            winner_name = active_bidders[0][1]
                        threading.Thread(target=end_auction_sequence).start()
                
                conn.sendall(b"\nYou have withdrawn from this round. Please wait for the next item...\n")
                broadcast_live_update(f"[ALERT] {client_name} withdrew.", client_name)
                
                while not auction_active:
                    time.sleep(1)
                continue 
            
            if auction_active:
                conn.sendall(b"Do you want to bid? (yes/no): ")
                
    except:
        pass

class ServerDashboard:
    def __init__(self, root):
        self.root = root
        self.root.title("SSL Auction Server Control Panel")
        self.root.geometry("500x450")
        
        self.header = tk.Label(root, text="AUCTION SYSTEM LOGS", font=("Helvetica", 12, "bold"))
        self.header.pack(pady=10)
        
        self.log_area = scrolledtext.ScrolledText(root, state='disabled', height=20, width=55, bg="#F5F5F5")
        self.log_area.pack(pady=5, padx=10)

    def update_log(self, text):
        self.log_area.config(state='normal')
        self.log_area.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {text}\n")
        self.log_area.see(tk.END)
        self.log_area.config(state='disabled')

def start_server():
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile="server.crt", keyfile="server.key")
    
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind(('0.0.0.0', 8443)) 
    server_sock.listen(5)
    
    secure_server = context.wrap_socket(server_sock, server_side=True)
    
    while True:
        try:
            client_conn, addr = secure_server.accept()
            global client_count
            client_count += 1
            threading.Thread(target=handle_client, args=(client_conn, addr, client_count)).start()
        except:
            break

if __name__ == "__main__":
    root = tk.Tk()
    server_gui = ServerDashboard(root)
    threading.Thread(target=start_server, daemon=True).start()
    root.mainloop()