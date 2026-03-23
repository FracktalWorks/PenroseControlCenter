"""
Printer UI Configuration Module

This module handles printer configuration (single vs dual nozzle) and manages
which UI elements should be shown/hidden based on the printer type.
Also handles Volterra ALF specific UI elements like heater ring, heated chamber,
and filament spool heater.
"""

import config
from utils.logger import get_logger
from PyQt5.QtWidgets import QWidget

logger = get_logger(__name__)

def is_dual_nozzle_printer():
    """Check if the printer is configured for dual nozzle operation."""
    # Access the current value dynamically to pick up changes from Klipper config loading
    return config.IS_DUAL_NOZZLE

def has_heater_ring():
    """Check if the printer has a heater ring (Volterra ALF specific)."""
    # Access the current value dynamically to pick up changes from Klipper config loading
    result = config.HAS_HEATER_RING
    logger.debug(f"has_heater_ring() returning: {result}")
    return result

def has_heated_chamber():
    """Check if the printer has a heated chamber/enclosure."""
    # Access the current value dynamically to pick up changes from Klipper config loading
    result = config.HAS_HEATED_CHAMBER
    logger.debug(f"has_heated_chamber() returning: {result}")
    return result

def has_spool_heater():
    """Check if the printer has a filament spool heater/dryer."""
    # Access the current value dynamically to pick up changes from Klipper config loading
    result = config.HAS_SPOOL_HEATER
    logger.debug(f"has_spool_heater() returning: {result}")
    return result

# UI elements that should be hidden for single nozzle printers
# Note: Only include QWidget-based elements (not layouts like QHBoxLayout/QVBoxLayout)
DUAL_NOZZLE_ELEMENTS = {
    'home_screen': [
        'tool1Label', 'tool1LoadedNozzle', 'tool1LoadedFilament',
        'tool1TargetTemperature', 'tool1TempBar', 'tool1ActualTemperature', 'tool1TextLabel', 'toolSeperationLine',
        'H1TargetTemperature', 'H1ActualTemperature', 'H1TempBar', 'H1Label', 'H1TextLabel'
    ],
    'control_screen': [
        'toolToggleTemperatureButton', 'toolToggleMotionButton',
        'togglePelletSensorT1Button',
        'H1TempSpinBox', 'setH1TempButton', 'H140PreheatButton', 'H160PreheatButton'
    ],
    'filament_management_screen': [
        'changeTool1MaterialBayX', 'tool1Frame', 'editTool1MaterialBayX',
        'tool11MaterialBayXStateColor', 'tool1MaterialBayXStateLabel', 'changeTool1Button',
        'tool1MaterialBayXLabel'
    ],
    'calibrate_screen': [
        'idexCalibrationWizardButton', 'toolOffsetZButton', 'toolOffsetXYButton',
        'cameraToolOffsetCalibrateButton', 'toolZOffsetWizardButton'
    ]
}

# UI elements that should only be shown for printers with heater ring (Volterra ALF)
# Note: ALF ring heater shows power % only (via ALFLabel), not temperature
# Only include QWidget-based elements (not layouts, which don't have show/hide methods)
HEATER_RING_ELEMENTS = {
    'home_screen': [
        'heaterRingLabel', 'ALFLabel', 'heaterRingSeparationLine', 'label_15'
    ]
}

# UI elements that should only be shown for printers with heated chamber
HEATED_CHAMBER_ELEMENTS = {
    'home_screen': [
        'chamberLabel', 'chamberTextLabel', 'chamberTargetTemperature', 
        'chamberActualTemperature', 'chamberTempBar'
    ]
}

# UI elements that should only be shown for printers with filament spool heater
SPOOL_HEATER_ELEMENTS = {
    'home_screen': [
        'spoolLabel', 'spoolTextLabel', 'spoolTargetTemperature',
        'spoolActualTemperature', 'spoolTempBar'
    ]
}

def hide_dual_nozzle_elements(widget, element_names):
    """
    Hide specified UI elements if printer is configured for single nozzle.
    
    Args:
        widget: The parent widget containing the elements
        element_names: List of element names to hide for single nozzle printers
    """
    if not is_dual_nozzle_printer():
        for element_name in element_names:
            element = getattr(widget, element_name, None)
            if element:
                try:
                    element.hide()
                    logger.debug(f"Hidden dual nozzle element: {element_name}")
                except Exception as e:
                    logger.error(f"Error hiding element {element_name}: {e}")

def force_single_tool(requested_tool):
    """
    Force tool1 requests to tool0 for single nozzle printers.
    
    Args:
        requested_tool: The requested tool ("tool0" or "tool1")
        
    Returns:
        str: "tool0" for single nozzle printers, original tool for dual nozzle
    """
    if requested_tool == "tool1" and not is_dual_nozzle_printer():
        logger.info("Forced tool1 to tool0 for single nozzle configuration")
        return "tool0"
    return requested_tool

def get_dual_nozzle_elements(screen_name):
    """
    Get the list of dual nozzle elements for a specific screen.
    
    Args:
        screen_name: Name of the screen (e.g., 'home_screen', 'control_screen')
        
    Returns:
        list: List of element names to hide for single nozzle printers
    """
    return DUAL_NOZZLE_ELEMENTS.get(screen_name, [])

def get_heater_ring_elements(screen_name):
    """
    Get the list of heater ring elements for a specific screen.
    
    Args:
        screen_name: Name of the screen (e.g., 'home_screen')
        
    Returns:
        list: List of element names to show only for heater ring printers
    """
    return HEATER_RING_ELEMENTS.get(screen_name, [])

def get_heated_chamber_elements(screen_name):
    """
    Get the list of heated chamber elements for a specific screen.
    
    Args:
        screen_name: Name of the screen (e.g., 'home_screen')
        
    Returns:
        list: List of element names to show only for heated chamber printers
    """
    return HEATED_CHAMBER_ELEMENTS.get(screen_name, [])

def get_spool_heater_elements(screen_name):
    """
    Get the list of spool heater elements for a specific screen.
    
    Args:
        screen_name: Name of the screen (e.g., 'home_screen')
        
    Returns:
        list: List of element names to show only for spool heater printers
    """
    return SPOOL_HEATER_ELEMENTS.get(screen_name, [])

def hide_heater_ring_elements(widget, element_names):
    """
    Show or hide heater ring UI elements based on printer configuration.
    
    Args:
        widget: The parent widget containing the elements
        element_names: List of element names to show/hide based on heater ring presence
    """
    has_ring = has_heater_ring()
    logger.info(f"hide_heater_ring_elements called: has_ring={has_ring}, elements={element_names}")
    for element_name in element_names:
        element = getattr(widget, element_name, None)
        if element is None:
            # Try findChild as fallback for elements not stored as attributes
            element = widget.findChild(QWidget, element_name)
        if element:
            try:
                if has_ring:
                    element.show()
                    logger.info(f"Shown heater ring element: {element_name}")
                else:
                    element.hide()
                    logger.info(f"Hidden heater ring element: {element_name}")
            except Exception as e:
                logger.error(f"Error showing/hiding element {element_name}: {e}")
        else:
            logger.warning(f"Heater ring element not found: {element_name}")

def hide_heated_chamber_elements(widget, element_names):
    """
    Show or hide heated chamber UI elements based on printer configuration.
    
    Args:
        widget: The parent widget containing the elements
        element_names: List of element names to show/hide based on heated chamber presence
    """
    has_chamber = has_heated_chamber()
    logger.info(f"hide_heated_chamber_elements called: has_chamber={has_chamber}, elements={element_names}")
    for element_name in element_names:
        element = getattr(widget, element_name, None)
        if element is None:
            # Try findChild as fallback for elements not stored as attributes
            element = widget.findChild(QWidget, element_name)
        if element:
            try:
                if has_chamber:
                    element.show()
                    logger.info(f"Shown heated chamber element: {element_name}")
                else:
                    element.hide()
                    logger.info(f"Hidden heated chamber element: {element_name}")
            except Exception as e:
                logger.error(f"Error showing/hiding element {element_name}: {e}")
        else:
            logger.warning(f"Heated chamber element not found: {element_name}")

def hide_spool_heater_elements(widget, element_names):
    """
    Show or hide spool heater UI elements based on printer configuration.
    
    Args:
        widget: The parent widget containing the elements
        element_names: List of element names to show/hide based on spool heater presence
    """
    has_spool = has_spool_heater()
    logger.info(f"hide_spool_heater_elements called: has_spool={has_spool}, elements={element_names}")
    for element_name in element_names:
        element = getattr(widget, element_name, None)
        if element is None:
            # Try findChild as fallback for elements not stored as attributes
            element = widget.findChild(QWidget, element_name)
        if element:
            try:
                if has_spool:
                    element.show()
                    logger.info(f"Shown spool heater element: {element_name}")
                else:
                    element.hide()
                    logger.info(f"Hidden spool heater element: {element_name}")
            except Exception as e:
                logger.error(f"Error showing/hiding element {element_name}: {e}")
        else:
            logger.warning(f"Spool heater element not found: {element_name}")

def apply_nozzle_config_to_screen(widget, screen_name):
    """
    Apply nozzle configuration to a specific screen widget.
    
    Args:
        widget: The screen widget
        screen_name: Name of the screen for element lookup
    """
    hide_dual_nozzle_elements(widget, get_dual_nozzle_elements(screen_name))
    hide_heater_ring_elements(widget, get_heater_ring_elements(screen_name))
    hide_heated_chamber_elements(widget, get_heated_chamber_elements(screen_name))
    hide_spool_heater_elements(widget, get_spool_heater_elements(screen_name))

def apply_nozzle_config_to_all_screens(main_window):
    """
    Apply nozzle configuration to all screens in the main window.
    
    Args:
        main_window: The main window containing all screen widgets
    """
    if not is_dual_nozzle_printer():
        try:
            for screen_name, elements in DUAL_NOZZLE_ELEMENTS.items():
                if hasattr(main_window, screen_name):
                    screen = getattr(main_window, screen_name)
                    hide_dual_nozzle_elements(screen, elements)
                    
            logger.info("Successfully applied single nozzle configuration to all screens")
        except Exception as e:
            logger.error(f"Error applying nozzle configuration: {e}")
    else:
        logger.info("Dual nozzle configuration active - all elements visible")
    
    # Apply heater ring visibility (show if has_heater_ring, hide otherwise)
    try:
        for screen_name, elements in HEATER_RING_ELEMENTS.items():
            if hasattr(main_window, screen_name):
                screen = getattr(main_window, screen_name)
                hide_heater_ring_elements(screen, elements)
                
        if has_heater_ring():
            logger.info("Heater ring configuration active - heater ring elements shown")
        else:
            logger.info("Hidden heater ring elements - printer does not have heater ring")
    except Exception as e:
        logger.error(f"Error applying heater ring configuration: {e}")

    # Apply heated chamber visibility (show if has_heated_chamber, hide otherwise)
    try:
        for screen_name, elements in HEATED_CHAMBER_ELEMENTS.items():
            if hasattr(main_window, screen_name):
                screen = getattr(main_window, screen_name)
                hide_heated_chamber_elements(screen, elements)
                
        if has_heated_chamber():
            logger.info("Heated chamber configuration active - heated chamber elements shown")
        else:
            logger.info("Hidden heated chamber elements - printer does not have heated chamber")
    except Exception as e:
        logger.error(f"Error applying heated chamber configuration: {e}")

    # Apply spool heater visibility (show if has_spool_heater, hide otherwise)
    try:
        for screen_name, elements in SPOOL_HEATER_ELEMENTS.items():
            if hasattr(main_window, screen_name):
                screen = getattr(main_window, screen_name)
                hide_spool_heater_elements(screen, elements)
                
        if has_spool_heater():
            logger.info("Spool heater configuration active - spool heater elements shown")
        else:
            logger.info("Hidden spool heater elements - printer does not have spool heater")
    except Exception as e:
        logger.error(f"Error applying spool heater configuration: {e}")
