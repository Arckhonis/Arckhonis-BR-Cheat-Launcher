import os
import ctypes
import shutil
import json
import subprocess
import sys
from pathlib import Path
import threading
import winreg
import requests
import tkinter as tk
from tkinter import messagebox, ttk

GAME_ID = "2835570"
GAME_NAME = "Buckshot Roulette"
REPO_API_URL = "https://api.github.com/repos/Arckhonis/Arckhonis-BR-Cheat/releases/latest"
PATCH_FILE = "patch.xdelta"
BINARY_FILE = "Arckhonis BR Cheat.exe"


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


def get_steam_path():
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\\WOW6432Node\\Valve\\Steam") as key:
            steam_path, _ = winreg.QueryValueEx(key, "InstallPath")
            return Path(steam_path)
    except FileNotFoundError:
        messagebox.showerror(
            "Error", "Steam installation not found in registry.")
        sys.exit(1)


def get_game_path():
    steam_path = get_steam_path()
    library_folders = steam_path / "steamapps" / "libraryfolders.vdf"
    if not library_folders.exists():
        messagebox.showerror("Error", "Steam library folders file not found.")
        sys.exit(1)

    with open(library_folders, "r", encoding="utf-8") as file:
        content = file.read()

    libraries = []
    for line in content.splitlines():
        if "path" in line:
            libraries.append(Path(line.split('"')[3]) / "steamapps" / "common")

    for library in libraries:
        game_path = library / GAME_NAME
        if game_path.exists():
            return game_path

    messagebox.showerror(
        "Error", f"{GAME_NAME} not found in any Steam library.")
    sys.exit(1)


def get_latest_patch_info():
    try:
        response = requests.get(REPO_API_URL)
        response.raise_for_status()
        data = response.json()
        for asset in data.get("assets", []):
            if asset["name"] == PATCH_FILE:
                return asset
        return None
    except Exception as e:
        messagebox.showerror(
            "Error", f"Failed to fetch release information: {e}")
        return None


def download_patch_file(url, progress, status_label):
    try:
        progress["mode"] = "determinate"
        response = requests.get(url, stream=True)
        response.raise_for_status()

        total_size = int(response.headers.get("content-length", 0))
        chunk_size = 1024
        downloaded_size = 0
        content = bytearray()

        for chunk in response.iter_content(chunk_size=chunk_size):
            content.extend(chunk)
            downloaded_size += len(chunk)
            if total_size > 0:
                progress_value = int((downloaded_size / total_size) * 100)
                progress["value"] = progress_value
                status_label.config(
                    text=f"Downloading patch... {progress_value}%")
                progress.update()

        progress["mode"] = "indeterminate"
        return bytes(content)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to download patch file: {e}")
        progress["mode"] = "indeterminate"
        return None


def is_patch_up_to_date(local_patch):
    meta_file = f"{local_patch}.meta"

    try:
        with open(meta_file, "r", encoding="utf-8") as meta:
            metadata = json.load(meta)
        patch_info = get_latest_patch_info()
        if patch_info:
            return metadata.get("id") == patch_info["id"]
    except (FileNotFoundError, json.JSONDecodeError):
        return False


def save_patch_metadata(local_patch, patch_metadata):
    meta_file = f"{local_patch}.meta"
    with open(meta_file, "w", encoding="utf-8") as meta:
        json.dump(patch_metadata, meta)


def apply_patch(game_path, local_patch):
    xdelta_path = resource_path("xdelta.exe")
    original_file = game_path / \
        "Buckshot Roulette_windows" / f"{GAME_NAME}.exe"
    output_file = game_path / "Arckhonis BR Cheat Cache" / BINARY_FILE

    try:
        subprocess.run([xdelta_path, "-f", "-d", "-s", original_file,
                       local_patch, output_file], check=True)
        messagebox.showinfo("Success", "Game patched successfully!")
        return True
    except subprocess.CalledProcessError as e:
        messagebox.showerror("Error", f"Failed to apply patch: {e}")
        return False


def perform_update_and_patch(root, button, progress, status_label, game_path):
    button.config(state=tk.DISABLED)
    progress.start()
    status_label.config(text="Checking for updates...")

    def task():
        try:
            cached_dir = game_path / "Arckhonis BR Cheat Cache"
            cached_dir.mkdir(exist_ok=True)

            local_patch = cached_dir / PATCH_FILE
            patch_info = get_latest_patch_info()

            if patch_info is None:
                if local_patch.exists():
                    status_label.config(text="Launching game...")
                    play_game(root, game_path, status_label)
                else:
                    messagebox.showerror(
                        "Error", "Patch file not found in the repository and no local version is available.")
            else:
                status_label.config(text="Downloading patch...")
                repo_patch = download_patch_file(
                    patch_info["browser_download_url"], progress, status_label)
                if repo_patch is None:
                    return

                with open(local_patch, "wb") as file:
                    file.write(repo_patch)

                meta_file = f"{local_patch}.meta"
                with open(meta_file, "w", encoding="utf-8") as meta:
                    json.dump(patch_info, meta)

                status_label.config(text="Applying patch...")
                if apply_patch(game_path, local_patch):
                    status_label.config(text="Launching game...")
                    play_game(root, game_path, status_label)
        finally:
            progress.stop()
            button.config(state=tk.NORMAL)
            update_button_state(root, button, progress,
                                status_label, game_path)

    threading.Thread(target=task, daemon=True).start()


def ensure_libraries(game_path):
    cache_dir = game_path / "Arckhonis BR Cheat Cache"
    game_dir = game_path / "Buckshot Roulette_windows"

    steam_api_file = game_dir / "steam_api64.dll"
    cached_steam_api_file = cache_dir / "steam_api64.dll"

    godotsteam_url = "https://github.com/Arckhonis/Arckhonis-BR-Cheat/releases/download/v1.0.0/godotsteam.x86_64.dll"
    cached_godotsteam_file = cache_dir / "godotsteam.x86_64.dll"

    cache_dir.mkdir(parents=True, exist_ok=True)

    if not cached_godotsteam_file.exists():
        try:
            response = requests.get(godotsteam_url, stream=True)
            response.raise_for_status()
            with open(cached_godotsteam_file, "wb") as f:
                shutil.copyfileobj(response.raw, f)
        except Exception as e:
            pass

    if not cached_steam_api_file.exists():
        if steam_api_file.exists():
            try:
                shutil.copy(steam_api_file, cached_steam_api_file)
            except Exception as e:
                pass


def play_game(root, game_path, status_label):
    try:
        status_label.config(text="Launching game...")
        game_directory = game_path / "Buckshot Roulette_windows"

        ensure_libraries(game_path)
        root.withdraw()
        subprocess.Popen([game_path / "Arckhonis BR Cheat Cache" /
                         BINARY_FILE], cwd=game_directory).wait()
        root.deiconify()
    except Exception as e:
        root.deiconify()
        messagebox.showerror("Error", f"Failed to launch the game: {e}")


def perform_patch(root, button, progress, status_label, game_path):
    button.config(state=tk.DISABLED)
    progress.start()

    def task():
        try:
            cached_dir = game_path / "Arckhonis BR Cheat Cache"
            cached_dir.mkdir(exist_ok=True)

            local_patch = cached_dir / PATCH_FILE

            status_label.config(text="Applying patch...")
            if apply_patch(game_path, local_patch):
                status_label.config(text="Launching game...")
                play_game(root, game_path, status_label)
        finally:
            progress.stop()
            button.config(state=tk.NORMAL)
            update_button_state(root, button, progress,
                                status_label, game_path)

    threading.Thread(target=task, daemon=True).start()


def update_button_state(root, button, progress, status_label, game_path):
    local_patch_path = game_path / "Arckhonis BR Cheat Cache" / PATCH_FILE
    local_binary_path = game_path / "Arckhonis BR Cheat Cache" / BINARY_FILE

    if not local_patch_path.exists():
        button.config(text="⤓ Download Cheat", bg="#2196F3",
                      command=lambda: perform_update_and_patch(root, button, progress, status_label, game_path))

    elif not is_patch_up_to_date(local_patch_path):
        button.config(text="Update", bg="#FFC107",
                      command=lambda: perform_update_and_patch(root, button, progress, status_label, game_path))

    elif not local_binary_path.exists():
        button.config(text="Patch", bg="#2196F3", fg="white",
                      command=lambda: perform_patch(root, button, progress, status_label, game_path))

    else:
        button.config(text="► Play", bg="#4CAF50", fg="white",
                      command=lambda: play_game(root, game_path, status_label))


# Some Fucking ChatGPT WinAPI Magic lol
GWL_STYLE = -16
WS_OVERLAPPED = 0x00000000
WS_CAPTION = 0x00C00000
WS_SYSMENU = 0x00080000
WS_MINIMIZEBOX = 0x00020000


def remove_titlebar(root):
    hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
    style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_STYLE)

    new_style = style & ~WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX
    ctypes.windll.user32.SetWindowLongW(hwnd, GWL_STYLE, new_style)

    # ctypes.windll.user32.SetWindowPos(
    #     hwnd, 0, 0, 0, 0, 0,
    #     0x0027
    # )


def main():

    root = tk.Tk()

    icon_path = resource_path("Arckhonis.ico")

    if Path(icon_path).exists():
        root.iconbitmap(icon_path)
    else:
        print(f"File not found: {icon_path}")

    root.eval('tk::PlaceWindow . center')

    root.geometry(f"+{root.winfo_x() - 100}+{root.winfo_y()}")

    root.resizable(False, False)
    root.update_idletasks()
    root.title("Arckhonis BR Cheat Launcher")
    root.geometry("400x200")
    root.configure(bg="#000000")

    root.after(10, lambda: remove_titlebar(root))

    def close_app():
        root.destroy()

    def minimize_app():
        # root.withdraw()
        root.iconify()

    # After ChatGPT Magic movement looks horrible. Do not uncomment this and don't try this at home kids!
    # def start_move(event):
    #     root.x = event.x
    #     root.y = event.y

    # def stop_move(event):
    #     root.x = None
    #     root.y = None

    # def do_move(event):
    #     x = root.winfo_pointerx() - root.x
    #     y = root.winfo_pointery() - root.y
    #     root.geometry(f"+{x}+{y}")

    # def do_move_label(event):
    #     x = root.winfo_pointerx() - root.x - 55
    #     y = root.winfo_pointery() - root.y
    #     root.geometry(f"+{x}+{y}")

    title_bar = tk.Frame(root, bg="#0f0f0f", relief="flat", height=30)
    title_bar.pack(fill=tk.X, side=tk.TOP)
    # title_bar.bind("<Button-1>", start_move)
    # title_bar.bind("<B1-Motion>", do_move)

    close_button = tk.Button(title_bar, text="✖", bg="#0f0f0f", fg="#ff0000", font=("Courier New", 10),
                             command=close_app, borderwidth=0, activebackground="#800000")

    close_button.pack(side=tk.RIGHT, padx=5, pady=2)

    minimize_button = tk.Button(title_bar, text="-", bg="#0f0f0f", fg="white", font=(
        "Arial", 12), command=minimize_app, borderwidth=0, activebackground="#555555")
    minimize_button.pack(side=tk.RIGHT)

    title_label = tk.Label(title_bar, text="Arckhonis BR Cheat Launcher",
                           bg="#0f0f0f", fg="#00ff00", font=("Courier New", 14))

    # title_label.bind("<Button-1>", start_move)
    # title_label.bind("<B1-Motion>", do_move_label)
    title_label.pack(side=tk.RIGHT, padx=10)

    status_label = tk.Label(root, text="", font=(
        "Courier New", 10), fg="#FFFFFF", bg="#000000")
    status_label.pack(pady=10)

    progress = ttk.Progressbar(root, mode="indeterminate", length=200)
    progress.pack(pady=10)

    button = tk.Button(root, font=("Courier New", 12))
    button.pack(pady=10)

    game_path = get_game_path()
    update_button_state(root, button, progress, status_label, game_path)

    root.mainloop()


if __name__ == "__main__":
    main()
