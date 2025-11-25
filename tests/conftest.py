# conftest.py
import os
import time
import logging
import pytest
from pathlib import Path
from typing import Optional

from pytest_embedded import Dut

# ---------- 1. 会话级日志目录 ----------
@pytest.fixture(scope="session", autouse=True)
def log_session_dir(request):
    root_dir = Path(request.config.rootdir)
    logs_root = root_dir / "logs"
    timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
    session_log_dir = logs_root / timestamp
    os.makedirs(session_log_dir, exist_ok=True)

    latest_link = logs_root / "latest"
    if latest_link.is_symlink() or latest_link.is_file():
        os.unlink(latest_link)
    try:
        os.symlink(session_log_dir.name, latest_link)
    except OSError:
        pass
    return session_log_dir

# ---------- 2. 串口原始数据记录器 ----------
class UartRecorder:
    """为单个 dut 实例持续记录串口原始数据"""
    def __init__(self, dut: Dut, file_path: Path):
        self.dut = dut
        self.file_path = file_path
        self._file = None
        self._original_read = None
        self.captured_data = bytearray() # Keep a buffer for failure reporting
        self.max_buffer_size = 1024 * 10 # Keep last 10KB

    def start(self):
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self._file = open(self.file_path, "wb")
        
        # 拦截 read 方法以捕获数据流
        # 优先尝试 dut.serial.proc (pyserial 对象)，其次是 dut.serial
        target_obj = None
        if hasattr(self.dut, "serial"):
            if hasattr(self.dut.serial, "proc") and hasattr(self.dut.serial.proc, "read"):
                target_obj = self.dut.serial.proc
            elif hasattr(self.dut.serial, "read"):
                target_obj = self.dut.serial
        
        if target_obj:
            self._original_read = target_obj.read
            target_obj.read = self._intercept_read
            self._target_obj = target_obj # Keep reference to restore later
        else:
            logging.warning("DUT serial attribute not found or has no read method")

    def stop(self):
        # 恢复原始 read 方法
        if self._original_read and hasattr(self, "_target_obj"):
            self._target_obj.read = self._original_read
        
        if self._file:
            self._file.close()

    def _intercept_read(self, size=1):
        # 调用原始 read
        data = self._original_read(size)
        # 如果读到数据，写入文件
        if data:
            self._file.write(data)
            self._file.flush()
            
            # Update memory buffer
            self.captured_data.extend(data)
            if len(self.captured_data) > self.max_buffer_size:
                self.captured_data = self.captured_data[-self.max_buffer_size:]
        return data

    def get_recent_logs(self) -> str:
        """Decode recent logs for reporting, ignoring errors"""
        return self.captured_data.decode("utf-8", errors="replace")

# ---------- 3. 为每个测试函数自动挂载 recorder ----------
@pytest.fixture(scope="function", autouse=True)
def uart_raw_logger(request, log_session_dir):
    """自动给每个用例创建 .uart.bin 原始串口日志"""
    # 计算安全文件名
    nodeid = request.node.nodeid
    safe_name = nodeid.replace("/", "_").replace("::", "_").replace(".py", "")
    bin_path = log_session_dir / f"{safe_name}.uart.bin"

    # 延迟到 dut 实例真正创建后再启动 recorder
    recorder = None

    def start_recording(dut: Dut):
        nonlocal recorder
        recorder = UartRecorder(dut, bin_path)
        recorder.start()
        # Store recorder on node for the failure hook to access
        request.node._uart_recorder = recorder
        return recorder

    # 挂载到 request.node，方便后面取用（可选）
    request.node._start_uart_recording = start_recording

    yield

    # 测试结束，停止 recorder
    if recorder:
        recorder.stop()

# ---------- 4. 自动把 recorder 绑定到每个 dut fixture ----------
@pytest.fixture(scope="function", autouse=True)
def _attach_recorder(request, dut, uart_raw_logger):
    """dut 创建完成后立即启动串口记录"""
    if hasattr(request.node, "_start_uart_recording"):
        request.node._start_uart_recording(dut)

# ---------- 5. 失败时自动附加日志 (Hook) ----------
@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    # Execute all other hooks to obtain the report object
    outcome = yield
    rep = outcome.get_result()

    # We only care about failures during call or setup
    if rep.when in ("call", "setup") and rep.failed:
        recorder = getattr(item, "_uart_recorder", None)
        if recorder:
            recent_logs = recorder.get_recent_logs()
            if recent_logs:
                # Attach logs to the report sections
                # pytest-embedded might already do some logging, but this ensures we have our raw capture
                rep.sections.append(("Captured Serial Log (Last 10KB)", recent_logs))