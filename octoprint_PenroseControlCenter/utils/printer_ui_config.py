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

def is_hybrid_printer():
    """Check if the printer is a Hybrid IDEX (T0 pellet auger, T1 filament extruder)."""
    # Access the current value dynamically to pick up changes from Klipper config loading
    return getattr(config, 'IS_HYBRID', False)

def tool_head_type(tool):
    """Return the extruder head type fitted to a tool: 'pellet' or 'filament'.

    On the Hybrid IDEX only the right carriage (tool1) carries a filament
    extruder; every other machine in the Penrose range is pellet on both sides.

    Args:
        tool: Tool identifier - "tool0"/"tool1", or 0/1

    Returns:
        str: 'filament' or 'pellet'
    """
    tool_name = tool if isinstance(tool, str) else f"tool{int(tool)}"
    if is_hybrid_printer() and tool_name == "tool1":
        return 'filament'
    return 'pellet'

def is_filament_tool(tool):
    """Check whether the given tool carries a filament extruder."""
    return tool_head_type(tool) == 'filament'

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
        # Home screen order: tool0 -> toolSeparationLine -> H0 ->
        # toolSeparationLine_2 -> tool1 -> H1 -> bed. Only the separator
        # that leads into the tool1 block goes away with it; the first one
        # still divides tool0 from H0, which both remain on a single nozzle.
        'tool1TargetTemperature', 'tool1TempBar', 'tool1ActualTemperature', 'tool1TextLabel',
        'toolSeparationLine_2',
        'H1TargetTemperature', 'H1ActualTemperature', 'H1TempBar', 'H1Label', 'H1TextLabel'
    ],
    'control_screen': [
        'toolToggleTemperatureButton', 'toolToggleMotionButton',
        'togglePelletSensorT1Button',
        # Hide the H1 container, not its individual controls: it also holds
        # H1Label and H1IconLabel, which otherwise stayed behind as a
        # captionless "H1" heading with nothing under it.
        'horizontalLayoutWidget_H1'
    ],
    'filament_management_screen': [
        'changeTool1MaterialBayX', 'tool1Frame', 'editTool1MaterialBayX',
        'tool11MaterialBayXStateColor', 'tool1MaterialBayXStateLabel', 'changeTool1Button'
    ],
    'calibrate_screen': [
        'idexCalibrationWizardButton', 'toolOffsetZButton', 'toolOffsetXYButton',
        'cameraToolOffsetCalibrateButton', 'toolZOffsetWizardButton'
    ]
}

# UI elements that should be hidden on Hybrid IDEX printers.
# T1 is a filament extruder: it has no H1 barrel heater, so those rows go
# away while the regular tool1 nozzle temperature rows stay visible.
# The tool toggle buttons are also gone: the machine presents as a
# single-extruder printer in either mode, so the mode - not a toggle -
# decides which tool the temperature and motion controls target.
HYBRID_HIDDEN_ELEMENTS = {
    'home_screen': [
        'H1TargetTemperature', 'H1ActualTemperature', 'H1TempBar', 'H1Label', 'H1TextLabel'
    ],
    'control_screen': [
        # Whole H1 column, container and all (see DUAL_NOZZLE_ELEMENTS) -
        # the filament head has no barrel heater
        'horizontalLayoutWidget_H1',
        'toolToggleTemperatureButton', 'toolToggleMotionButton'
    ]
}

# Hybrid extruder-mode skin.
#
# Since the config-swap model, Klipper only ever has ONE extruder, so the
# SKU sets variable_is_dual_nozzle: 0 and DUAL_NOZZLE_ELEMENTS above
# already hides every tool1 row, the H1 column and the T0/T1 toggles.
# The only thing that still varies BETWEEN the two modes is the heater
# count:
#
#   PELLET   - TWO heaters: the nozzle (tool0 rows) AND the H0 pellet
#              barrel heater. Both must be visible and both must be
#              settable from the Control screen.
#   FILAMENT - ONE heater: the nozzle only. There is no H0 hardware in
#              this config at all, so every H0 row and control is hidden.
#
# Keyed by mode -> screen -> elements hidden while that mode is active
# (and re-shown when the mode flips). Anything listed under one mode but
# not the other is what toggles.
MODE_HIDDEN_ELEMENTS = {
    'pellet': {
        # Nothing extra to hide: pellet mode is the "everything visible"
        # case - nozzle rows plus the H0 barrel rows.
        'home_screen': [],
        'control_screen': [],
        'filament_management_screen': []
    },
    'filament': {
        'home_screen': [
            # No H0 barrel heater on the filament head. Its separator goes
            # too, or the layout leaves a divider with nothing under it.
            'H0TargetTemperature', 'H0ActualTemperature', 'H0TempBar',
            'H0Label', 'H0TextLabel', 'toolSeparationLine'
        ],
        'control_screen': [
            # Whole H0 barrel column - container hides label, icon,
            # spinbox, set button and both preheat buttons in one go
            'horizontalLayoutWidget_H0'
        ],
        'filament_management_screen': []
    }
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

def get_hybrid_hidden_elements(screen_name):
    """
    Get the list of elements to hide on Hybrid IDEX printers for a screen.

    Args:
        screen_name: Name of the screen (e.g., 'home_screen', 'control_screen')

    Returns:
        list: List of element names to hide on Hybrid IDEX printers
    """
    return HYBRID_HIDDEN_ELEMENTS.get(screen_name, [])

def hide_hybrid_elements(widget, element_names):
    """
    Hide UI elements that do not apply to a Hybrid IDEX printer.

    Args:
        widget: The parent widget containing the elements
        element_names: List of element names to hide on Hybrid IDEX printers
    """
    if not is_hybrid_printer():
        return
    for element_name in element_names:
        element = getattr(widget, element_name, None)
        if element is None:
            element = widget.findChild(QWidget, element_name)
        if element:
            try:
                element.hide()
                logger.debug(f"Hidden hybrid IDEX element: {element_name}")
            except Exception as e:
                logger.error(f"Error hiding element {element_name}: {e}")

def get_extruder_mode():
    """Return the Hybrid IDEX runtime extruder mode ('pellet'/'filament')."""
    # Mirrored from Klipper's variables.cfg by PrinterModel.update_extruder_mode()
    return getattr(config, 'EXTRUDER_MODE', 'pellet')

def apply_extruder_mode_visibility(widget, screen_name):
    """Skin a screen for the active Hybrid IDEX extruder mode.

    In either mode the machine presents as a single-extruder printer:
    the other tool's rows are hidden, and the rows belonging to the
    active mode's tool are re-shown (so flipping the mode back and
    forth works without a restart). No-op on non-hybrid printers.

    Args:
        widget: The screen widget
        screen_name: Name of the screen for element lookup
    """
    if not is_hybrid_printer():
        return
    mode = get_extruder_mode()
    other = 'filament' if mode == 'pellet' else 'pellet'

    def _resolve(name):
        element = getattr(widget, name, None)
        if element is None:
            element = widget.findChild(QWidget, name)
        return element

    # Show the rows the other mode had hidden first, then hide this
    # mode's list - elements in both lists (e.g. the separator line)
    # end up hidden, which is what a single-tool presentation wants.
    for name in MODE_HIDDEN_ELEMENTS.get(other, {}).get(screen_name, []):
        element = _resolve(name)
        if element:
            try:
                element.show()
            except Exception as e:
                logger.error(f"Error showing element {name}: {e}")
    for name in MODE_HIDDEN_ELEMENTS.get(mode, {}).get(screen_name, []):
        element = _resolve(name)
        if element:
            try:
                element.hide()
            except Exception as e:
                logger.error(f"Error hiding element {name}: {e}")
    logger.debug(f"Applied {mode} mode visibility to {screen_name}")

def apply_extruder_mode_to_all_screens(main_window):
    """Re-skin every mode-aware screen for the active extruder mode.

    Called at startup and whenever PrinterModel.extruder_mode_changed
    fires, so the touchscreen follows mode switches live - no firmware
    restart needed.
    """
    if not is_hybrid_printer():
        return
    mode = get_extruder_mode()
    screen_names = set()
    for per_mode in MODE_HIDDEN_ELEMENTS.values():
        screen_names.update(per_mode.keys())
    for screen_name in screen_names:
        if hasattr(main_window, screen_name):
            screen = getattr(main_window, screen_name)
            apply_extruder_mode_visibility(screen, screen_name)
            # Screens with mode-dependent behaviour beyond show/hide
            # (control routing, selector state) expose a hook
            if hasattr(screen, 'on_extruder_mode_applied'):
                try:
                    screen.on_extruder_mode_applied(mode)
                except Exception as e:
                    logger.error(f"Error in {screen_name}.on_extruder_mode_applied: {e}")
    logger.info(f"Applied extruder mode '{mode}' to screens: {sorted(screen_names)}")

def configure_sensor_toggles_for_hybrid(widget):
    """
    Relabel the control screen's sensor toggle for the active Hybrid mode.

    The machine is single-extruder in both modes, so there is exactly ONE
    sensor toggle (``togglePelletSensorT0Button``); the T1 toggle is
    hidden by the single-nozzle path. What that one toggle means depends
    on which head is fitted by the active config:

        pellet mode   -> the hopper level sensor (pellet_sensor_left)
        filament mode -> the filament runout switch (switch_sensor_E1)

    Only the label changes here; the routing lives in
    ControlScreen.togglePelletSensorT0 and
    MainController.apply_extruder_sensors, both of which key off the mode.

    Args:
        widget: The control screen widget
    """
    if not is_hybrid_printer():
        return
    mode = get_extruder_mode()
    label_text = ('Filament Runout Sensor' if mode == 'filament'
                  else 'Pellet Level Sensor')
    element = getattr(widget, 'feedRateLabelControlPage_3', None)
    if element is None:
        element = widget.findChild(QWidget, 'feedRateLabelControlPage_3')
    if element is None:
        logger.warning("Sensor toggle label not found: feedRateLabelControlPage_3")
        return
    try:
        element.setText(label_text)
        logger.debug(f"Sensor toggle relabelled for {mode} mode -> '{label_text}'")
    except Exception as e:
        logger.error(f"Error relabelling sensor toggle: {e}")


def configure_material_bay_for_hybrid(widget):
    """
    Name the single material bay after the head the active config fits.

    Only one bay is shown (the machine is single-extruder), so "Tool 0" is
    replaced with the head type - which is also the cue that tells the
    operator which mode the machine is currently in.

    Args:
        widget: The filament management screen widget
    """
    if not is_hybrid_printer():
        return
    mode = get_extruder_mode()
    title = 'Filament Extruder' if mode == 'filament' else 'Pellet Extruder'
    element = getattr(widget, 'calibrateLabel_6', None)
    if element is None:
        element = widget.findChild(QWidget, 'calibrateLabel_6')
    if element is None:
        logger.warning("Material bay label not found: calibrateLabel_6")
        return
    try:
        element.setText(title)
        logger.debug(f"Material bay relabelled -> '{title}'")
    except Exception as e:
        logger.error(f"Error relabelling material bay: {e}")

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
    hide_hybrid_elements(widget, get_hybrid_hidden_elements(screen_name))
    apply_extruder_mode_visibility(widget, screen_name)
    hide_heater_ring_elements(widget, get_heater_ring_elements(screen_name))
    hide_heated_chamber_elements(widget, get_heated_chamber_elements(screen_name))
    hide_spool_heater_elements(widget, get_spool_heater_elements(screen_name))
    if screen_name == 'control_screen':
        configure_sensor_toggles_for_hybrid(widget)
    elif screen_name == 'filament_management_screen':
        configure_material_bay_for_hybrid(widget)

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

    # Apply Hybrid IDEX visibility (hide H1 barrel heater rows, relabel toggles)
    if is_hybrid_printer():
        try:
            for screen_name, elements in HYBRID_HIDDEN_ELEMENTS.items():
                if hasattr(main_window, screen_name):
                    screen = getattr(main_window, screen_name)
                    hide_hybrid_elements(screen, elements)
            if hasattr(main_window, 'control_screen'):
                configure_sensor_toggles_for_hybrid(main_window.control_screen)
            if hasattr(main_window, 'filament_management_screen'):
                configure_material_bay_for_hybrid(main_window.filament_management_screen)

            logger.info("Successfully applied Hybrid IDEX configuration to all screens")
        except Exception as e:
            logger.error(f"Error applying Hybrid IDEX configuration: {e}")

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
