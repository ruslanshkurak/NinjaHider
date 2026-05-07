import ctypes
from ctypes import wintypes
import keyboard
import subprocess
import os
import sys

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# Настройка для SetWindowLongPtrW
try:
    user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
    user32.SetWindowLongPtrW.restype = ctypes.c_void_p
    user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.GetWindowLongPtrW.restype = ctypes.c_void_p
except AttributeError:
    # 32-bit fallback
    user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
    user32.SetWindowLongW.restype = ctypes.c_void_p

# Настройка типов возвращаемых значений и аргументов для 64-битной Windows!
# Это критически важно для внедрения DLL, иначе адреса обрезаются и происходит сбой.
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.VirtualAllocEx.restype = ctypes.c_void_p
kernel32.VirtualAllocEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD, wintypes.DWORD]
kernel32.VirtualFreeEx.restype = wintypes.BOOL
kernel32.VirtualFreeEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD]
kernel32.WriteProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_char_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
kernel32.GetModuleHandleW.restype = wintypes.HMODULE
kernel32.GetProcAddress.restype = ctypes.c_void_p
kernel32.GetProcAddress.argtypes = [wintypes.HMODULE, ctypes.c_char_p]
kernel32.CreateRemoteThread.restype = wintypes.HANDLE
kernel32.CreateRemoteThread.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetWindowLongW.restype = wintypes.DWORD
user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.DWORD]
user32.SetWindowLongW.restype = wintypes.DWORD
kernel32.GetConsoleWindow.restype = wintypes.HWND
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.ShowWindow.restype = wintypes.BOOL
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = wintypes.BOOL
user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
user32.SetWindowPos.restype = wintypes.BOOL

# Константы
SW_HIDE = 0
SW_SHOW = 5
SW_SHOWNA = 8
GWLP_HWNDPARENT = -8
PROCESS_ALL_ACCESS = (0x000F0000 | 0x00100000 | 0xFFF)
MEM_COMMIT = 0x1000
MEM_RESERVE = 0x2000
PAGE_READWRITE = 0x04
MEM_RELEASE = 0x8000

GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000

WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

DLL_PATH = os.path.abspath("payload.dll")

def get_pids_by_name(process_names):
    pids = []
    for name in process_names:
        try:
            output = subprocess.check_output(
                ['tasklist', '/FI', f'IMAGENAME eq {name}', '/NH', '/FO', 'CSV'], 
                creationflags=subprocess.CREATE_NO_WINDOW
            ).decode('cp866', errors='ignore')
            for line in output.strip().split('\n'):
                parts = line.split('","')
                if len(parts) > 1:
                    pid_str = parts[1].replace('"', '')
                    if pid_str.isdigit():
                        pids.append(int(pid_str))
        except subprocess.CalledProcessError:
            pass
    return pids

def get_hwnds_for_pids(pids):
    hwnds = []
    def enum_windows_proc(hwnd, lParam):
        if user32.IsWindowVisible(hwnd):
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value in pids:
                hwnds.append(hwnd)
        return True

    user32.EnumWindows(WNDENUMPROC(enum_windows_proc), 0)
    return hwnds

def toggle_taskbar(hwnd):
    """Скрывает/показывает иконку в панели задач классическим стилем (работает идеально без консоли)."""
    ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    
    if ex_style & WS_EX_TOOLWINDOW:
        ex_style &= ~WS_EX_TOOLWINDOW
        ex_style |= WS_EX_APPWINDOW
    else:
        ex_style &= ~WS_EX_APPWINDOW
        ex_style |= WS_EX_TOOLWINDOW
        
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style)

def inject_dll(pid, dll_path):
    """Внедряет DLL в процесс для сокрытия от видеозахвата."""
    if not os.path.exists(dll_path):
        print(f"Ошибка: DLL не найдена: {dll_path}")
        return False
        
    dll_path_bytes = dll_path.encode('utf-16le') + b'\x00\x00'
    
    h_process = kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
    if not h_process:
        print(f"Не удалось открыть процесс {pid}. Запустите скрипт от Администратора!")
        return False
        
    arg_addr = kernel32.VirtualAllocEx(h_process, 0, len(dll_path_bytes), MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE)
    
    written = ctypes.c_size_t(0)
    kernel32.WriteProcessMemory(h_process, arg_addr, dll_path_bytes, len(dll_path_bytes), ctypes.byref(written))
    
    h_kernel32 = kernel32.GetModuleHandleW("kernel32.dll")
    load_lib_addr = kernel32.GetProcAddress(h_kernel32, b"LoadLibraryW")
    
    thread_id = wintypes.DWORD(0)
    h_thread = kernel32.CreateRemoteThread(h_process, None, 0, load_lib_addr, arg_addr, 0, ctypes.byref(thread_id))
    
    if not h_thread:
        kernel32.VirtualFreeEx(h_process, arg_addr, 0, MEM_RELEASE)
        kernel32.CloseHandle(h_process)
        return False

    kernel32.WaitForSingleObject(h_thread, 0xFFFFFFFF)
    
    exit_code = wintypes.DWORD(0)
    kernel32.GetExitCodeThread(h_thread, ctypes.byref(exit_code))
    h_module = exit_code.value
    
    kernel32.VirtualFreeEx(h_process, arg_addr, 0, MEM_RELEASE)
    kernel32.CloseHandle(h_thread)
    
    # Сразу же выгружаем DLL из памяти чужого процесса (FreeLibrary).
    # Так как DLL свою работу (сокрытие) уже выполнила при загрузке.
    # Это позволяет нам безопасно загрузить ее заново при повторном нажатии!
    if h_module:
        free_lib_addr = kernel32.GetProcAddress(h_kernel32, b"FreeLibrary")
        h_thread_free = kernel32.CreateRemoteThread(h_process, None, 0, free_lib_addr, ctypes.c_void_p(h_module), 0, ctypes.byref(thread_id))
        if h_thread_free:
            kernel32.WaitForSingleObject(h_thread_free, 0xFFFFFFFF)
            kernel32.CloseHandle(h_thread_free)
        
    kernel32.CloseHandle(h_process)
    return True

TARGETS_FILE = os.path.abspath("targets.txt")
target_processes = []

def load_targets():
    global target_processes
    if os.path.exists(TARGETS_FILE):
        with open(TARGETS_FILE, 'r', encoding='utf-8') as f:
            target_processes = [line.strip() for line in f if line.strip()]
    else:
        target_processes = ['Discord.exe', 'Obsidian.exe']
        save_targets()

def save_targets():
    with open(TARGETS_FILE, 'w', encoding='utf-8') as f:
        for p in target_processes:
            f.write(p + '\n')

def console_loop():
    while True:
        try:
            cmd = input("").strip()
            if not cmd:
                continue
            parts = cmd.split(maxsplit=1)
            action = parts[0].lower()
            
            if action == "add" and len(parts) > 1:
                prog = parts[1]
                if not prog.lower().endswith(".exe"):
                    prog += ".exe"
                if prog not in target_processes:
                    target_processes.append(prog)
                    save_targets()
                    print(f"[+] Программа '{prog}' добавлена!")
                else:
                    print(f"[*] Программа '{prog}' уже в списке.")
            elif action == "remove" and len(parts) > 1:
                prog = parts[1]
                if not prog.lower().endswith(".exe"):
                    prog += ".exe"
                if prog in target_processes:
                    target_processes.remove(prog)
                    save_targets()
                    print(f"[-] Программа '{prog}' удалена!")
                else:
                    print(f"[!] Программа '{prog}' не найдена в списке.")
            elif action == "list":
                print("Текущий список программ:")
                for p in target_processes:
                    print(f" - {p}")
            elif action == "restore":
                print("Сброс стилей панели задач для всех окон из списка...")
                pids = get_pids_by_name(target_processes)
                hwnds = get_hwnds_for_pids(pids)
                
                for hwnd in hwnds:
                    ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                    if ex_style & WS_EX_TOOLWINDOW:
                        ex_style &= ~WS_EX_TOOLWINDOW
                        ex_style |= WS_EX_APPWINDOW
                        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style)
                print("Панель задач восстановлена! (Скрытие от видео сбрасывается перезапуском самой программы).")
            elif action == "exit" or action == "quit":
                print("Выход из панели управления. Фоновый процесс продолжает работу!")
                os._exit(0)
            elif action == "stop" or action == "kill":
                print("Остановка фонового процесса...")
                os.system('taskkill /F /IM pythonw.exe >nul 2>&1')
                print("Фоновый процесс остановлен! Горячие клавиши больше не работают.")
                print("Выход из панели управления...")
                os._exit(0)
            else:
                print("Команды: add <имя>, remove <имя>, list, restore, stop, exit")
        except (EOFError, KeyboardInterrupt):
            print("\nВыход...")
            os._exit(0)

def toggle_protection():
    try:
        # Загружаем свежий список при каждом нажатии!
        load_targets()
        global target_processes
        pids = get_pids_by_name(target_processes)
        
        if not pids:
            return

        hwnds = get_hwnds_for_pids(pids)
        
        for hwnd in hwnds:
            toggle_taskbar(hwnd)
            
        for pid in set(pids):
            inject_dll(pid, DLL_PATH)
            
    except Exception as e:
        with open("error.log", "a", encoding="utf-8") as f:
            f.write(f"Ошибка в toggle_protection: {e}\n")

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--daemon":
        # Фоновый режим (без консоли)
        keyboard.add_hotkey('ctrl+alt+h', toggle_protection)
        keyboard.wait()
    else:
        # Режим панели управления
        load_targets()
        print("="*60)
        print("NinjaHider: Панель управления")
        print("Основной фоновый процесс запущен невидимо!")
        print("Нажмите 'ctrl+alt+h' чтобы скрыть/вернуть программы.")
        print("\nУправление из консоли:")
        print("  add <имя>    - добавить программу (например: add notepad)")
        print("  remove <имя> - удалить программу (например: remove notepad)")
        print("  list         - показать список")
        print("  restore      - принудительно вернуть иконки в панель задач")
        print("  stop         - полностью ВЫКЛЮЧИТЬ фоновый скрипт и выйти")
        print("  exit         - закрыть панель управления (фоновый скрипт продолжит работу)")
        print("="*60)
        
        console_loop()

if __name__ == '__main__':
    main()
