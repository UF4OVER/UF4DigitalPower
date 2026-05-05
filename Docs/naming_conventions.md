# F4CP PyQt Naming Conventions

This project follows PyQt-style naming for application code.

## General Rules

- Classes use `PascalCase`: `PowerPage`, `MetricCard`, `DaplinkFlashPage`.
- Functions, methods, slots, and callbacks use `lowerCamelCase`: `refreshPorts()`, `onSend()`, `_applyTexts()`.
- Instance attributes use `lowerCamelCase`: `titleLabel`, `powerInterface`, `_rxTimer`.
- Qt signals use `lowerCamelCase` with an action-oriented name: `readStatusRequested`, `deviceConnected`.
- Constants and enum-like module values use `UPPER_SNAKE_CASE`: `SESSION_PAGE_BAUD_RATES`, `LANGUAGE_ZH_CN`.
- Files and modules keep Python module naming, `snake_case.py`, because Python imports conventionally use this style.

## Visibility

- Public UI methods use `lowerCamelCase`: `scanProbe()`, `startDownload()`.
- Private helpers keep a leading underscore and use lowerCamelCase after it: `_initConnectionCard()`, `_refreshThemeBundle()`.
- Name-mangled private helpers may use double underscores with lowerCamelCase: `__initWidget()`, `__onFontChanged()`.

## Qt Compatibility

Do not rename Qt override methods. Their names must match Qt/PyQt exactly:

- `event()`
- `closeEvent()`
- `showEvent()`
- `resizeEvent()`
- `paintEvent()`
- `mousePressEvent()`

Do not rename Qt or third-party API methods and attributes, for example:

- `setObjectName()`
- `setStyleSheet()`
- `currentIndexChanged`
- `exec_()`
- `raise_()`

## Data And Protocol Boundaries

Keep external protocol, dataclass payload, JSON, INI, and generated field names stable when they are part of a serialized or cross-module contract. Examples:

- Serial protocol field names and TLV identifiers.
- `Resources/Config/config.ini` keys.
- JSON translation keys in `Resources/Language/*.json`.
- pyOCD, CMSIS-Pack, and Qt API attribute names.

When an internal UI variable mirrors one of those external fields, prefer a local lowerCamelCase variable while leaving serialized keys unchanged.

## Examples

```python
class DevicePage(QWidget):
    rxEventSignal = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rxTimer = QTimer(self)
        self.refreshButton.clicked.connect(self.refreshPorts)

    def refreshPorts(self):
        ...

    def _appendLog(self, text: str):
        ...
```

