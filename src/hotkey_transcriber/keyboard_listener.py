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

    # VK sets per modifier name
    _VK_SETS = {
        "alt":   {0x12, 0xA4, 0xA5},
        "ctrl":  {0x11, 0xA2, 0xA3},
        "shift": {0x10, 0xA0, 0xA1},
    }

    _FKEY_VK = {
        "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73,
        "f5": 0x74, "f6": 0x75, "f7": 0x76, "f8": 0x77,
        "f9": 0x78, "f10": 0x79, "f11": 0x7A, "f12": 0x7B,
    }

    def _build_modifier_sets(modifier: str):
        """Return list of VK sets, one per required modifier component."""
        parts = [p.strip().lower() for p in modifier.split("+")]
        return [_VK_SETS[p] for p in parts if p in _VK_SETS]

    def _key_to_vk(key: str) -> int:
        k = key.lower()
        if k in _FKEY_VK:
            return _FKEY_VK[k]
        return ord(k.upper())

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

    # argtypes/restype fuer CallNextHookEx setzen – ohne diese scheitert
    # ctypes an 64-bit lParam-Werten (OverflowError: int too long).
    _user32.CallNextHookEx.argtypes = [
        ctypes.wintypes.HHOOK, ctypes.c_int,
        ctypes.wintypes.WPARAM, ctypes.wintypes.LPARAM,
    ]
    _user32.CallNextHookEx.restype = ctypes.c_long

    class KeyBoardListener:
        """
        Win32 Low-Level Keyboard Hook fuer Push-to-Talk mit konfigurierbarer Tastenkombination.
        Unterdrueckt den Trigger-Key-Event auf OS-Ebene waehrend der Aufnahme
        (SetWindowsHookExW + return 1 statt CallNextHookEx).
        """

        def __init__(self, start_callback, stop_callback, modifier: str = "alt", key: str = "r"):
            self.start_callback = start_callback
            self.stop_callback = stop_callback
            self.recording = False
            self._modifier_sets = _build_modifier_sets(modifier)
            self._trigger_vk = _key_to_vk(key)
            # Track pressed state for every VK that belongs to any modifier set
            self._modifier_vks = set().union(*self._modifier_sets) if self._modifier_sets else set()
            self._held = set()  # currently held modifier VKs
            self._hook_id = None
            self._hook_func = None
            self._thread = None

        def _modifiers_held(self) -> bool:
            return all(
                vk_set & self._held
                for vk_set in self._modifier_sets
            )

        def _proc(self, nCode, wParam, lParam):
            try:
                if nCode >= 0:
                    kb = _KBDLLHOOKSTRUCT.from_address(lParam)
                    vk = kb.vkCode
                    is_down = wParam in (_WM_KEYDOWN, _WM_SYSKEYDOWN)
                    is_up = wParam in (_WM_KEYUP, _WM_SYSKEYUP)

                    if vk in self._modifier_vks:
                        if is_down:
                            self._held.add(vk)
                        elif is_up:
                            self._held.discard(vk)

                    if vk == self._trigger_vk:
                        if is_down and self._modifiers_held() and not self.recording:
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
                            return 1  # suppress
            except Exception:
                pass  # Safety: Crash darf NIE die Tastatur blockieren

            return _user32.CallNextHookEx(self._hook_id, nCode, wParam, lParam)

        def _run(self):
            # Message-Queue im Thread erzwingen, bevor der Hook installiert wird
            msg = ctypes.wintypes.MSG()
            _user32.PeekMessageW(
                ctypes.byref(msg), None, 0, 0, 0,  # PM_NOREMOVE
            )

            self._hook_func = _HOOKPROC(self._proc)

            # hMod=NULL fuer WH_KEYBOARD_LL — Low-Level-Hooks brauchen
            # kein DLL-Handle, und GetModuleHandleW schlaegt auf manchen
            # Python-Distributionen fehl (error 126).
            self._hook_id = _user32.SetWindowsHookExW(
                _WH_KEYBOARD_LL,
                self._hook_func,
                None,
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

        def __init__(self, start_callback, stop_callback, modifier: str = "alt", key: str = "r"):
            self.start_callback = start_callback
            self.stop_callback = stop_callback
            self.recording = False
            self._modifier_parts = [p.strip().lower() for p in modifier.split("+")]
            self._key = key.lower()
            self._held_modifiers = set()
            self._hook = None

        def _modifiers_held(self) -> bool:
            return all(m in self._held_modifiers for m in self._modifier_parts)

        def _on_event(self, event):
            name = event.name.lower() if event.name else ""
            # Track modifier state
            for mod in self._modifier_parts:
                if mod in name:
                    if event.event_type == keyboard.KEY_DOWN:
                        self._held_modifiers.add(mod)
                    else:
                        self._held_modifiers.discard(mod)
                    return

            if name != self._key:
                return

            if event.event_type == keyboard.KEY_DOWN:
                if self._modifiers_held() and not self.recording:
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
