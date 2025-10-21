import tkinter as tk
from tkinter import scrolledtext, messagebox, filedialog, simpledialog
import serial
import serial.tools.list_ports
import threading
import time
from xmodem import XMODEM

# --- GŁÓWNA KLASA APLIKACJI ---
# Ta klasa dziedziczy po tk.Tk, co oznacza, że jest głównym oknem naszej aplikacji.
# Zawiera całą logikę i wszystkie elementy interfejsu graficznego (GUI).
class ModemApp(tk.Tk):
    # Metoda __init__ to konstruktor klasy. Wywołuje się automatycznie
    # przy tworzeniu nowego obiektu (naszej aplikacji).
    def __init__(self):
        super().__init__()

        # --- Podstawowe ustawienia okna ---
        self.title("Terminal Modemowy")
        self.geometry("800x600")

        # --- Zmienne stanu aplikacji ---
        # Te zmienne przechowują informacje o aktualnym stanie programu.
        self.serial_port = None          # Obiekt portu szeregowego (będzie tu, gdy się połączymy)
        self.is_connected = False        # Flaga, czy jesteśmy połączeni z portem COM
        self.in_chat_mode = False        # Flaga, czy modemy nawiązały połączenie i jesteśmy w trybie rozmowy
        self.receive_thread = None       # Wątek, który będzie nasłuchiwał na porcie szeregowym

        # --- Inicjalizacja GUI ---
        # Ta metoda tworzy i rozmieszcza wszystkie widżety (przyciski, pola tekstowe etc.)
        self.create_widgets()

    # Metoda odpowiedzialna za tworzenie interfejsu graficznego.
    def create_widgets(self):
        # --- Ramka 1: Zarządzanie połączeniem z portem COM ---
        connection_frame = tk.Frame(self)
        connection_frame.pack(fill=tk.X, padx=10, pady=5)

        tk.Label(connection_frame, text="Port COM:").pack(side=tk.LEFT, padx=(0, 5))
        
        # Automatyczne wyszukiwanie dostępnych portów COM w systemie
        available_ports = [port.device for port in serial.tools.list_ports.comports()]
        self.com_port_var = tk.StringVar(self)
        if available_ports:
            self.com_port_var.set(available_ports[0]) # Ustawia pierwszy znaleziony jako domyślny
        
        # Lista rozwijana do wyboru portu
        com_port_menu = tk.OptionMenu(connection_frame, self.com_port_var, *available_ports if available_ports else ["Brak portów"])
        com_port_menu.pack(side=tk.LEFT, padx=5)

        self.connect_button = tk.Button(connection_frame, text="Połącz z portem", command=self.connect)
        self.connect_button.pack(side=tk.LEFT, padx=5)
        self.disconnect_button = tk.Button(connection_frame, text="Rozłącz", command=self.disconnect, state=tk.DISABLED)
        self.disconnect_button.pack(side=tk.LEFT, padx=5)

        # KROK 4: Przycisk do czyszczenia logu
        self.clear_log_button = tk.Button(connection_frame, text="Wyczyść Log", command=self.clear_log)
        self.clear_log_button.pack(side=tk.LEFT, padx=10)

        # --- Ramka 2: Komendy modemu (ATD, ATA) ---
        # KROK 1: Dodanie przycisków do kluczowych komend
        modem_commands_frame = tk.Frame(self)
        modem_commands_frame.pack(fill=tk.X, padx=10, pady=5)

        self.dial_button = tk.Button(modem_commands_frame, text="Zadzwoń (ATD)", command=self.dial, state=tk.DISABLED)
        self.dial_button.pack(side=tk.LEFT, padx=5)

        self.answer_button = tk.Button(modem_commands_frame, text="Odbierz (ATA)", command=self.answer, state=tk.DISABLED)
        self.answer_button.pack(side=tk.LEFT, padx=5)
        
        self.hangup_button = tk.Button(modem_commands_frame, text="Rozłącz połączenie (ATH)", command=self.hangup, state=tk.DISABLED)
        self.hangup_button.pack(side=tk.LEFT, padx=5)

        # --- Główne pole tekstowe do wyświetlania komunikacji ---
        self.log_area = scrolledtext.ScrolledText(self, wrap=tk.WORD, state=tk.DISABLED, bg="#2b2b2b", fg="white", font=("Consolas", 10))
        self.log_area.pack(expand=True, fill=tk.BOTH, padx=10, pady=5)

        # --- Ramka 3: Wprowadzanie danych (czat / komendy) ---
        input_frame = tk.Frame(self)
        input_frame.pack(fill=tk.X, padx=10)
        
        tk.Label(input_frame, text="Komenda/Wiadomość:").pack(side=tk.LEFT)
        self.entry_var = tk.StringVar()
        self.entry_field = tk.Entry(input_frame, textvariable=self.entry_var, state=tk.DISABLED)
        self.entry_field.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        self.entry_field.bind("<Return>", self.send_message) # Umożliwia wysyłanie przez naciśnięcie Enter

        self.send_button = tk.Button(input_frame, text="Wyślij", command=self.send_message, state=tk.DISABLED)
        self.send_button.pack(side=tk.LEFT)

        # --- Ramka 4: Operacje na plikach (XModem) ---
        file_frame = tk.Frame(self)
        file_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.send_file_button = tk.Button(file_frame, text="Wyślij Plik (XModem)", command=self.send_file, state=tk.DISABLED)
        self.send_file_button.pack(side=tk.LEFT, padx=5)

        # KROK 3: Implementacja odbierania plików
        self.receive_file_button = tk.Button(file_frame, text="Odbierz Plik (XModem)", command=self.receive_file, state=tk.DISABLED)
        self.receive_file_button.pack(side=tk.LEFT, padx=5)

    # --- Metody pomocnicze i obsługi zdarzeń ---

    # Bezpieczna wątkowo metoda do dodawania tekstu do pola logów.
    def log(self, message, prefix=""):
        self.log_area.config(state=tk.NORMAL)
        # Dodaje timestamp dla lepszej czytelności
        timestamp = time.strftime("%H:%M:%S")
        self.log_area.insert(tk.END, f"[{timestamp}] {prefix}{message}\n")
        self.log_area.config(state=tk.DISABLED)
        self.log_area.see(tk.END) # Automatycznie przewija na dół

    # Metoda czyszcząca pole logów.
    def clear_log(self):
        self.log_area.config(state=tk.NORMAL)
        self.log_area.delete(1.0, tk.END)
        self.log_area.config(state=tk.DISABLED)

    # Metoda do wysyłania komend do modemu.
    def send_command(self, command):
        if not self.is_connected:
            return
        try:
            full_command = command + '\r\n' # Komendy AT wymagają znaku powrotu karetki
            self.serial_port.write(full_command.encode('utf-8'))
            self.log(f"Wysłano komendę: {command}")
        except serial.SerialException as e:
            self.log(f"Błąd wysyłania: {e}", "BŁĄD: ")
            self.disconnect()

    # --- Logika połączenia z portem COM ---

    # Nawiązuje połączenie z wybranym portem szeregowym.
    def connect(self):
        port_name = self.com_port_var.get()
        if not port_name or port_name == "Brak portów":
            messagebox.showerror("Błąd", "Nie wybrano portu COM lub żaden nie jest dostępny.")
            return

        try:
            # Parametry połączenia (można je zmienić w razie potrzeby)
            self.serial_port = serial.Serial(port_name, baudrate=9600, timeout=1)
            self.is_connected = True
            self.in_chat_mode = False # Resetujemy tryb czatu przy każdym nowym połączeniu
            
            # Uruchomienie wątku do odbierania danych w tle
            self.receive_thread = threading.Thread(target=self.receive_data, daemon=True)
            self.receive_thread.start()

            # Aktualizacja stanu GUI - włączamy/wyłączamy odpowiednie przyciski
            self.connect_button.config(state=tk.DISABLED)
            self.disconnect_button.config(state=tk.NORMAL)
            self.entry_field.config(state=tk.NORMAL)
            self.send_button.config(state=tk.NORMAL)
            self.dial_button.config(state=tk.NORMAL)
            self.answer_button.config(state=tk.NORMAL)
            
            self.log(f"Połączono z portem {port_name}", "SYSTEM: ")
        except serial.SerialException as e:
            messagebox.showerror("Błąd Połączenia", f"Nie można otworzyć portu {port_name}:\n{e}")

    # Zamyka połączenie z portem szeregowym.
    def disconnect(self):
        self.is_connected = False # Sygnał dla wątku, żeby się zakończył
        self.in_chat_mode = False
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
        
        # Aktualizacja stanu GUI
        self.connect_button.config(state=tk.NORMAL)
        self.disconnect_button.config(state=tk.DISABLED)
        self.entry_field.config(state=tk.DISABLED)
        self.send_button.config(state=tk.DISABLED)
        self.dial_button.config(state=tk.DISABLED)
        self.answer_button.config(state=tk.DISABLED)
        self.hangup_button.config(state=tk.DISABLED)
        self.send_file_button.config(state=tk.DISABLED)
        self.receive_file_button.config(state=tk.DISABLED)

        self.log("Rozłączono z portem.", "SYSTEM: ")

    # --- Logika komend modemu ---

    # Wysyła komendę ATD (Dial)
    def dial(self):
        number = simpledialog.askstring("Wybieranie numeru", "Wprowadź numer do wybrania:", parent=self)
        if number:
            self.send_command(f"ATD{number}")

    # Wysyła komendę ATA (Answer)
    def answer(self):
        self.send_command("ATA")

    # Wysyła komendę ATH (Hang up)
    def hangup(self):
        self.send_command("ATH")

    # --- Główna pętla odbierania danych ---

    # Ta funkcja działa w osobnym wątku, aby nie blokować interfejsu GUI.
    # Ciągle nasłuchuje na porcie szeregowym i przetwarza przychodzące dane.
    def receive_data(self):
        while self.is_connected:
            try:
                if self.serial_port.in_waiting > 0:
                    # Odczytujemy jedną linijkę danych
                    data = self.serial_port.readline().decode('utf-8', errors='ignore').strip()
                    if data:
                        # KROK 2: Usprawnienie trybu konwersacji
                        # Sprawdzamy, czy modem wszedł w tryb danych
                        if "CONNECT" in data:
                            self.in_chat_mode = True
                            self.log("Nawiązano połączenie modemowe. Tryb konwersacji włączony.", "SYSTEM: ")
                            # Po nawiązaniu połączenia włączamy przyciski do transferu plików i rozłączania
                            self.hangup_button.config(state=tk.NORMAL)
                            self.send_file_button.config(state=tk.NORMAL)
                            self.receive_file_button.config(state=tk.NORMAL)
                            continue # Nie wyświetlamy samej linii "CONNECT"

                        # Sprawdzamy, czy połączenie zostało zerwane
                        if "NO CARRIER" in data:
                            self.in_chat_mode = False
                            self.log("Połączenie modemowe zostało zerwane.", "SYSTEM: ")
                            self.hangup_button.config(state=tk.DISABLED)
                            self.send_file_button.config(state=tk.DISABLED)
                            self.receive_file_button.config(state=tk.DISABLED)
                            continue
                        
                        # Jeśli jesteśmy w trybie czatu, wyświetlamy dane "na czysto"
                        if self.in_chat_mode:
                            self.log(data, "Rozmówca: ")
                        else: # W przeciwnym razie, to odpowiedź modemu na komendę
                            self.log(data, "Modem: ")

            except (serial.SerialException, TypeError):
                break # Zakończ pętlę, jeśli port zostanie zamknięty
            time.sleep(0.1) # Krótka pauza, aby nie obciążać procesora

    # Wysyła wiadomość z pola Entry (dla komend lub czatu).
    def send_message(self, event=None):
        message = self.entry_var.get()
        if message:
            self.send_command(message) # Używamy send_command, bo zawsze wysyłamy linię
            self.entry_var.set("")

    # --- Logika transferu plików XModem ---

    # Wysyła plik.
    def send_file(self):
        filepath = filedialog.askopenfilename()
        if not filepath:
            return
        
        # Uruchamiamy transfer w osobnym wątku, aby nie blokować GUI
        transfer_thread = threading.Thread(target=self._send_file_worker, args=(filepath,), daemon=True)
        transfer_thread.start()

    # Prywatna metoda robocza do wysyłania pliku (działa w tle).
    def _send_file_worker(self, filepath):
        self.log(f"Inicjowanie transferu XModem dla pliku: {filepath}...", "PLIK: ")
        
        # Funkcje, które biblioteka xmodem będzie używać do komunikacji z portem
        def getc(size, timeout=1):
            return self.serial_port.read(size) or None

        def putc(data, timeout=1):
            return self.serial_port.write(data)

        modem = XMODEM(getc, putc)
        
        try:
            with open(filepath, 'rb') as f:
                if modem.send(f):
                    self.log("Plik wysłany pomyślnie!", "PLIK: ")
                else:
                    self.log(f"Błąd transferu pliku: {modem.message}", "BŁĄD PLIKU: ")
        except Exception as e:
            self.log(f"Wystąpił krytyczny błąd podczas wysyłania pliku: {e}", "BŁĄD PLIKU: ")

    # Odbiera plik.
    def receive_file(self):
        filepath = filedialog.asksaveasfilename()
        if not filepath:
            return

        # Uruchamiamy odbieranie w osobnym wątku
        transfer_thread = threading.Thread(target=self._receive_file_worker, args=(filepath,), daemon=True)
        transfer_thread.start()

    # Prywatna metoda robocza do odbierania pliku (działa w tle).
    def _receive_file_worker(self, filepath):
        self.log(f"Oczekiwanie na plik (XModem), zostanie zapisany jako: {filepath}...", "PLIK: ")
        
        def getc(size, timeout=15): # Dłuższy timeout na start transmisji
            return self.serial_port.read(size)

        def putc(data, timeout=15):
            return self.serial_port.write(data)

        modem = XMODEM(getc, putc)
        
        try:
            with open(filepath, 'wb') as f:
                if modem.recv(f):
                    self.log("Plik odebrany pomyślnie!", "PLIK: ")
                else:
                    self.log(f"Błąd odbioru pliku: {modem.message}", "BŁĄD PLIKU: ")
        except Exception as e:
            self.log(f"Wystąpił krytyczny błąd podczas odbioru pliku: {e}", "BŁĄD PLIKU: ")

    # Obsługa zamknięcia okna.
    def on_closing(self):
        if self.is_connected:
            self.disconnect()
        self.destroy()

# --- URUCHOMIENIE APLIKACJI ---
if __name__ == "__main__":
    app = ModemApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
