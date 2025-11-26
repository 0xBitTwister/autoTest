import pytest
import logging
import re
import time
from pytest_embedded import Dut

def expect_unordered(dut: Dut, patterns: list[str], timeout: float = 10) -> bool:
    """
    Waits for ALL patterns to be matched in the serial output, in ANY order.
    
    Args:
        dut: The device under test.
        patterns: List of regex patterns to match.
        timeout: Total timeout in seconds.
        
    Returns:
        True if all patterns are matched.
        Raises Exception if timeout occurs.
    """
    remaining_patterns = patterns[:]
    start_time = time.time()
    
    logging.info(f"Waiting for {len(patterns)} events (unordered)...")
    
    while remaining_patterns:
        if time.time() - start_time > timeout:
            raise TimeoutError(f"Timeout waiting for patterns. Remaining: {remaining_patterns}")
        
        # We use expect with a short timeout to check for any of the remaining patterns
        # Note: expect_any usually returns the index of the matched pattern
        # But here we need to be careful because expect_any might consume the stream
        # and we want to match against multiple potential patterns.
        
        # Strategy: Use expect(regex_for_any_remaining)
        # Construct a combined regex: (pattern1)|(pattern2)|...
        combined_regex = "|".join(f"({p})" for p in remaining_patterns)
        
        try:
            # Wait for ANY of the remaining patterns
            # We use a small slice of the total timeout for each check, 
            # but actually we can just use the remaining time.
            current_timeout = timeout - (time.time() - start_time)
            if current_timeout <= 0:
                break
                
            match = dut.expect(combined_regex, timeout=current_timeout)
            
            # Identify which pattern was matched
            matched_text = match.group(0)
            if isinstance(matched_text, bytes):
                matched_text = matched_text.decode('utf-8', errors='ignore')
                
            logging.info(f"Matched: {matched_text.strip()}")
            
            # Remove the matched pattern from the list
            # We need to find which pattern matched. 
            # Since we used capturing groups in combined_regex, we can check match.groups()
            # match.groups() will look like (None, 'matched_str', None, ...)
            
            found_index = -1
            for i, group_match in enumerate(match.groups()):
                if group_match is not None:
                    found_index = i
                    break
            
            if found_index != -1:
                matched_pattern = remaining_patterns[found_index]
                logging.info(f"Confirmed pattern match: {matched_pattern}")
                remaining_patterns.pop(found_index)
            else:
                # Fallback if groups didn't work as expected (shouldn't happen with proper regex)
                # Re-check manually
                for p in remaining_patterns:
                    if re.search(p, matched_text):
                        remaining_patterns.remove(p)
                        break
                        
        except Exception as e:
            # If expect times out or fails, we propagate the error
            raise e

    logging.info("All patterns matched successfully.")
    return True

@pytest.mark.serial
def test_hfp_connection(dut):
    """
    Test HFP Service Level Connection (SLC) establishment.
    Verifies the sequence of AT commands exchanged during connection.
    """
    logging.info("Starting HFP Connection Test...")
    
    # 1. Wait for the initial BRSF command (usually the start of SLC)
    # This might be initiated by the HF (Hands-Free) unit (our device)
    logging.info("Waiting for AT+BRSF...")
    dut.expect(r"AT\+BRSF=\d+", timeout=10)
    
    # 2. Define the set of initialization commands that can arrive in any order
    # Based on the log file:
    # AT+BAC=1,2
    # AT+CIND=?
    # AT+CIND?
    # AT+CMER=3,0,0,1
    # AT+CHLD=?
    # AT+CLIP=1
    # AT+CCWA=1
    # AT+COPS=3,0
    # AT+CMEE=1
    # AT+CNUM
    # AT+XAPL=...
    # AT+VGS=...
    
    expected_commands = [
        r"AT\+BAC=[\d,]+",
        r"AT\+CIND=\?",
        r"AT\+CIND\?",
        r"AT\+CMER=[\d,]+",
        r"AT\+CHLD=\?",
        r"AT\+CLIP=\d",
        r"AT\+CCWA=\d",
        r"AT\+COPS=[\d,]+",
        r"AT\+CMEE=\d",
        r"AT\+CNUM",
        r"AT\+XAPL=[\w-]+,\d",
        # AT+VGS might appear multiple times or not, let's include it if it's critical, 
        # but based on logs it appears mixed in. Let's stick to the core SLC commands.
    ]
    
    # 3. Wait for all these commands to appear within a reasonable time (e.g., 5 seconds)
    try:
        expect_unordered(dut, expected_commands, timeout=10)
    except TimeoutError as e:
        pytest.fail(f"HFP SLC negotiation failed: {e}")
        
    # 4. Verify final state or specific event
    # In the log, we see +CIEV events indicating status changes
    # or just check that we reached a stable state.
    # Let's wait for a final OK or a specific indicator.
    logging.info("HFP SLC commands verified. Waiting for final stability...")
    
    # Optional: Wait for +BCS (Codec Selection) which usually happens after SLC if audio is set up
    # dut.expect(r"\+BCS", timeout=5) 
    
    logging.info("HFP Connection Test Passed.")
