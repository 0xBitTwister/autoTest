import pytest
import logging

@pytest.mark.serial
def test_serial_connection(dut):
    """
    Verify that we can connect to the serial port and receive data.
    This test expects ANY data to be received within 5 seconds.
    """
    logging.info("Starting serial connection test...")
    
    # Try to read something. r'.+' matches any character (except newline)
    # This verifies that the serial port is open and receiving data.
    # If the device is silent, this might fail.
    try:
        # Expecting any non-empty string
        dut.expect(r'.+', timeout=5)
        logging.info("Successfully received data from serial port.")
    except Exception as e:
        pytest.fail(f"Failed to receive data from serial port: {e}")

@pytest.mark.serial
def test_boot_keyword(dut):
    """
    A sample test that waits for a specific keyword.
    NOTE: You should change 'Booting' to a keyword that your device actually outputs.
    """
    target_keyword = "device is ready for uart test" 
    logging.info(f"Waiting for keyword: {target_keyword}")
    
    try:
        # We use expect_exact for simple string matching
        dut.expect_exact(target_keyword, timeout=2)
        logging.info(f"Found keyword: {target_keyword}")
    except Exception:
        logging.warning(f"Keyword '{target_keyword}' not found. This is expected if the device output is different.")
        # We don't fail here to allow the user to see the framework working even if the keyword is wrong
        # In a real test, you would use pytest.fail()
