import sys
import threading


if sys.platform == 'win32':
    import ctypes
    import ctypes.wintypes

    _WH_KEYBOARD_LL = 13
    _WM_KEYDOWN = 0x0100
    _WM_KEYUP = 0x0101
    _WM_SYSKEYDOWN = 0x0104
    _WM_SYSKEYUP = 0x0105
    _WM_QUIT = 0x0012
    _VK_MENU = 0x12
    _VK_LMENU = 0xA4
    _VK_RMENU = 0xA5
    _VK_R = 0x52

    _HOOKPROC = ctypes.WINFUNCTYPE(
        ctypes.c_long, ctypes.c_int,
        ctypes.wintypes.WPARAM, ctypes.wintypes.LPARAM,
    )

    class _KBDLLHOOKSTRUCT(ctypes.Structure):
        _fields_ = [
            ('vkCode', ctypes.wintypes.DWORD),
            ('scanCode', ctypes.wintypes.DWORD),
            ('flags', ctypes.wintypes.DWORD),
            ('time', ctypes.wintypes.DWORD),
            ('dwExtraInfo', ctypes.POINTER(ctypes.c_ulong)),
        ]

    _user32 = ctypes.WinDLL('user32', use_last_error=True)
    _kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

    class KeyBoardListener:
        """
        Win32 Low-Level Keyboard Hook fuer Alt+R Push-to-Talk.
        Unterdrueckt 'r'-Events auf OS-Ebene waehrend der Aufnahme
        (SetWindowsHookExW + return 1 statt CallNextHookEx).
        """

        def __init__(self, start_callback, stop_callback):
            self.start_callback = start_callback
            self.stop_callback = stop_callback
            self.recording = False
            self._alt_held = False
            self._hook_id = None
            self._hook_func = None
            self._thread = None

        def _proc(self, nCode, wParam, lParam):
            if nCode >= 0:
                kb = _KBDLLHOOKSTRUCT.from_address(lParam)
                vk = kb.vkCode
                is_down = wParam in (_WM_KEYDOWN, _WM_SYSKEYDOWN)
                is_up = wParam in (_WM_KEYUP, _WM_SYSKEYUP)

                if vk in (_VK_MENU, _VK_LMENU, _VK_RMENU):
                    self._alt_held = is_down

                if vk == _VK_R:
                    if is_down and self._alt_held and not self.recording:
                        self.recording = True
                        threading.Thread(
                            target=self.start_callback, daemon=True
                        ).start()
                    if self.recording:
                        if is_up:
                            self.recording = False
                            threading.Thread(
                                target=self.stop_callback, daemon=True
                            ).start()
                        return 1  # suppress – nicht an naechsten Hook/App weiterleiten

            return _user32.CallNextHookEx(self._hook_id, nCode, wParam, lParam)

        def _run(self):
            # Message-Queue im Thread erzwingen, bevor der Hook installiert wird
            msg = ctypes.wintypes.MSG()
            _user32.PeekMessageW(
                ctypes.byref(msg), None, 0, 0, 0,  # PM_NOREMOVE
            )

            self._hook_func = _HOOKPROC(self._proc)
            self._hook_id = _user32.SetWindowsHookExW(
                _WH_KEYBOARD_LL,
                self._hook_func,
                _kernel32.GetModuleHandleW(None),
                0,
            )
            if not self._hook_id:
                err = ctypes.get_last_error()
                raise RuntimeError(
                    f"SetWindowsHookExW failed (error {err})"
                )

            while _user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                _user32.TranslateMessage(ctypes.byref(msg))
                _user32.DispatchMessageW(ctypes.byref(msg))

        def start(self):
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()

        def stop(self):
            if self._hook_id:
                _user32.UnhookWindowsHookEx(self._hook_id)
                self._hook_id = None
            if self._thread and self._thread.is_alive():
                tid = self._thread.ident
                if tid:
                    _user32.PostThreadMessageW(tid, _WM_QUIT, 0, 0)

else:
    import keyboard

    class KeyBoardListener:
        """Keyboard-Library Fallback fuer Nicht-Windows-Plattformen."""

        def __init__(self, start_callback, stop_callback):
            self.start_callback = start_callback
            self.stop_callback = stop_callback
            self.recording = False
            self._alt_held = False
            self._hook = None

        def _on_event(self, event):
            if 'alt' in event.name:
                self._alt_held = (event.event_type == keyboard.KEY_DOWN)
                return
            if event.name != 'r':
                return
            if event.event_type == keyboard.KEY_DOWN:
                if self._alt_held and not self.recording:
                    self.recording = True
                    threading.Thread(
                        target=self.start_callback, daemon=True
                    ).start()
                if self.recording:
                    return False
            elif event.event_type == keyboard.KEY_UP and self.recording:
                self.recording = False
                threading.Thread(
                    target=self.stop_callback, daemon=True
                ).start()
                return False

        def start(self):
            self._hook = keyboard.hook(self._on_event)

        def stop(self):
            if self._hook:
                keyboard.unhook(self._hook)
                self._hook = None
