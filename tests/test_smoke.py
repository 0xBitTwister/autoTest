import pytest
import time

# ==========================================
# 配置区域：请根据你的实际设备进行修改
# ==========================================

# 1. [被动接收测试] 设备启动或运行时必然会打印的一个关键词/正则
# 如果你的设备很安静，可以设置为空字符串 ""，但这可能导致测试不严谨
KNOWN_BOOT_LOG = r"I \(\d+\) boot: Project name:" 
# 或者简单点，等待任意一个换行符，代表收到了数据：
# KNOWN_BOOT_LOG = r"\n"

# 2. [主动交互测试] 一个肯定会有响应的简单命令，例如 "help", "version", 或者一个回车 ""
TEST_COMMAND = "help"

# 3. [主动交互测试] 发送上述命令后，期待设备返回的关键响应内容（部分匹配即可）
# 例如发送 "help" 后，期待看到 "Available commands"
TEST_COMMAND_RESPONSE = "Available commands"

# ==========================================
# 测试用例实现
# ==========================================

@pytest.mark.smoke
def test_serial_connection_basic(dut):
    """
    冒烟测试 1: 基础连接检查
    验证 pytest-embedded 是否成功打开了串口对象。
    """
    # dut (Device Under Test) 是 pytest-embedded 提供的核心 fixture。
    # 当测试函数请求 'dut' 参数时，框架会自动尝试连接串口。
    # 如果连接失败（例如串口被占用、不存在），测试会在进入函数体之前就报错。
    
    print(f"\n[对勾] Verifying serial port object for port: {dut.serial.port}")
    
    # 检查 pyserial 对象的状态
    assert dut.serial is not None, "Serial object is None!"
    assert dut.serial.is_open, f"Serial port {dut.serial.port} is not open!"
    
    print(f"[Pass] Successfully connected to {dut.serial.port} at {dut.serial.baudrate} baud.")


@pytest.mark.smoke
def test_passive_log_reception(dut):
    """
    冒烟测试 2: 被动日志接收测试
    连接设备后，等待设备主动吐出一些已知日志。验证接收通路是否正常。
    """
    print(f"\n[Action] Waiting for known log pattern: '{KNOWN_BOOT_LOG}'...")
    
    # 如果设备已经启动很久了，可能不会再打印启动日志。
    # 这里的策略是：先尝试复位设备（如果支持），或者提示用户手动复位。
    # 如果你的设备不支持软件复位，请注释掉下面这行，并手动复位设备。
    try:
        # 尝试发送常用的软件复位命令，不同的设备命令不同，如 "reboot", "reset"
        dut.write("reboot") 
        print("[Info] Sent potential reboot command. If device doesn't reboot, please reset manually.")
    except Exception:
        pass # 忽略发送失败，也许设备不支持

    try:
        # expect() 是最核心的方法。它会阻塞等待串口数据匹配指定的正则或字符串。
        # timeout 设置为 20 秒，给予设备足够的启动时间。
        matched_data = dut.expect(KNOWN_BOOT_LOG, timeout=20)
        
        print(f"[Pass] Successfully matched log. Captured data snippet:\n---BEGIN---\n{matched_data.decode('utf-8').strip()}\n---END---")
        
    except Exception as e:
        pytest.fail(f"Timed out waiting for log pattern '{KNOWN_BOOT_LOG}'. \n"
                    f"Possible reasons: \n"
                    f"1. Device baudrate incorrect.\n"
                    f"2. Device didn't boot or output log.\n"
                    f"3. The KNOWN_BOOT_LOG pattern is wrong.\n"
                    f"Error details: {e}")


@pytest.mark.smoke
def test_active_command_interaction(dut):
    """
    冒烟测试 3: 主动命令交互测试 (发送 -> 接收)
    发送一个命令，验证设备是否有预期的响应。验证发送和接收双向通路。
    """
    # 先清空之前的缓冲区，避免旧日志干扰
    dut.serial.reset_input_buffer()
    
    print(f"\n[Action] Sending command: '{TEST_COMMAND}'")
    # 发送命令 (pytest-embedded 会自动添加换行符，取决于配置，默认是 \n)
    dut.write(TEST_COMMAND)
    
    print(f"[Action] Waiting for response pattern: '{TEST_COMMAND_RESPONSE}'...")
    
    try:
        # 等待预期的响应
        dut.expect(TEST_COMMAND_RESPONSE, timeout=5)
        print(f"[Pass] Received expected response for command '{TEST_COMMAND}'.")
        
    except Exception as e:
        # 如果失败，打印一下当前缓冲区里到底收到了什么，方便调试
        # 注意：读取缓冲区可能会读走数据，影响后续测试，但在失败场景下是可以的。
        current_buffer = dut.serial.read(dut.serial.in_waiting or 100).decode('utf-8', errors='ignore')
        
        pytest.fail(f"Failed to get expected response '{TEST_COMMAND_RESPONSE}' for command '{TEST_COMMAND}'.\n"
                    f"Timeout or mismatch.\n"
                    f"Data currently in buffer (if any):\n---\n{current_buffer}\n---\n"
                    f"Error details: {e}")