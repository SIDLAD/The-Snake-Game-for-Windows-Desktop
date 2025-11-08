EMPTY = "Desktop"

def stopExec(instance, *args):
    if instance and hasattr(instance, '_has_stopped') and not instance._has_stopped:
        if hasattr(instance, '_stop'):
            instance._stop()
        instance._has_stopped = True
    if hasattr(instance, '_log') and callable(getattr(instance, '_log')):
        instance._log(*args)
    instance._debug = False

def performCheck(instance):
    return not instance or not hasattr(instance, '_has_stopped') or not instance._has_stopped
        
from functools import wraps
import threading
import pyautogui
from pywinauto import Desktop
    

def with_check(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if not performCheck(self):
            return
        try:
            return func(self, *args, **kwargs)
        except Exception as e:
            self._log(f"Error occurred in {func.__name__}: {e}, terminating session.")
            stopExec(self, "Terminating session due to error")
            return
    return wrapper
    
def auto_check(cls):
    """Class decorator that adds performCheck to all non-private methods"""
    for attr_name in dir(cls):
        if not attr_name.startswith('_'):  # Non-private
            attr = getattr(cls, attr_name)
            if callable(attr):
                setattr(cls, attr_name, with_check(attr))
    return cls

def set_pause(pause):
    def _set_pause(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            pyautogui.PAUSE = pause
            return func(self, *args, **kwargs)
        return wrapper
    return _set_pause

def skip_debug(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        original_debug = self._debug
        self._debug = False
        result = func(self, *args, **kwargs)
        self._debug = original_debug
        return result
    return wrapper

@auto_check
class Session:

    allowed_keys: dict[str, function] = {}
    def _desktop(self):
        import keyboard
        while keyboard.is_pressed('ctrl') or keyboard.is_pressed('shift'):
            pass
        pyautogui.hotkey('win','d')

    def _code(self):
        pyautogui.hotkey('win', '3')
        
    def _stop(self):
        if self.listener:
            self.listener.stop()
        self._code()

    def __init__(self, **kwargs):
        self.listener = None
        self._has_stopped = False
        self._debug = kwargs.get('debug', False)
        self._action_lock = threading.Lock()
        
    def _before_start(self):
        self._has_stopped = False
        self._desktop()
        
        import pyautogui
        pyautogui.press('esc') # Unselect any selected icon
        
        from pynput import keyboard
        
        def on_press(key):
            self._log(f"Key pressed: {str(key)}")
            if str(key).strip("'") not in self.allowed_keys:
                self._log("Key not in allowed keys, stopping execution")
                stopExec(self, "Stopped by user")
            else:
                self._log("Key recognized, performing action")
                action = self.allowed_keys[str(key).strip("'")]
                with self._action_lock:
                    try:
                        action()
                    except Exception as e:
                        import traceback
                        
                        tb = traceback.format_exc()
                        self._log(f"Exception traceback: {tb}")
                        stopExec(self, e)

        self.listener = keyboard.Listener(
            on_press= on_press
        )
        
    def __enter__(self):
        self._before_start()
        self.listener.start()
        return self
        
    def __exit__(self, exc_type, exc_value, traceback):
        if not self._has_stopped:
            self._stop()
        
    topRCoords = (75, 60)
    rowMax = 8
    colMax = 19
    rowGap = 200
    colGap = 150
    
    def _log(self, *args):
        if self._debug:
            print(*args)
        
    def persistSession(self):
        while not self._has_stopped:
            pass
    
    def _transformToPos(self, xy):
        # xy is (row_index, col_index)
        # validate indices using the class attributes
        row_idx, col_idx = xy
        if not (0 <= row_idx < self.rowMax) or not (0 <= col_idx < self.colMax):
            raise Exception("Index out of range")
        # convert grid indices to screen coordinates based on topRCoords and gaps
        x = self.topRCoords[0] + self.colGap * col_idx
        y = self.topRCoords[1] + self.rowGap * row_idx
        return (x, y)
    
    # @set_pause(0.1)
    def moveAtoB(self, xy1: tuple[int,int], xy2: tuple[int,int]):
        # move the mouse from grid position xy1 to xy2 (both are (row, col))
        
        # Skip these checks for performance
        # at_xy1 = self.iconAtPos(xy1)
        # at_xy2 = self.iconAtPos(xy2)
        # if at_xy1 == False:
        #     raise ValueError(f"No clickable element at position {xy1}")
        # if at_xy2:
        #     raise ValueError(f"Position {xy2} is not empty, found {at_xy2}")

        pos1 = self._transformToPos(xy1)
        pos2 = self._transformToPos(xy2)
        
        pyautogui.moveTo(*pos1)
        pyautogui.mouseDown()
        pyautogui.moveTo(*pos2)
        pyautogui.mouseUp()
        
    @skip_debug
    def iconAtPos(self, xy: tuple[int, int]) -> False | str:
        """Check if grid position has clickable element"""
        try:
            pos = self._transformToPos(xy)
        
            desktop = Desktop(backend="uia")
            element = desktop.from_point(*pos)
            
            # Debug: print what we found
            self._log(f"Position: {pos}")
            self._log(f"Element found: {element.element_info.name}")
            self._log(f"Control type: {element.element_info.control_type}")
            self._log(f"Is enabled: {element.is_enabled()}")
            self._log(f"Is visible: {element.is_visible()}")

            if not element.is_enabled() or not element.is_visible() or not element.element_info.name != EMPTY:
                return False
            return element.element_info.name
        except Exception as e:
            # Debug: see what error occurred
            self._log(f"Error: {e}")
            return False