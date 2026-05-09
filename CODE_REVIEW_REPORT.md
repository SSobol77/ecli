<!--
Filename: CODE_REVIEW_REPORT.md
Project:  ECLI
License:  MIT
Author:   Siergej Sobolewski
Copyright: (c) 2026 Siergej Sobolewski
-->

# Code Review Report - ECLI Python Codebase
**Date**: May 9, 2026
**Scope**: Full codebase review
**Reviewer**: Senior Python Developer

---

## Summary
The ECLI codebase is a terminal-based text editor with comprehensive features including Git integration, LSP support, AI providers, and async task handling. Overall architecture is sound with good separation of concerns. However, several issues were identified ranging from minor bugs to potential runtime errors and resource management concerns.

**Total Issues Found**: 11
**Severity**: 3 Critical, 5 High, 3 Medium

---

## Issues

### 1. **[CRITICAL]** Typo in Class Name - DrawScreen.py (Line 37)

**Location**: `src/ecli/ui/DrawScreen.py:37`

**Issue**: Class name contains Cyrillic character 'с' instead of Latin 'c':
```python
class сlass DrawScreen:  # ← Wrong: Cyrillic 'с'
```

**Impact**: This will cause a syntax error or runtime failures when trying to reference the class. Python will interpret this as a different identifier.

**Recommended Change**:
```python
# Current (line ~37):
class сlass DrawScreen:

# Should be:
class DrawScreen:
```

---

### 2. **[CRITICAL]** Attribute Name Typo - History.py (Line 188)

**Location**: `src/ecli/core/History.py:188`

**Issue**: Reference to `self.text[row]` instead of `self.editor.text[row]`:
```python
logging.warning(
    f"Undo insert: Text mismatch for deletion at [{row},{col}] len {len_inserted}. Expected '{text_that_was_inserted}', found '{self.text[row][col:col + len_inserted]}'."
)
```

**Impact**: AttributeError will be raised at runtime because `History` class does not have a `text` attribute - it should access `self.editor.text`.

**Recommended Change**:
```python
# Current (line ~188):
found '{self.text[row][col:col + len_inserted]}'

# Should be:
found '{self.editor.text[row][col:col + len_inserted]}'
```

---

### 3. **[CRITICAL]** Resource Leak - LinterBridge.py (LSP Process)

**Location**: `src/ecli/integrations/LinterBridge.py`

**Issue**: The `lsp_proc` subprocess is created but never properly terminated or cleaned up. No destructor or cleanup method is provided, and `preexec_fn=os.setsid` creates a process group but there's no corresponding `os.killpg()` call on shutdown.

**Impact**:
- Ruff LSP processes accumulate in memory over time
- When the editor exits, zombie processes remain
- On Windows (where `preexec_fn` is None), the process might not be properly terminated

**Recommended Change**:
Add a cleanup method to LinterBridge class:
```python
# Add this method to LinterBridge class (after line ~50):
def cleanup(self) -> None:
    """Clean up LSP process and threads."""
    if self.lsp_reader and self.lsp_reader.is_alive():
        try:
            self.lsp_reader.join(timeout=2)
        except Exception:
            pass

    if self.lsp_proc and self.lsp_proc.poll() is None:
        try:
            if sys.platform != "win32":
                import signal
                os.killpg(os.getpgid(self.lsp_proc.pid), signal.SIGTERM)
            else:
                self.lsp_proc.terminate()
            self.lsp_proc.wait(timeout=3)
        except Exception as e:
            logging.warning(f"Failed to cleanly terminate LSP: {e}")
            try:
                self.lsp_proc.kill()
            except Exception:
                pass

# Call this from Ecli.exit_editor() or a cleanup routine
```

---

### 4. **[HIGH]** Unnecessary Await Statement - AI.py (Line 48)

**Location**: `src/ecli/integrations/AI.py:48`

**Issue**: The `_get_session()` method includes a pointless `await asyncio.sleep(0)`:
```python
async def _get_session(self) -> aiohttp.ClientSession:
    if self.session is None or self.session.closed:
        logger.debug("Creating new aiohttp.ClientSession")
        self.session = aiohttp.ClientSession()
    # Small await to ensure this coroutine uses asynchronous features
    await asyncio.sleep(0)  # ← Unnecessary
    return self.session
```

**Impact**:
- Performance: Adds unnecessary context switch even when session already exists
- Confusing: The comment suggests it's a workaround for static analysis, not a genuine requirement
- Misleading: Reviewers may assume there's a real async operation happening

**Recommended Change**:
```python
# Current (lines ~45-50):
async def _get_session(self) -> aiohttp.ClientSession:
    if self.session is None or self.session.closed:
        logger.debug("Creating new aiohttp.ClientSession")
        self.session = aiohttp.ClientSession()
    await asyncio.sleep(0)  # Remove this line
    return self.session

# Should be:
async def _get_session(self) -> aiohttp.ClientSession:
    if self.session is None or self.session.closed:
        logger.debug("Creating new aiohttp.ClientSession")
        self.session = aiohttp.ClientSession()
    return self.session
```

---

### 5. **[HIGH]** Missing Timeout Parameter Validation - utils.py (Line ~290)

**Location**: `src/ecli/utils/utils.py:290`

**Issue**: The `safe_run()` function accepts `**kwargs` that can include `timeout`, but doesn't handle the case where timeout is `None` or invalid:
```python
def safe_run(cmd: List[str], **kwargs: Any) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            cmd, capture_output=True, text=True, check=False,
            encoding="utf-8", errors="replace", **kwargs,
        )
    except subprocess.TimeoutExpired as e:
        logger.warning(f"Command timed out: {' '.join(cmd)}")
        return subprocess.CompletedProcess(cmd, -9, stdout=e.stdout or "", stderr=e.stderr or "")
```

**Impact**:
- If `kwargs` contains `timeout=None`, it won't set a timeout (intentional but undocumented)
- Large timeout values or invalid types are passed directly to `subprocess.run()` without validation
- The `-9` return code (SIGKILL) is used, but SIGTERM (-15) would be more appropriate

**Recommended Change**:
```python
# Current (lines ~285-295):
def safe_run(cmd: List[str], **kwargs: Any) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            cmd, capture_output=True, text=True, check=False,
            encoding="utf-8", errors="replace", **kwargs,
        )
    except subprocess.TimeoutExpired as e:
        logger.warning(f"Command timed out: {' '.join(cmd)}")
        return subprocess.CompletedProcess(cmd, -9, stdout=e.stdout or "", stderr=e.stderr or "")

# Should be:
def safe_run(cmd: List[str], **kwargs: Any) -> subprocess.CompletedProcess:
    # Validate and normalize timeout
    timeout = kwargs.pop('timeout', None)
    if timeout is not None and not isinstance(timeout, (int, float)):
        logger.warning(f"Invalid timeout type {type(timeout).__name__}, ignoring")
        timeout = None
    if timeout is not None and timeout <= 0:
        logger.warning(f"Invalid timeout value {timeout}, using default 30s")
        timeout = 30

    try:
        return subprocess.run(
            cmd, capture_output=True, text=True, check=False,
            encoding="utf-8", errors="replace", timeout=timeout, **kwargs,
        )
    except subprocess.TimeoutExpired as e:
        logger.warning(f"Command timed out after {timeout}s: {' '.join(cmd)}")
        return subprocess.CompletedProcess(cmd, -15, stdout=e.stdout or "", stderr=e.stderr or "")
```

---

### 6. **[HIGH]** Type Annotation Inconsistency - utils.py

**Location**: `src/ecli/utils/utils.py` (multiple locations)

**Issue**: Mixed use of `Dict` (old style) and `dict` (modern style) type hints:
```python
# Line ~180:
DEFAULT_CONFIG: Dict[str, Any] = {

# Line ~245:
def get_file_icon(filename: Optional[str], config: Dict[str, Any]) -> str:

# Should use consistently:
DEFAULT_CONFIG: dict[str, Any] = {
def get_file_icon(filename: Optional[str], config: dict[str, Any]) -> str:
```

**Impact**:
- Inconsistent style reduces code readability
- Mixed imports: need both `Dict` from `typing` and built-in `dict`
- With Python 3.9+, `dict[...]` is preferred over `Dict[...]`

**Recommended Change**:
```python
# Find and replace all occurrences:
# OLD: Dict[str, Any], List[str], Optional[str]
# NEW: dict[str, Any], list[str], Optional[str]

# Current imports (line ~23-25):
from typing import Any, Dict, List, Optional

# Should be:
from typing import Any, Optional

# Then replace:
Dict[str, Any] → dict[str, Any]
List[str] → list[str]
```

---

### 7. **[HIGH]** Overly Broad Exception Handling - main.py (Line 31)

**Location**: `src/ecli/main.py:31-34`

**Issue**: Silently catching all exceptions during dotenv loading:
```python
try:
    user_config_dir = Path.home() / ".config" / "ecli"
    dotenv_path = user_config_dir / ".env"
    load_dotenv(dotenv_path=dotenv_path)
except Exception:  # ← Too broad
    pass
```

**Impact**:
- Actual errors (permission denied, corrupted .env, etc.) are silently swallowed
- Makes debugging difficult
- Mask potential security issues with config files

**Recommended Change**:
```python
# Current (lines ~31-34):
try:
    user_config_dir = Path.home() / ".config" / "ecli"
    dotenv_path = user_config_dir / ".env"
    load_dotenv(dotenv_path=dotenv_path)
except Exception:
    pass

# Should be:
try:
    user_config_dir = Path.home() / ".config" / "ecli"
    dotenv_path = user_config_dir / ".env"
    if dotenv_path.exists():
        load_dotenv(dotenv_path=dotenv_path)
except (RuntimeError, PermissionError, OSError) as e:
    # Only catch expected errors during config loading
    print(f"Warning: Could not load .env file: {e}", file=sys.stderr)
except Exception:
    # Still catch unexpected errors to prevent bootstrap failure
    print("Warning: Unexpected error loading .env, continuing with defaults", file=sys.stderr)
```

---

### 8. **[HIGH]** AsyncEngine Task Collection Race Condition - AsyncEngine.py (Line 157)

**Location**: `src/ecli/core/AsyncEngine.py:157`

**Issue**: Task collection uses a set without synchronization, which can cause race conditions:
```python
async def main_loop(self) -> None:
    while True:
        try:
            task_data = await self.loop.run_in_executor(None, self.from_ui_queue.get)
            if task_data is None:
                break
            task = self.loop.create_task(self.dispatch_task(task_data))
            self._tasks.add(task)  # ← Potential race condition
            task.add_done_callback(self._tasks.discard)  # ← And here
```

**Impact**:
- If multiple tasks complete simultaneously or during shutdown, the set could be modified during iteration in `_shutdown_tasks()`
- This can raise `RuntimeError: Set changed size during iteration`
- Especially likely during cleanup/shutdown scenarios

**Recommended Change**:
```python
# Current (lines ~140-175):
self._tasks: set[asyncio.Task[Any]] = set()

async def main_loop(self) -> None:
    while True:
        try:
            task_data = await self.loop.run_in_executor(None, self.from_ui_queue.get)
            if task_data is None:
                break
            task = self.loop.create_task(self.dispatch_task(task_data))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)

# Should use a lock:
import threading
self._tasks: set[asyncio.Task[Any]] = set()
self._tasks_lock = threading.Lock()

async def main_loop(self) -> None:
    while True:
        try:
            task_data = await self.loop.run_in_executor(None, self.from_ui_queue.get)
            if task_data is None:
                break
            task = self.loop.create_task(self.dispatch_task(task_data))
            with self._tasks_lock:
                self._tasks.add(task)
            task.add_done_callback(lambda t: self._remove_task(t))

def _remove_task(self, task: asyncio.Task[Any]) -> None:
    with self._tasks_lock:
        self._tasks.discard(task)

async def _shutdown_tasks(self) -> None:
    with self._tasks_lock:
        tasks_copy = list(self._tasks)
    for task in tasks_copy:
        if not task.done():
            task.cancel()
```

---

### 9. **[MEDIUM]** Hardcoded Log File Path - logging_config.py (Line 106)

**Location**: `src/ecli/utils/logging_config.py:106`

**Issue**: Log file path is hardcoded to current directory instead of using a proper log directory:
```python
log_filename = "editor.log"  # ← Hardcoded, relative to CWD
# ...
log_dir = os.path.dirname(log_filename)  # Will be empty string
if log_dir and not os.path.exists(log_dir):  # This condition is False!
    try:
        os.makedirs(log_dir)
```

**Impact**:
- Logs are created in whatever directory the editor was launched from
- Difficult to locate logs (user doesn't expect them in random directories)
- Log cleanup doesn't follow standard conventions

**Recommended Change**:
```python
# Current (lines ~105-112):
log_filename = "editor.log"
log_dir = os.path.dirname(log_filename)
if log_dir and not os.path.exists(log_dir):
    try:
        os.makedirs(log_dir)

# Should be:
import os
log_dir = os.path.join(os.path.expanduser("~"), ".config", "ecli", "logs")
log_filename = os.path.join(log_dir, "editor.log")

if not os.path.exists(log_dir):
    try:
        os.makedirs(log_dir, exist_ok=True)
```

---

### 10. **[MEDIUM]** Root Logger Configuration Issue - logging_config.py (Line 173)

**Location**: `src/ecli/utils/logging_config.py:173`

**Issue**: Setting root logger level might be too permissive:
```python
root_logger.setLevel(log_file_level)  # Line ~173
```

**Impact**:
- If `file_level` is DEBUG, the root logger will emit DEBUG for all libraries
- Can cause excessive logging from third-party libraries (requests, aiohttp, etc.)
- Better practice is to set root to a higher level and configure specific loggers

**Recommended Change**:
```python
# Current (lines ~170-173):
root_logger = logging.getLogger()
root_logger.handlers = []
if file_handler:
    root_logger.addHandler(file_handler)
if console_handler:
    root_logger.addHandler(console_handler)
if error_file_handler:
    root_logger.addHandler(error_file_handler)

root_logger.setLevel(log_file_level)

# Should be:
root_logger = logging.getLogger()
root_logger.handlers = []
if file_handler:
    root_logger.addHandler(file_handler)
if console_handler:
    root_logger.addHandler(console_handler)
if error_file_handler:
    root_logger.addHandler(error_file_handler)

# Set root logger to the most verbose file level, but cap third-party loggers
root_logger.setLevel(log_file_level)

# Suppress verbose loggers from dependencies
logging.getLogger("aiohttp").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.INFO)
```

---

### 11. **[MEDIUM]** Missing Input Validation - main.py (Line 68)

**Location**: `src/ecli/main.py:68-70`

**Issue**: No validation of the `candidate` path before attempting to resolve it:
```python
def _resolve_cli_path(argv: list[str]) -> Optional[Path]:
    if len(argv) <= 1:
        return None
    raw = argv[1].strip()
    if not raw:
        return None
    try:
        return Path(raw).expanduser()
    except Exception:
        return None
```

**Impact**:
- Path objects with extremely long names or invalid characters might not be caught
- Silent failure with None return makes debugging difficult
- User doesn't get feedback if they provided an invalid path

**Recommended Change**:
```python
# Current (lines ~68-78):
def _resolve_cli_path(argv: list[str]) -> Optional[Path]:
    if len(argv) <= 1:
        return None
    raw = argv[1].strip()
    if not raw:
        return None
    try:
        return Path(raw).expanduser()
    except Exception:
        return None

# Should be:
def _resolve_cli_path(argv: list[str]) -> Optional[Path]:
    if len(argv) <= 1:
        return None
    raw = argv[1].strip()
    if not raw:
        return None
    try:
        resolved = Path(raw).expanduser().resolve()
        # Validate path doesn't contain suspicious patterns
        path_str = str(resolved)
        if len(path_str) > 4096:  # Most filesystems limit paths to 4096
            logger.warning(f"Provided path is too long: {raw}")
            return None
        return resolved
    except (ValueError, RuntimeError) as e:
        logger.warning(f"Invalid path provided: {raw!r} - {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error resolving path {raw!r}: {e}")
        return None
```

---

## Summary Table

| Issue # | Severity | Module | Line(s) | Type | Status |
|---------|----------|--------|---------|------|--------|
| 1 | CRITICAL | DrawScreen.py | 37 | Typo (Cyrillic char) | Blocker |
| 2 | CRITICAL | History.py | 188 | Attribute error | Blocker |
| 3 | CRITICAL | LinterBridge.py | ~165 | Resource leak | Memory issue |
| 4 | HIGH | AI.py | 48 | Unnecessary await | Performance |
| 5 | HIGH | utils.py | 290 | Missing validation | Robustness |
| 6 | HIGH | utils.py | Multiple | Type consistency | Style |
| 7 | HIGH | main.py | 31 | Broad exception | Debugging |
| 8 | HIGH | AsyncEngine.py | 157 | Race condition | Stability |
| 9 | MEDIUM | logging_config.py | 106 | Hardcoded path | UX |
| 10 | MEDIUM | logging_config.py | 173 | Log config | Noise |
| 11 | MEDIUM | main.py | 68 | Input validation | UX |

---

## Recommendations

1. **Immediate Action Required** (Issues #1, #2, #3):
   - Fix the typo in DrawScreen.py class name
   - Fix the attribute reference in History.py
   - Implement LSP process cleanup in LinterBridge

2. **High Priority** (Issues #4-8):
   - Remove unnecessary await in AI.py
   - Add proper timeout validation in utils.py
   - Standardize type hints to modern Python style
   - Improve exception handling in bootstrap code
   - Add thread-safe task collection in AsyncEngine

3. **Medium Priority** (Issues #9-11):
   - Use proper log directory conventions
   - Fine-tune root logger configuration
   - Add input path validation

---

## Notes

- The codebase shows good architectural design with proper separation of concerns
- Documentation is comprehensive and well-written
- Most issues are localized and can be fixed independently
- No issues found with the overall async/await patterns (except unnecessary sleep)
- Security posture is reasonable but could benefit from stricter input validation
