import tkinter as tk
from tkinter import ttk, messagebox
import os

import cv2
import face_recognition
import threading
import sqlite3
import 
from datetime import datetime
import string
import ctypes
from ctypes import windll
import requests

# === Конфигурация ===
ACCESS_LEVELS = {
    "azaza1": [r"C:\Users\ASHTRAY\Azanbayev_Dipl\azaza\level_1", r"C:\STEAM", r"C:/"],
    "azaza2": [r"C:\Users\ASHTRAY\Azanbayev_Dipl\azaza\level_1", r"C:\Games"],
    "azaza3": [r"C:\Users\ASHTRAY\Azanbayev_Dipl\azaza\level_2"]
}

TELEGRAM_BOT_TOKEN = "8104290452:AAHCx_nFt_Y8VJntCY2bfWiaBRnLyOgHNfM"
# Ваш chat_id (получить можно через @userinfobot или @getmyid_bot)
TELEGRAM_CHAT_ID = "5415707803"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(SCRIPT_DIR, "access_logs.db")
PHOTOS_DIR = r"C:\Users\ASHTRAY\Azanbayev_Dipl\access_denied_photos"

REFERENCE_FOLDERS = [
    r"C:\Users\ASHTRAY\Azanbayev_Dipl\azaza\azaza1",
    r"C:\Users\ASHTRAY\Azanbayev_Dipl\azaza\azaza2",
    r"C:\Users\ASHTRAY\Azanbayev_Dipl\azaza\azaza3"
]

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text
    }
    try:
        resp = requests.post(url, data=payload, timeout=5)
        print(f"[TELEGRAM DEBUG] {resp.status_code} {resp.text}")
    except Exception as e:
        print(f"[TELEGRAM ERROR] {e}")

if __name__ == "__main__":
    send_telegram_message("Тестовое сообщение от Python!")
    
class AccessLogger:
    def __init__(self):
        self.db_name = DATABASE_PATH
        self._init_database()

    def _init_database(self):
        os.makedirs(os.path.dirname(self.db_name), exist_ok=True)
        if os.path.exists(self.db_name):
            import stat
            os.chmod(self.db_name, stat.S_IWRITE | stat.S_IREAD)
        with sqlite3.connect(self.db_name) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT, filepath TEXT, status TEXT, reason TEXT,
                    rank TEXT, timestamp TEXT, photo_path TEXT
                )
            """)

    def log_attempt(self, username, filepath, status, reason, rank, photo_path=""):
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with sqlite3.connect(self.db_name) as conn:
                conn.execute("""
                    INSERT INTO logs (username, filepath, status, reason, rank, timestamp, photo_path)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (username, filepath, status, reason, rank, timestamp, photo_path))
            print(f"[LOG] {username} -> {status} -> {filepath}")
            msg = (f"User: {username}\n"
                   f"Path: {filepath}\n"
                   f"Status: {status}\n"
                   f"Reason: {reason}\n"
                   f"Rank: {rank}\n"
                   f"Timestamp: {timestamp}\n"
                   f"Photo: {photo_path if photo_path else 'N/A'}")
            send_telegram_message(msg)
        except Exception as e:
            print(f"[ERROR] Logging failed: {e}")

    def get_all_logs(self):
        try:
            with sqlite3.connect(self.db_name) as conn:
                return conn.execute("""
                    SELECT id, username, filepath, status, reason, timestamp, photo_path 
                    FROM logs ORDER BY id DESC
                """).fetchall()
        except Exception:
            return []

class FaceAuthenticator:
    def __init__(self, reference_folders):
        self.reference_folders = reference_folders
        self.known_encodings = []
        self.known_labels = []
        self._load_references()

    def _load_references(self):
        print(f"[DEBUG] Папки для загрузки: {self.reference_folders}")
        loaded = 0
        for person_folder in self.reference_folders:
            print(f"[DEBUG] Читаем папку: {person_folder}")
            person = os.path.basename(person_folder)
            if not os.path.isdir(person_folder):
                print(f"[WARNING] Не найдена папка: {person_folder}")
                continue
            for img_name in os.listdir(person_folder):
                print(f"[DEBUG] Файл: {img_name}")
                if not img_name.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp')):
                    continue
                try:
                    img_path = os.path.join(person_folder, img_name)
                    print(f"[DEBUG] Пробуем загрузить: {img_path}")
                    img = face_recognition.load_image_file(img_path)
                    encodings = face_recognition.face_encodings(img)
                    if encodings:
                        self.known_encodings.append(encodings[0])
                        self.known_labels.append(person)
                        print(f"[LOADED] {person} from {img_name}")
                        loaded += 1
                    else:
                        print(f"[NO FACE] {img_path}")
                except Exception as e:
                    print(f"[ERROR] Loading {img_name}: {e}")

        print(f"[INFO] Total faces loaded: {len(self.known_encodings)}")
        if loaded == 0:
            print("[ERROR] No reference faces loaded!")

    def authenticate(self):
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            return "unknown_no_camera", None
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        recognized_user = None
        best_frame = None
        face_detected = False
        start_time = time.time()
        frame_count = 0
        while time.time() - start_time < 7:
            ret, frame = cap.read()
            if not ret:
                break
            frame_count += 1
            if frame_count % 3 != 0:
                continue
            small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
            rgb_small = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
            faces = face_recognition.face_locations(rgb_small)
            encodings = face_recognition.face_encodings(rgb_small, faces)
            if faces:
                face_detected = True
                best_frame = frame.copy()
                for encoding in encodings:
                    matches = face_recognition.compare_faces(self.known_encodings, encoding, tolerance=0.4)
                    if any(matches):
                        recognized_user = self.known_labels[matches.index(True)]
                        break
            cv2.imshow("Распознавание лица", frame)
            if cv2.waitKey(1) & 0xFF == 27 or recognized_user:
                break
        cap.release()
        cv2.destroyAllWindows()
        if recognized_user:
            return recognized_user, best_frame
        elif face_detected:
            return "unknown_face_detected", best_frame
        else:
            return "unknown_no_face", best_frame

class CustomExplorer:
    def __init__(self, root):
        self.root = root
        self.root.title("Custom Explorer with Face Access")
        self.root.geometry("900x600")
        self.root.configure(bg="#f2f2f2")
        self.logger = AccessLogger()
        self.authenticator = FaceAuthenticator(REFERENCE_FOLDERS)
        self._ensure_photos_dir()
        self._setup_ui()
        print(f"[INFO] Found {len(self.logger.get_all_logs())} existing logs")

    def _ensure_photos_dir(self):
        try:
            os.makedirs(PHOTOS_DIR, exist_ok=True)
            # Проверка возможности записи
            test_path = os.path.join(PHOTOS_DIR, "test_write.txt")
            with open(test_path, "w") as f:
                f.write("test")
            os.remove(test_path)
            print("[DEBUG] Папка для фото доступна для записи!")
        except Exception as e:
            print(f"[ERROR] Не удалось создать папку или записать файл для фото: {e}")

    def _setup_ui(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", font=("Segoe UI", 10), rowheight=26)
        style.configure("Treeview.Heading", font=("Segoe UI", 11, "bold"))
        self.tree = ttk.Treeview(self.root)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.tree.bind("<<TreeviewOpen>>", self._lazy_load)
        self.tree.bind("<Double-1>", self._on_double_click)
        self._populate_tree()

    def _populate_tree(self):
        bitmask = windll.kernel32.GetLogicalDrives()
        for i in range(26):
            if bitmask & (1 << i):
                drive = f"{string.ascii_uppercase[i]}:/"
                node = self.tree.insert("", "end", text=drive, values=[drive], open=False)
                self.tree.insert(node, "end")

    def _lazy_load(self, event):
        node = self.tree.focus()
        path = self.tree.item(node, "values")[0]
        self.tree.delete(*self.tree.get_children(node))
        try:
            for entry in os.listdir(path):
                full_path = os.path.join(path, entry)
                if os.path.isdir(full_path) or os.path.isfile(full_path):
                    self.tree.insert(node, "end", text=entry, values=[full_path])
        except Exception as e:
            print(f"[ERROR] Access denied: {e}")

    def _on_double_click(self, event):
        node = self.tree.focus()
        if not node:
            return
        path = self.tree.item(node, "values")[0]
        threading.Thread(target=self._authenticate_and_open, args=(path,), daemon=True).start()

    def _authenticate_and_open(self, path):
        try:
            user, frame = self.authenticator.authenticate()
            photo_path = self._save_frame(frame, user or "unknown") if frame is not None else ""
            if user in ["unknown_no_face", "unknown_face_detected", "unknown_no_camera", None]:
                reason = "Камера недоступна" if user == "unknown_no_camera" else "Лицо не распознано"
                self.logger.log_attempt("unknown", path, "Отказано", reason, "unknown", photo_path)
                error_msg = "Не удалось распознать лицо." if user != "unknown_no_camera" else "Камера недоступна."
                self.root.after(0, lambda: messagebox.showerror("Ошибка доступа", error_msg))
                return
            allowed_paths = ACCESS_LEVELS.get(user, [])
            has_access = any(path.startswith(p) for p in allowed_paths)
            if has_access:
                try:
                    self.logger.log_attempt(user, path, "Доступ разрешен", "ОК", user, photo_path)
                    os.startfile(path)
                except Exception as e:
                    self.root.after(0, lambda: messagebox.showerror("Ошибка", f"Не удалось открыть: {e}"))
            else:
                self.logger.log_attempt(user, path, "Отказано", "Доступ запрещен", user, photo_path)
                self.root.after(0, lambda: messagebox.showerror("Доступ запрещен", 
                    f"Пользователь '{user}' не имеет доступа к:\n{path}"))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Ошибка", f"Ошибка аутентификации: {e}"))

    def _save_frame(self, frame, user_label):
        """
        Сохраняет кадр из камеры в папку PHOTOS_DIR.
        Возвращает полный путь к файлу или пустую строку, если сохранение не удалось.
        """
        # Проверка папки
        try:
            os.makedirs(PHOTOS_DIR, exist_ok=True)
            test_path = os.path.join(PHOTOS_DIR, "test_write.txt")
            with open(test_path, "w") as f:
                f.write("test")
            os.remove(test_path)
            print("[DEBUG] Папка доступна для записи!")
        except Exception as e:
            print(f"[DEBUG] Нет доступа к папке: {e}")
            return ""
        # Проверка кадра
        if frame is None:
            print("[DEBUG] Frame is None!")
            return ""
        if not hasattr(frame, 'shape'):
            print("[DEBUG] Frame has no shape!")
            return ""
        print(f"[DEBUG] Frame shape: {frame.shape}, dtype: {getattr(frame, 'dtype', 'unknown')}")
        # Сохраняем файл
        try:
            filename = f"{user_label}_{int(time.time())}.jpg"
            full_path = os.path.join(PHOTOS_DIR, filename)
            saved = cv2.imwrite(full_path, frame)
            print(f"[DEBUG] Попытка cv2.imwrite: {saved}, путь: {full_path}")
            if saved and os.path.exists(full_path):
                print(f"[PHOTO] Saved: {full_path} ({os.path.getsize(full_path)} bytes)")
                return full_path
            else:
                print(f"[ERROR] Не удалось сохранить фото по пути: {full_path}")
        except Exception as e:
            print(f"[ERROR] Photo save failed: {e}")
        return ""

def protect_file_deletion():
    protect_path = r"C:/Users/ASHTRAY/Desktop"
    if not os.path.exists(protect_path):
        return
    excluded_paths = [DATABASE_PATH, PHOTOS_DIR, SCRIPT_DIR]
    protected_count = 0
    for root_dir, dirs, files in os.walk(protect_path):
        for file in files:
            file_path = os.path.join(root_dir, file)
            if any(file_path.startswith(exc) for exc in excluded_paths):
                continue
            try:
                ctypes.windll.kernel32.SetFileAttributesW(str(file_path), 0x01)
                protected_count += 1
            except:
                pass
    print(f"[INFO] Protected {protected_count} files")
    if os.path.exists(DATABASE_PATH):
        import stat
        os.chmod(DATABASE_PATH, stat.S_IWRITE | stat.S_IREAD)

if __name__ == "__main__":
    print("[INFO] Starting Face Recognition Explorer...")
    protect_file_deletion()
    root = tk.Tk()
    app = CustomExplorer(root)
    root.mainloop()