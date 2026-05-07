#include <windows.h>

// Функция для установки атрибута скрытия от захвата для окон текущего процесса
void ApplyStealthToProcessWindows() {
    HWND hwnd = NULL;
    // WDA_EXCLUDEFROMCAPTURE = 0x11 (для Windows 10 версии 2004 и выше)
    // Этот флаг делает окно невидимым для инструментов захвата экрана
    DWORD affinity = 0x00000011;
    
    // Перебираем все окна в системе
    while ((hwnd = FindWindowEx(NULL, hwnd, NULL, NULL)) != NULL) {
        DWORD pid;
        GetWindowThreadProcessId(hwnd, &pid);
        // Если окно принадлежит текущему процессу (в который внедрена DLL)
        if (pid == GetCurrentProcessId()) {
            // Применяем защиту
            SetWindowDisplayAffinity(hwnd, affinity);
        }
    }
}

BOOL APIENTRY DllMain(HMODULE hModule, DWORD ul_reason_for_call, LPVOID lpReserved) {
    switch (ul_reason_for_call) {
        case DLL_PROCESS_ATTACH:
            // Как только DLL загружается в процесс, применяем защиту ко всем его окнам
            ApplyStealthToProcessWindows();
            break;
        case DLL_PROCESS_DETACH:
            break;
    }
    return TRUE;
}
