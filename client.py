import socket 
import ssl 
import threading 
import os
import time
import tkinter as tk 
import random
from tkinter import scrolledtext, messagebox, simpledialog
from PIL import Image, ImageTk 

class LoginWindow:
    def __init__(self, root, on_success):
        self.root = root
        self.on_success = on_success
        self.window = tk.Toplevel(root)
        self.window.title("Auction Login")
        self.window.geometry("300x250")
        self.window.resizable(False, False)
        
        tk.Label(self.window, text="AUCTION SYSTEM", font=("Helvetica", 12, "bold")).pack(pady=10)
        
        tk.Label(self.window, text="Username:").pack(pady=5)
        self.user_entry = tk.Entry(self.window)
        self.user_entry.pack()
        
        tk.Label(self.window, text="Password:").pack(pady=5)
        self.pass_entry = tk.Entry(self.window, show="*")
        self.pass_entry.pack()
        
        self.login_btn = tk.Button(self.window, text="Login", command=self.attempt_login, bg="#DB7093", fg="white")
        self.login_btn.pack(pady=20)
        
        self.window.protocol("WM_DELETE_WINDOW", lambda: os._exit(0))

    def attempt_login(self):
        u = self.user_entry.get().strip()
        p = self.pass_entry.get().strip()
        if u and p:
            self.on_success(u, p)

class AuctionClientGUI:
    def __init__(self, root): 
        self.root = root
        self.root.title("Secure SSL Auction Client")
        self.root.geometry("600x700") 
        self.root.withdraw() 
        self.fireworks_active = False

        self.canvas = tk.Canvas(self.root, width=600, height=700, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        self.bg_image_name = "bg.jpeg"  
        self.load_background()

        self.item_label = tk.Label(self.root, text="Synchronizing with server...", 
                                   font=("Helvetica", 16, "bold"), bg="white", padx=10)
        self.canvas.create_window(300, 40, window=self.item_label)
        
        self.frame_container = tk.Frame(self.root, bg="#5C4033", padx=10, pady=10)
        self.canvas.create_window(300, 190, window=self.frame_container)

        self.img_label = tk.Label(self.frame_container, bg="white")
        self.img_label.pack()

        self.display = scrolledtext.ScrolledText(self.root, state='disabled', wrap=tk.WORD, 
                                                height=15, width=60, bg="#FFF0F5", font=("Arial", 10))
        self.canvas.create_window(300, 440, window=self.display)

        self.entry = tk.Entry(self.root, font=("Helvetica", 12), width=45)
        self.entry.bind("<Return>", lambda e: self.send_message())
        self.canvas.create_window(250, 640, window=self.entry)

        self.send_btn = tk.Button(self.root, text="SEND", command=self.send_message, 
                                  bg="#DB7093", fg="white", font=("Helvetica", 10, "bold"), width=8)
        self.canvas.create_window(520, 640, window=self.send_btn)

        t = threading.Thread(target=self.setup_connection, daemon=True)
        t.start()

    def load_background(self):
        try:
            img = Image.open(self.bg_image_name).convert("RGBA")
            img = img.resize((600, 700), Image.Resampling.LANCZOS)
            r, g, b, alpha = img.split()
            opacity_factor = 0.2 
            new_alpha = alpha.point(lambda p: int(p * opacity_factor))
            img.putalpha(new_alpha)
            self.bg_photo = ImageTk.PhotoImage(img)
            self.canvas.create_image(0, 0, image=self.bg_photo, anchor="nw")
        except:
            self.canvas.config(bg="#FFB6C1")

    def load_item_image(self, path):
        try:
            full_path = os.path.join(os.getcwd(), path)
            img = Image.open(full_path).resize((300, 200), Image.Resampling.LANCZOS)
            self.item_photo = ImageTk.PhotoImage(img)
            self.img_label.config(image=self.item_photo)
            self.img_label.image = self.item_photo 
        except:
            self.img_label.config(text=f"Missing: {path}", bg="white")

    def setup_connection(self):
        try:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock = context.wrap_socket(raw_sock, server_hostname='localhost')
            self.sock.connect(('127.0.0.1', 8443)) 
            self.root.after(0, lambda: LoginWindow(self.root, self.send_credentials))
        except:
            os._exit(0)

    def send_credentials(self, u, p):
        try:
            if self.sock.recv(1024).decode() == "AUTH_REQUEST":
                self.sock.sendall(f"{u}|{p}".encode())
                resp = self.sock.recv(1024).decode()
                if resp == "AUTH_SUCCESS":
                    self.root.deiconify()
                    threading.Thread(target=self.receive_loop, daemon=True).start()
                else:
                    messagebox.showerror("Error", "Invalid Login")
        except:
            os._exit(0)

    def clear_chat(self):
        self.display.config(state='normal')
        self.display.delete('1.0', tk.END)
        self.display.config(state='disabled')

    def receive_loop(self):
        while True:
            try:
                data = self.sock.recv(4096).decode()
                if not data:
                    os._exit(0)
                
                for msg in data.split('\n'):
                    msg = msg.strip()
                    if not msg: continue

                    if "SET_ITEM|" in msg:
                        parts = msg.split("|")
                        if len(parts) >= 3:
                            i_name = parts[1]
                            i_path = parts[2]
                            self.fireworks_active = False
                            self.display.config(state='normal')
                            self.display.delete('1.0', tk.END)
                            self.display.config(state='disabled')
                            self.root.after(0, lambda n=i_name: self.item_label.config(text=f"CURRENT ITEM: {n}"))
                            self.root.after(0, lambda p=i_path: self.load_item_image(p))
                    elif "NEXT_ROUND_PREP" in msg:
                        self.fireworks_active = False
                        self.root.after(0, self.clear_chat)
                    elif "SHUTDOWN_NOW" in msg:
                        os._exit(0)
                    elif "SHOW_FIREWORKS" in msg:
                        self.fireworks_active = True
                        self.root.after(0, self.trigger_fireworks)
                    elif any(tag in msg for tag in ["[NOTICE]", "[LIVE]", "[TIMER]", "[ALERT]"]):
                        self.root.after(0, self.show_popup_alert, msg)
                    else:
                        self.root.after(0, self.update_display, msg)
            except:
                os._exit(0)

    def trigger_fireworks(self):
        def loop():
            if self.fireworks_active:
                self.create_firework_at_random()
                self.root.after(500, loop)
        loop()

    def create_firework_at_random(self):
        x = random.randint(50, 550)
        y = random.randint(50, 450)
        color = random.choice(["#FF1493", "#FFD700", "#00FFFF", "#ADFF2F", "#FF4500", "#FFFFFF"])
        self.create_firework(x, y, color)

    def create_firework(self, x, y, color):
        particles = []
        for _ in range(15):
            p = self.canvas.create_oval(x, y, x+6, y+6, fill=color, outline="")
            vx = random.uniform(-7, 7)
            vy = random.uniform(-7, 7)
            particles.append((p, vx, vy))
        
        def animate(step=0):
            if self.root.winfo_exists() and self.fireworks_active:
                if step < 30:
                    for p, vx, vy in particles:
                        self.canvas.move(p, vx, vy)
                    self.root.after(40, lambda: animate(step + 1))
                else:
                    for p, _, _ in particles:
                        self.canvas.delete(p)
            else:
                for p, _, _ in particles:
                    self.canvas.delete(p)
        animate()

    def show_popup_alert(self, text):
        self.root.update_idletasks()
        popup = tk.Toplevel(self.root)
        popup.overrideredirect(True)
        popup.attributes("-topmost", True)
        
        box_x = self.display.winfo_rootx()
        box_y = self.display.winfo_rooty()
        box_w = self.display.winfo_width()
        box_h = self.display.winfo_height()
        
        pop_w = 320
        pop_h = 90
        x = box_x + (box_w // 2) - (pop_w // 2)
        y = box_y + (box_h // 2) - (pop_h // 2)
        
        popup.geometry(f"{pop_w}x{pop_h}+{x}+{y}")
        f = tk.Frame(popup, bg="white", padx=2, pady=2)
        f.pack(fill="both", expand=True)
        inner = tk.Frame(f, bg="#DB7093")
        inner.pack(fill="both", expand=True)
        
        l = tk.Label(inner, text=text, wraplength=280, bg="#DB7093", fg="white", 
                 font=("Helvetica", 11, "bold"))
        l.pack(expand=True)
        self.root.after(2500, popup.destroy)

    def update_display(self, text):
        self.display.config(state='normal')
        self.display.insert(tk.END, text + "\n")
        self.display.see(tk.END)
        self.display.config(state='disabled')

    def send_message(self):
        val = self.entry.get().strip()
        if val:
            try:
                self.sock.sendall(val.encode())
                self.entry.delete(0, tk.END)
            except:
                os._exit(0)

if __name__ == "__main__":
    root = tk.Tk()
    root.protocol("WM_DELETE_WINDOW", lambda: os._exit(0))
    app = AuctionClientGUI(root)
    root.mainloop()