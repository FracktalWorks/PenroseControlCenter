#!/usr/bin/env python3
"""
Test script for advanced debugging mode functionality
"""

import sys
import os

# Add the octoprint_PenroseControlCenter directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'octoprint_PenroseControlCenter'))

from utils.logger import get_logger, set_advanced_debug_mode, get_advanced_debug_mode

def test_debug_mode():
    """Test the advanced debugging mode functionality"""
    
    print("Testing Advanced Debug Mode functionality...")
    
    # Get a logger
    logger = get_logger("test_logger")
    
    # Test initial state
    print(f"Initial debug mode state: {get_advanced_debug_mode()}")
    
    # Test normal logging
    print("\n--- Testing Normal Mode ---")
    logger.info("This is an INFO message in normal mode")
    logger.debug("This is a DEBUG message in normal mode (should not appear in file)")
    
    # Enable debug mode
    print("\n--- Enabling Debug Mode ---")
    set_advanced_debug_mode(True)
    print(f"Debug mode state after enabling: {get_advanced_debug_mode()}")
    
    # Test debug logging
    print("\n--- Testing Debug Mode ---")
    logger.info("This is an INFO message in debug mode")
    logger.debug("This is a DEBUG message in debug mode (should appear in file)")
    
    # Disable debug mode
    print("\n--- Disabling Debug Mode ---")
    set_advanced_debug_mode(False)
    print(f"Debug mode state after disabling: {get_advanced_debug_mode()}")
    
    # Test normal logging again
    print("\n--- Testing Normal Mode Again ---")
    logger.info("This is an INFO message back in normal mode")
    logger.debug("This is a DEBUG message back in normal mode (should not appear in file)")
    
    print("\nTest completed! Check the log file for debug messages.")

if __name__ == "__main__":
    test_debug_mode()
