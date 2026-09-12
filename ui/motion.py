"""Small, dependency-free motion helpers for CustomTkinter.

Tkinter is event-loop driven, so animation must schedule tiny updates with
``after`` instead of blocking the UI thread. These helpers intentionally use
short transitions and stop gracefully when their widget is destroyed.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class AnimationHandle:
    widget: object
    job: str | None = None
    cancelled: bool = False

    def cancel(self):
        self.cancelled = True
        if self.job and hasattr(self.widget, "after_cancel"):
            try:
                self.widget.after_cancel(self.job)
            except Exception:
                pass
            self.job = None


def _schedule(handle: AnimationHandle, callback: Callable, delay: int):
    if handle.cancelled:
        return None
    try:
        handle.job = handle.widget.after(delay, callback)
    except Exception:
        handle.cancelled = True
    return handle.job


def tween(widget, start: float, end: float, duration: int = 220, steps: int = 12, on_step: Callable[[float], None] | None = None, on_done: Callable[[], None] | None = None) -> AnimationHandle:
    """Interpolate between two numeric values without blocking the UI."""
    handle = AnimationHandle(widget)
    steps = max(1, steps)
    interval = max(1, duration // steps)
    current = 0

    def tick():
        nonlocal current
        if handle.cancelled:
            return
        current += 1
        ratio = min(current / steps, 1.0)
        eased = 1 - (1 - ratio) ** 3
        value = start + (end - start) * eased
        if on_step:
            on_step(value)
        if ratio >= 1:
            handle.job = None
            if on_done:
                on_done()
            return
        _schedule(handle, tick, interval)

    _schedule(handle, tick, interval)
    return handle


def stagger(widget, callbacks: list[Callable[[], None]], delay: int = 75) -> AnimationHandle:
    """Run callbacks in order, useful for cards appearing in a staggered row."""
    handle = AnimationHandle(widget)
    index = 0

    def run_next():
        nonlocal index
        if handle.cancelled or index >= len(callbacks):
            handle.job = None
            return
        try:
            callbacks[index]()
        finally:
            index += 1
        if index < len(callbacks):
            _schedule(handle, run_next, delay)
        else:
            handle.job = None

    _schedule(handle, run_next, 1)
    return handle


def reveal(widget, start_height: int, end_height: int, duration: int = 240, on_done: Callable[[], None] | None = None) -> AnimationHandle:
    """Animate a frame height where the geometry manager permits it."""
    def update(value: float):
        try:
            widget.configure(height=max(1, int(value)))
        except Exception:
            pass

    return tween(widget, start_height, end_height, duration=duration, on_step=update, on_done=on_done)


def pulse(widget, color_a: str, color_b: str, cycles: int = 2, duration: int = 700) -> AnimationHandle:
    """Pulse a widget border or foreground color when supported."""
    handle = AnimationHandle(widget)
    total = max(1, cycles * 2)
    current = 0

    def tick():
        nonlocal current
        if handle.cancelled:
            return
        current += 1
        try:
            widget.configure(border_color=color_b if current % 2 else color_a)
        except Exception:
            try:
                widget.configure(fg_color=color_b if current % 2 else color_a)
            except Exception:
                handle.cancelled = True
                return
        if current < total:
            _schedule(handle, tick, max(1, duration // total))
        else:
            handle.job = None

    _schedule(handle, tick, 1)
    return handle


class MotionGroup:
    """Owns multiple animations so a destroyed view can cancel them together."""

    def __init__(self):
        self.handles: list[AnimationHandle] = []

    def add(self, handle: AnimationHandle) -> AnimationHandle:
        self.handles.append(handle)
        return handle

    def cancel_all(self):
        for handle in self.handles:
            handle.cancel()
        self.handles.clear()

    def remove_finished(self):
        self.handles = [handle for handle in self.handles if not handle.cancelled and handle.job]

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.cancel_all()


class HoverMotion:
    """Attach a restrained hover color transition to a CustomTkinter widget."""

    def __init__(self, widget, normal: str, hover: str, duration: int = 120):
        self.widget = widget
        self.normal = normal
        self.hover = hover
        self.duration = duration
        self.handle: AnimationHandle | None = None
        widget.bind("<Enter>", self.enter, add="+")
        widget.bind("<Leave>", self.leave, add="+")

    def enter(self, _event=None):
        self._set(self.hover)

    def leave(self, _event=None):
        self._set(self.normal)

    def _set(self, color: str):
        if self.handle:
            self.handle.cancel()
        try:
            self.widget.configure(fg_color=color)
        except Exception:
            pass


class PressMotion:
    """Provide a small pressed-state response without changing layout."""

    def __init__(self, widget, pressed: str):
        self.widget = widget
        self.pressed = pressed
        self.original = None
        widget.bind("<ButtonPress-1>", self.press, add="+")
        widget.bind("<ButtonRelease-1>", self.release, add="+")

    def press(self, _event=None):
        try:
            self.original = self.widget.cget("fg_color")
            self.widget.configure(fg_color=self.pressed)
        except Exception:
            pass

    def release(self, _event=None):
        if self.original:
            try:
                self.widget.configure(fg_color=self.original)
            except Exception:
                pass


class Countdown:
    """Reusable countdown label for transient security states."""

    def __init__(self, widget, seconds: int, on_tick: Callable[[int], None], on_done: Callable[[], None] | None = None):
        self.widget = widget
        self.remaining = max(0, seconds)
        self.on_tick = on_tick
        self.on_done = on_done
        self.job = None

    def start(self):
        self.stop()
        self._tick()

    def _tick(self):
        self.on_tick(self.remaining)
        if self.remaining <= 0:
            if self.on_done:
                self.on_done()
            return
        self.remaining -= 1
        self.job = self.widget.after(1000, self._tick)

    def stop(self):
        if self.job:
            try:
                self.widget.after_cancel(self.job)
            except Exception:
                pass
            self.job = None


class Debouncer:
    """Delay a callback until input has been quiet for the given interval."""

    def __init__(self, widget, callback: Callable, delay: int = 180):
        self.widget = widget
        self.callback = callback
        self.delay = delay
        self.job = None

    def call(self, *args, **kwargs):
        if self.job:
            try:
                self.widget.after_cancel(self.job)
            except Exception:
                pass
        self.job = self.widget.after(self.delay, lambda: self.callback(*args, **kwargs))
