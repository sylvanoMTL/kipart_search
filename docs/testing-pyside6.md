# PySide6 Testing Cheat Sheet

Proven patterns for testing PySide6/Qt6 code in this project. Every GUI test
must follow these rules to avoid segfaults, access violations, and flaky
failures on Windows.

---

## 1. QApplication Lifecycle

Qt requires exactly **one** `QApplication` for the process lifetime.
`pytest-qt` manages this automatically via `qtbot` — never create your own.

```python
# WRONG — will crash on second test module
app = QApplication(sys.argv)

# RIGHT — let pytest-qt handle it via the qtbot fixture
def test_widget(qtbot):
    w = MyWidget()
    qtbot.addWidget(w)
```

If a test file must guard against missing PySide6:
```python
PySide6 = pytest.importorskip("PySide6", reason="PySide6 required")
```

---

## 2. Widget Fixture Cleanup

Every widget created in a test must be closed and scheduled for deletion.
Use `qtbot.addWidget()` or a yield fixture:

```python
@pytest.fixture
def my_panel(qtbot):
    p = MyPanel()
    qtbot.addWidget(p)
    yield p
    p.close()
```

**Anti-pattern:** Creating widgets without cleanup causes access violations
when Qt tries to repaint destroyed C++ objects.

---

## 3. QThread closeEvent + wait()

Any window or dialog that creates QThread workers **must** wait for them
in `closeEvent`. Without this, the thread may outlive the widget and
access deleted memory.

```python
def closeEvent(self, event: QCloseEvent):
    """Wait for background workers before destroying the window."""
    if self._worker is not None and self._worker.isRunning():
        self._worker.wait(5000)  # 5-second timeout prevents hang
    super().closeEvent(event)
```

**Codebase examples:**
- `gui/update_dialog.py:211-215` — waits for `_DownloadWorker`
- `gui/main_window.py:555-567` — waits for `_connect_worker` and `_update_check_worker`

In tests, use `qtbot.waitSignal()` to wait for worker completion:
```python
with qtbot.waitSignal(worker.scan_complete, timeout=5000):
    worker.start()
```

---

## 4. QSettings Isolation

Tests must **never** write to the real Windows registry. The project
`conftest.py` has an autouse fixture `_isolate_qsettings` that redirects
QSettings to a temp directory. If you see QSettings in a test, verify the
fixture is active.

```python
# conftest.py provides this automatically — no action needed in test files.
# If writing a standalone test script, use:
from PySide6.QtCore import QSettings
QSettings.setDefaultFormat(QSettings.Format.IniFormat)
QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path))
```

---

## 5. Modal Dialog Testing

Never call `dialog.exec()` in a test — it blocks the event loop. Use
`dialog.show()` or `dialog.open()` and interact programmatically:

```python
def test_dialog(qtbot):
    dialog = MyDialog()
    qtbot.addWidget(dialog)
    dialog.show()

    # Interact with widgets directly
    dialog.some_button.click()
    assert dialog.result_label.text() == "expected"
```

For dialogs that must be modal, use `QTimer.singleShot` to schedule
interaction before calling `exec()`:
```python
from PySide6.QtCore import QTimer

def interact():
    dialog.accept()

QTimer.singleShot(100, interact)
dialog.exec()
```

---

## 6. eventFilter Testing

Use `installEventFilter` / `eventFilter` override — never monkey-patch
`mousePressEvent` or similar methods. Test by sending events:

```python
from PySide6.QtCore import QEvent, QPoint
from PySide6.QtGui import QMouseEvent

event = QMouseEvent(
    QEvent.Type.MouseButtonPress,
    QPoint(10, 10),
    Qt.MouseButton.LeftButton,
    Qt.MouseButton.LeftButton,
    Qt.KeyboardModifier.NoModifier,
)
widget.eventFilter(widget, event)
```

---

## 7. MainWindow.__new__() Pattern

Testing individual MainWindow methods without full `__init__()` (which
creates all panels, connects signals, accesses QSettings, etc.):

```python
from kipart_search.gui.main_window import MainWindow

window = MainWindow.__new__(MainWindow)
window._bridge = MagicMock(spec=KiCadBridge)
window.verify_panel = MagicMock()
# ... set only the attributes the method under test needs

window._on_component_clicked("C1")
window._bridge.select_component.assert_called_once_with("C1")
```

**When to use:** Testing specific methods that don't need the full UI.
**When NOT to use:** Testing layout, signal wiring, or visual behavior.

---

## 8. Anti-Patterns (Things That Always Fail)

| Anti-pattern | Symptom | Fix |
|---|---|---|
| Multiple `QApplication` instances | Crash / "already exists" | Use `qtbot` fixture |
| No `processEvents()` after signal | Signal handler not called | Use `qtbot.waitSignal()` |
| No widget cleanup in fixture | Access violation on teardown | `qtbot.addWidget()` + `close()` |
| Accessing QThread after `start()` without `wait()` | Race condition / segfault | `qtbot.waitSignal()` or `worker.wait()` |
| Calling `dialog.exec()` | Test hangs forever | Use `show()` + direct interaction |
| Writing to real QSettings | Pollutes registry, flaky tests | Use conftest `_isolate_qsettings` |
| Full `MainWindow()` construction in tests | Access violation (VerifyPanel init) | Use `MainWindow.__new__()` pattern |

---

## 9. Mock Robustness

Prefer **state-based verification** over call-counting:

```python
# FRAGILE — breaks if implementation adds a log call
mock.method.assert_called_once_with("arg")

# ROBUST — verifies the outcome, not the journey
assert component.mpn == "expected_value"
assert panel.table.rowCount() == 3
```

Use `assert_called_once_with` only when the call itself IS the behavior
(e.g., verifying `bridge.write_field` was called with correct args).
