def test_connection_and_log(dut):
    """连接设备并确认能收到日志，同时验证日志文件是否生成"""
    print("\n连接成功，准备等待任意日志...")
    # 等待任意一个换行符，相当于读取一行日志
    dut.write("pytest is ready\r\n")
    dut.expect(r"ok\r\n", timeout=30) 
    print("成功读取到日志。请检查 logs/ 目录下是否生成了对应的日志文件。")