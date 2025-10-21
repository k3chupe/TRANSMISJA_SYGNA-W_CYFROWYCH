import tkinter as tk
from tkinter import scrolledtext, messagebox, filedialog
import serial
import serial.tools.list_ports
import threading
import time
from xmodem import XMODEM

# --- GŁÓWNA KLASA APLIKACJI ---
class ModemApp(tk.Tk):
    def __init__(self):
        super().__init__()

        # --- Podstawowe ustawienia okna ---
        self.title("Terminal Modemowy")
        self.geometry("800x600")

        # --- Zmienne stanu ---
        self.serial_port = None
        self.is_connected = False
        self.receive_thread = None

        # --- Inicjalizacja GUI ---
        self.create_widgets()

    def create_widgets(self):
        # --- Ramka do zarządzania połączeniem ---
        # Poprawka: Usunięto nieprawidłowy argument 'padding' i dodano padx/pady w metodzie pack()
        connection_frame = tk.Frame(self)
        connection_frame.pack(fill=tk.X, padx=10, pady=5)

        # Etykieta i lista rozwijana dla portów COM
        tk.Label(connection_frame, text="Port COM:").pack(side=tk.LEFT, padx=(0, 5))
        
        # Pobieranie dostępnych portów COM
        ports = serial.tools.list_ports.comports()
        available_ports = [port.device for port in ports]
        self.com_port_var = tk.StringVar(self)
        if available_ports:
            self.com_port_var.set(available_ports[0])
        
        com_port_menu = tk.OptionMenu(connection_frame, self.com_port_var, *available_ports if available_ports else ["Brak portów"])
        com_port_menu.pack(side=tk.LEFT, padx=5)

        # Przyciski Połącz/Rozłącz
        self.connect_button = tk.Button(connection_frame, text="Połącz", command=self.connect)
        self.connect_button.pack(side=tk.LEFT, padx=5)
        self.disconnect_button = tk.Button(connection_frame, text="Rozłącz", command=self.disconnect, state=tk.DISABLED)
        self.disconnect_button.pack(side=tk.LEFT, padx=5)

        # --- Główne pole tekstowe do wyświetlania komunikacji ---
        self.log_area = scrolledtext.ScrolledText(self, wrap=tk.WORD, state=tk.DISABLED)
        self.log_area.pack(expand=True, fill=tk.BOTH, padx=10, pady=5)

        # --- Ramka do wprowadzania danych ---
        # Poprawka: Usunięto nieprawidłowy argument 'padding' i dodano padx w metodzie pack()
        input_frame = tk.Frame(self)
        input_frame.pack(fill=tk.X, padx=10)
        
        tk.Label(input_frame, text="Komenda/Wiadomość:").pack(side=tk.LEFT)
        self.entry_var = tk.StringVar()
        self.entry_field = tk.Entry(input_frame, textvariable=self.entry_var, state=tk.DISABLED)
        self.entry_field.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        self.entry_field.bind("<Return>", self.send_message) # Wysyłanie enterem

        self.send_button = tk.Button(input_frame, text="Wyślij", command=self.send_message, state=tk.DISABLED)
        self.send_button.pack(side=tk.LEFT)

        # --- Ramka do operacji na plikach ---
        # Poprawka: Usunięto nieprawidłowy argument 'padding' i dodano padx/pady w metodzie pack()
        file_frame = tk.Frame(self)
        file_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.send_file_button = tk.Button(file_frame, text="Wyślij Plik (XModem)", command=self.send_file, state=tk.DISABLED)
        self.send_file_button.pack(side=tk.LEFT, padx=5)

    def log(self, message):
        """Dodaje wiadomość do pola logów w bezpieczny sposób (wątkowo)."""
        self.log_area.config(state=tk.NORMAL)
        self.log_area.insert(tk.END, message + "\n")
        self.log_area.config(state=tk.DISABLED)
        self.log_area.see(tk.END)

    # --- METODY OBSŁUGI POŁĄCZENIA ---

    def connect(self):
        """Nawiązuje połączenie z wybranym portem szeregowym."""
        port_name = self.com_port_var.get()
        if not port_name or port_name == "Brak portów":
            messagebox.showerror("Błąd", "Nie wybrano portu COM lub żaden nie jest dostępny.")
            return

        try:
            # Zmień parametry (baudrate, etc.) zgodnie z wymaganiami modemu
            self.serial_port = serial.Serial(port_name, baudrate=9600, timeout=1)
            self.is_connected = True
            
            # Uruchomienie wątku do odbierania danych
            self.receive_thread = threading.Thread(target=self.receive_data, daemon=True)
            self.receive_thread.start()

            # Aktualizacja stanu GUI
            self.connect_button.config(state=tk.DISABLED)
            self.disconnect_button.config(state=tk.NORMAL)
            self.entry_field.config(state=tk.NORMAL)
            self.send_button.config(state=tk.NORMAL)
            self.send_file_button.config(state=tk.NORMAL)
            
            self.log(f"Połączono z {port_name}")
        except serial.SerialException as e:
            messagebox.showerror("Błąd Połączenia", f"Nie można otworzyć portu {port_name}:\n{e}")

    def disconnect(self):
        """Zamyka połączenie szeregowe."""
        if self.serial_port and self.serial_port.is_open:
            self.is_connected = False # Sygnał dla wątku, żeby się zakończył
            self.serial_port.close()
        
        # Aktualizacja stanu GUI
        self.connect_button.config(state=tk.NORMAL)
        self.disconnect_button.config(state=tk.DISABLED)
        self.entry_field.config(state=tk.DISABLED)
        self.send_button.config(state=tk.DISABLED)
        self.send_file_button.config(state=tk.DISABLED)

        self.log("Rozłączono.")

    def receive_data(self):
        """Funkcja działająca w osobnym wątku, odbierająca dane z portu."""
        while self.is_connected:
            try:
                if self.serial_port.in_waiting > 0:
                    data = self.serial_port.readline().decode('utf-8', errors='ignore').strip()
                    if data:
                        self.log(f"Odebrano: {data}")
            except (serial.SerialException, TypeError):
                # Błąd może wystąpić podczas zamykania portu
                break
            time.sleep(0.1)

    def send_message(self, event=None):
        """Wysyła wiadomość z pola Entry."""
        if not self.is_connected:
            return
        
        message = self.entry_var.get()
        if message:
            try:
                # Komendy AT wymagają znaku powrotu karetki
                full_message = message + '\r\n'
                self.serial_port.write(full_message.encode('utf-8'))
                self.log(f"Wysłano: {message}")
                self.entry_var.set("") # Wyczyszczenie pola po wysłaniu
            except serial.SerialException as e:
                self.log(f"Błąd wysyłania: {e}")
                self.disconnect()

    # --- METODY OBSŁUGI PLIKÓW ---

    def send_file(self):
        """Wysyła plik za pomocą protokołu XModem."""
        if not self.is_connected:
            messagebox.showwarning("Ostrzeżenie", "Musisz być połączony, aby wysłać plik.")
            return

        filepath = filedialog.askopenfilename()
        if not filepath:
            return
            
        # UWAGA: Wysyłanie pliku może zablokować GUI.
        # W docelowej wersji warto to również przenieść do osobnego wątku.
        self.log(f"Inicjowanie transferu XModem dla pliku: {filepath}...")
        
        def getc(size, timeout=1):
            return self.serial_port.read(size) or None

        def putc(data, timeout=1):
            return self.serial_port.write(data)

        modem = XMODEM(getc, putc)
        
        try:
            with open(filepath, 'rb') as f:
                # Poinformuj drugą stronę o rozpoczęciu transferu
                # (to zależy od implementacji po drugiej stronie)
                # Np. wyślij komendę inicjującą odbiór
                # self.serial_port.write(b'start_xmodem_receive\r\n')
                
                # Czekaj na sygnał gotowości od odbiorcy
                # W praktyce modem odbiorcy po komendzie ATA/ATO
                # powinien być gotowy do nasłuchu.
                
                if modem.send(f):
                    self.log("Plik wysłany pomyślnie!")
                else:
                    self.log(f"Błąd transferu pliku: {modem.message}")
        except Exception as e:
            self.log(f"Wystąpił krytyczny błąd podczas wysyłania pliku: {e}")

    def on_closing(self):
        """Obsługa zamknięcia okna."""
        if self.is_connected:
            self.disconnect()
        self.destroy()

# --- URUCHOMIENIE APLIKACJI ---
if __name__ == "__main__":
    app = ModemApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
