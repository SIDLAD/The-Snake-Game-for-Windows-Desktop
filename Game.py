from functools import wraps
from collections import deque

def use_stack(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if hasattr(self, 'colMax'):
            self.colMax += 1
            result = func(self, *args, **kwargs)
            self.colMax -= 1
            return result
        else:
            return func(self, *args, **kwargs)
    return wrapper

def init_grid(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if not hasattr(self, '_initial_grid') or self._initial_grid is None:
            if hasattr(self, 'getRawGrid') and callable(getattr(self, 'getRawGrid')):
                self._initial_grid = self.getRawGrid()
                if hasattr(self, '_log') and callable(getattr(self, '_log')):
                    self._log("Initial grid captured.")
        return func(self, *args, **kwargs)
    return wrapper

def mark_initialized(flag_str):
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            result = func(self, *args, **kwargs)
            setattr(self, flag_str, True)
            return result
        return wrapper
    return decorator

def check_initialized(flag_str):
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            if not hasattr(self, flag_str) or not getattr(self, flag_str):
                raise Exception(f"Cannot call {func.__name__} before initialization.")
            return func(self, *args, **kwargs)
        return wrapper
    return decorator

from Session import Session, skip_debug
HEAD = "Recycle Bin"

class SnakeBody:
    
    # store body both as a deque for ordered operations and a set for O(1) membership checks
    @property
    def positions(self) -> deque:
        return self._positions

    @positions.setter
    def positions(self, value):
        # value can be None, an iterable of positions, or a deque
        self._positions = deque(value) if value is not None else deque()
        self._positions_set = set(self._positions)

    def contains(self, pos: tuple[int,int]) -> bool:
        return pos in getattr(self, "_positions_set", set())

    def _add_before_head(self, pos: tuple[int,int]):
        self.positions.appendleft(pos)
        self._positions_set.add(pos)

    def _remove_at_tail(self) -> tuple[int,int]:
        tail = self.positions.pop()
        self._positions_set.remove(tail)
        return tail
    
    def move_body(self, next: tuple[int,int], remove_at_tail: bool):
        self._add_before_head(next)
        if remove_at_tail:
            self._remove_at_tail()

    def clear(self):
        self.positions.clear()
        self._positions_set.clear()

    def to_list(self) -> list[tuple[int,int]]:
        return list(self.positions)

    def __iter__(self):
        return iter(self.positions)

    def __len__(self):
        return len(self.positions)
    
    def __init__(self, positions = None):
        self.positions = deque(positions) if positions is not None else deque()


class TheSnakeGame(Session):
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.colMax -= 1 # Stack space :)
    
    @use_stack
    def _move_to_free_stack_space(self, pos: tuple[int,int]) -> tuple[int,int]:
        free = self._free_stack_space.pop()
        self.moveAtoB(pos, free)
        return free
    
    @use_stack
    def _move_from_stack_space(self, pos: tuple[int,int], free: tuple[int,int]):
        self.moveAtoB(free, pos)
        self._free_stack_space.add(free)
    
    @check_initialized('_snake_initialized')
    def _move_snake(self, direction: str):
        
        r, c = self.current_position
        if direction == 'up':
            new_pos = (r-1, c)
        elif direction == 'down':
            new_pos = (r+1, c)
        elif direction == 'left':
            new_pos = (r, c-1)
        elif direction == 'right':
            new_pos = (r, c+1)
        if new_pos[0] < 0 or new_pos[0] >= self.rowMax or new_pos[1] < 0 or new_pos[1] >= self.colMax:
            self._log("Cannot move out of bounds")
            return  # Out of bounds
        if self._snake_body.contains(new_pos) and (not len(self._snake_body) or self._snake_body.positions[-1] != new_pos):
            self._log("Cannot move into itself")
            return  # Cannot move into itself
        if len(self._snake_body) and self._snake_body.positions[-1] == new_pos:
            self._log("Chasing your own tail, eh?")
            self._swapIcons(self.current_position, new_pos)
            self._snake_body.move_body(self.current_position, remove_at_tail=True)
        elif new_pos not in self._apples:
            self._log(f"Moving snake, no apple at {new_pos}")
            self.moveAtoB(self.current_position, new_pos)
            if len(self._snake_body) > 0:
                self.moveAtoB(self._snake_body.positions[-1], self.current_position)
                self._snake_body.move_body(self.current_position, remove_at_tail=True)
        else:
            self._log(f"Moving snake, apple found at {new_pos}")
            self._swapIcons(self.current_position, new_pos)
            self._snake_body.move_body(self.current_position, remove_at_tail=False)
            self._apples.remove(new_pos)
        
        self.current_position = new_pos
        # self._log(f"Snake head now at {self.current_position}, body at {self._snake_body.to_list()}")
    
    def __enter__(self):
        
        self._free_stack_space: set[tuple[int,int]] = set()
        
        for i in range(self.rowMax):
            self._free_stack_space.add((i, self.colMax))
        
        
        self.allowed_keys = {
            'w': lambda: self._move_snake('up'),
            'a': lambda: self._move_snake('left'),
            's': lambda: self._move_snake('down'),
            'd': lambda: self._move_snake('right'),
        }
        self._before_start()
        
        self._init_snake()
        
        self.listener.start()
        return self
    
    def _getAvailableMoves(self):
        pass
    
    @init_grid
    def _init_apples(self):
        self._apples = set[tuple[int,int]]()
        for r in range(self.rowMax):
            for c in range(self.colMax):
                icon = self.iconAtPos((r,c))
                if icon and icon != HEAD:
                    self._log(f"Apple found at {(r,c)}: {icon}")
                    self._apples.add((r,c))
        self._log(f"Apples found at: {self._apples}")

    @init_grid
    def _init_snake_head(self):
        for r in range(self.rowMax):
            for c in range(self.colMax):
                icon = self.iconAtPos((r,c))
                if icon == HEAD:
                    self.current_position = (r,c)
                    self._log(f"Snake head found at {self.current_position}")
                    return
        raise Exception("Snake head not found")
    
    @init_grid
    @mark_initialized('_snake_initialized')
    def _init_snake(self):
        self._init_snake_head()
        self._init_apples()
        self._snake_body = SnakeBody()
    
    def _swapIcons(self, pos1: tuple[int,int], pos2: tuple[int,int]):
        icon1 = self.iconAtPos(pos1)
        icon2 = self.iconAtPos(pos2)
        if not icon1 or not icon2:
            raise ValueError(f"Cannot swap since one of the positions is empty: {pos1}, {pos2}")
        
        free = self._move_to_free_stack_space(pos2)
        self.moveAtoB(pos1, pos2)
        self._move_from_stack_space(pos1, free)

    @skip_debug
    def getRawGrid(self) -> list[list[False | str]]:
        grid = []
        for r in range(self.rowMax):
            row = []
            for c in range(self.colMax):
                icon = self.iconAtPos((r,c))
                row.append(icon)
            grid.append(row)
            self._log(f"Row {r}: {row}")
        return grid