# coding=utf-8
from __future__ import absolute_import

import octoprint.plugin
from octoprint.events import Events
from octoprint.server import NO_CONTENT
from flask import jsonify
import os
import subprocess
import sys
import time
import threading
from time import sleep

# Try to import RPi.GPIO, but handle the case where it's not available (e.g., on non-Raspberry Pi systems)
try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except (ImportError, RuntimeError):
    GPIO_AVAILABLE = False
    GPIO = None

from ._version import get_versions
_versioneer_info = get_versions()
__version__ = _versioneer_info['version']
# Commit hash is what the github_commit update checker compares against
__commit__ = _versioneer_info.get('full-revisionid') or __version__
del get_versions


class StrobeLED(threading.Thread):
    """Thread class for controlling LED strobe effect"""
    DELAY_ON = 100
    DELAY_OFF = 200

    def __init__(self, pin, delay_on=DELAY_ON, delay_off=DELAY_OFF, fn_on=None, fn_off=None):
        super(StrobeLED, self).__init__()
        self.daemon = True  # Daemon thread so it doesn't block OctoPrint shutdown
        self.pin = pin
        self.delay_on = delay_on
        self.delay_off = delay_off
        self._stop_event = threading.Event()
        self.fn_on = fn_on
        self.fn_off = fn_off

    def stop(self):
        self._stop_event.set()

    def stopped(self):
        return self._stop_event.is_set()

    def run(self):
        while not self.stopped():
            try:
                if GPIO_AVAILABLE:
                    GPIO.output(self.pin, GPIO.HIGH)
                if self.fn_on:
                    self.fn_on()
                sleep(self.delay_on / 1000.0)
                if GPIO_AVAILABLE:
                    GPIO.output(self.pin, GPIO.LOW)
                if self.fn_off:
                    self.fn_off()
                sleep(self.delay_off / 1000.0)
            except:
                pass

# import time
# import subprocess
# from threading import Timer

# class RepeatedTimer(object):
# 	def __init__(self, interval, function, *args, **kwargs):
# 		self._timer = None
# 		self.interval = interval
# 		self.function = function
# 		self.args = args
# 		self.kwargs = kwargs
# 		self.is_running = False
#
# 	def _run(self):
# 		self.is_running = False
# 		self.start()
# 		self.function(*self.args, **self.kwargs)
#
# 	def start(self):
# 		if not self.is_running:
# 			self._timer = Timer(self.interval, self._run)
# 			self._timer.start()
# 			self.is_running = True
#
# 	def stop(self):
# 		if self.is_running:
# 			self._timer.cancel()
# 			self.is_running = False


class PenroseControlCenter(octoprint.plugin.StartupPlugin,
                           octoprint.plugin.EventHandlerPlugin,
                           octoprint.plugin.TemplatePlugin,
                           octoprint.plugin.SettingsPlugin,
                           octoprint.plugin.BlueprintPlugin,
                           octoprint.plugin.AssetPlugin):
    
    '''
    Tower Light GPIO pin mapping (BCM numbering)
    BCM   BOARD
    '''
    PIN_R = 19  # 35 - Red LED (Offline)
    PIN_Y = 16  # 36 - Yellow LED (Paused)
    PIN_G = 20  # 38 - Green LED (Printing)
    PIN_B = 21  # 40 - Blue LED (Operational)

    '''
    Door Lock GPIO pin mapping (BCM numbering)
    '''
    PIN_DOOR_LOCK = 13  # Door lock relay control

    '''
    Door Lock State
    '''
    DOOR_STATE = 'unlocked'

    '''
    OctoPrint states
    '''
    STATE_OFFLINE = "Offline"
    STATE_PAUSED = "Paused"
    STATE_PRINTING = "Printing"
    STATE_OPERATIONAL = "Operational"
    AVAILABLE_STATES = [STATE_OFFLINE, STATE_PAUSED, STATE_PRINTING, STATE_OPERATIONAL]
    BLINK_STATES = [STATE_PAUSED, STATE_PRINTING, STATE_OPERATIONAL]

    '''
    Mapping
    '''
    MAP_LED_STATE = {
        STATE_OFFLINE: PIN_R,
        STATE_PAUSED: PIN_Y,
        STATE_PRINTING: PIN_G,
        STATE_OPERATIONAL: PIN_B
    }

    MAP_UI_STATE = {
        STATE_OFFLINE: "red",
        STATE_PAUSED: "yellow",
        STATE_PRINTING: "green",
        STATE_OPERATIONAL: "blue"
    }

    '''
    Global variables
    '''
    __thread_strobe = None
    __machine_state = None

    '''
    Logging helpers
    '''
    def log_info(self, txt):
        self._logger.info(txt)

    def log_error(self, txt):
        self._logger.error(txt)

    '''
    Tower Light Settings Properties
    '''
    @property
    def tower_enabled(self):
        return self._settings.get_boolean(["tower_enabled"])

    @property
    def strobe(self):
        return self._settings.get_boolean(["strobe"])

    @property
    def delay_on(self):
        return self._settings.get_int(["delay_on"])

    @property
    def delay_off(self):
        return self._settings.get_int(["delay_off"])

    '''
    Door Lock Settings Properties
    '''
    @property
    def door_lock_enabled(self):
        return self._settings.get_boolean(["door_lock_enabled"])

    @property
    def auto_lock_on_print(self):
        return self._settings.get_boolean(["auto_lock_on_print"])

    '''
    Door Lock Control Methods
    '''
    def lock_door(self):
        """Lock the door by setting the relay HIGH"""
        if not self.door_lock_enabled:
            return
        try:
            if GPIO_AVAILABLE:
                GPIO.output(self.PIN_DOOR_LOCK, GPIO.HIGH)
            self.DOOR_STATE = 'locked'
            self.log_info("Door Locked")
            self._plugin_manager.send_plugin_message(
                self._identifier, 
                dict(type="door_state", door_state="locked")
            )
        except Exception as e:
            self.log_error(f"Error locking door: {e}")

    def unlock_door(self):
        """Unlock the door by setting the relay LOW"""
        if not self.door_lock_enabled:
            return
        try:
            if GPIO_AVAILABLE:
                GPIO.output(self.PIN_DOOR_LOCK, GPIO.LOW)
            self.DOOR_STATE = 'unlocked'
            self.log_info("Door Unlocked")
            self._plugin_manager.send_plugin_message(
                self._identifier, 
                dict(type="door_state", door_state="unlocked")
            )
        except Exception as e:
            self.log_error(f"Error unlocking door: {e}")

    def toggle_door_lock(self):
        """Toggle the door lock state"""
        if self.DOOR_STATE == 'unlocked':
            self.lock_door()
        else:
            self.unlock_door()

    def get_door_status(self):
        """Get current door lock status"""
        return dict(
            door_lock_enabled=self.door_lock_enabled,
            door_state=self.DOOR_STATE
        )

    '''
    Door Lock REST API Endpoints
    '''
    @octoprint.plugin.BlueprintPlugin.route("/lock_override", methods=["GET"])
    def route_lock_override(self):
        """Toggle door lock state via REST API"""
        self.toggle_door_lock()
        return NO_CONTENT

    @octoprint.plugin.BlueprintPlugin.route("/door_status", methods=["GET"])
    def route_door_status(self):
        """Get door lock status via REST API"""
        return jsonify(self.get_door_status())

    @octoprint.plugin.BlueprintPlugin.route("/lock_door", methods=["GET"])
    def route_lock_door(self):
        """Lock door via REST API"""
        self.lock_door()
        return NO_CONTENT

    @octoprint.plugin.BlueprintPlugin.route("/unlock_door", methods=["GET"])
    def route_unlock_door(self):
        """Unlock door via REST API"""
        self.unlock_door()
        return NO_CONTENT

    '''
    Tower Light Thread Management
    '''
    def kill_thread_strobe(self):
        if self.__thread_strobe is not None and self.__thread_strobe.is_alive():
            self.__thread_strobe.stop()
        self.__thread_strobe = None

    def start_thread_strobe(self, pin):
        try:
            self.kill_thread_strobe()
            self.__thread_strobe = StrobeLED(pin, self.delay_on, self.delay_off, 
                                            self.strobe_fn_on, self.strobe_fn_off)
            self.__thread_strobe.start()
        except Exception as e:
            self.log_error(f"Error starting strobe thread: {e}")

    '''
    Tower Light Helpers
    '''
    def send_machine_state(self, color):
        self._plugin_manager.send_plugin_message(self._identifier, 
                                                  dict(type="machine_state", machine_state=str(color)))

    def set_light_state(self, pin, state=None):
        if state is None:
            state = GPIO.LOW if GPIO_AVAILABLE else 0
        try:
            if GPIO_AVAILABLE:
                GPIO.output(pin, state)
        except Exception as e:
            self.log_error(f"Error setting light state: {e}")

    def reset_lights(self):
        self.set_light_state(self.PIN_R)
        self.set_light_state(self.PIN_Y)
        self.set_light_state(self.PIN_G)
        self.set_light_state(self.PIN_B)

    def handle_machine_state(self):
        try:
            self.kill_thread_strobe()
        except Exception as e:
            self.log_error(f"Error killing strobe thread: {e}")

        self.reset_lights()

        if self.__machine_state not in self.AVAILABLE_STATES:
            return

        if self.strobe and self.__machine_state in self.BLINK_STATES:
            self.log_info("Strobe " + self.__machine_state)
            self.start_thread_strobe(self.MAP_LED_STATE[self.__machine_state])
        else:
            self.log_info("Static " + self.__machine_state)
            if GPIO_AVAILABLE:
                self.set_light_state(self.MAP_LED_STATE[self.__machine_state], GPIO.HIGH)
            self.send_machine_state(self.MAP_UI_STATE[self.__machine_state])

    def strobe_fn_on(self):
        if self.__machine_state in self.MAP_UI_STATE:
            self.send_machine_state(self.MAP_UI_STATE[self.__machine_state])

    def strobe_fn_off(self):
        self.send_machine_state("")

    '''
    Tower Light GPIO Initialization
    '''
    def _gpio_clean_pin(self, pin):
        try:
            if GPIO_AVAILABLE:
                GPIO.cleanup(pin)
        except:
            pass

    def _gpio_setup(self):
        if not GPIO_AVAILABLE:
            self.log_info("Tower Light: RPi.GPIO not available, skipping GPIO setup")
            return
            
        try:
            GPIO.setmode(GPIO.BCM)

            self._gpio_clean_pin(self.PIN_R)
            self._gpio_clean_pin(self.PIN_Y)
            self._gpio_clean_pin(self.PIN_G)
            self._gpio_clean_pin(self.PIN_B)
            self._gpio_clean_pin(self.PIN_DOOR_LOCK)

            # Setup Door Lock GPIO
            if self.door_lock_enabled:
                self.log_info("Door Lock GPIO setup on pin %s" % self.PIN_DOOR_LOCK)
                GPIO.setup(self.PIN_DOOR_LOCK, GPIO.OUT, initial=GPIO.LOW)
                self.DOOR_STATE = 'unlocked'
            else:
                self.log_info("Door Lock disabled")

            if self.tower_enabled:
                self.log_info("Tower Light GPIO setup")
                GPIO.setup(self.PIN_R, GPIO.OUT, initial=GPIO.LOW)
                GPIO.setup(self.PIN_Y, GPIO.OUT, initial=GPIO.LOW)
                GPIO.setup(self.PIN_G, GPIO.OUT, initial=GPIO.LOW)
                GPIO.setup(self.PIN_B, GPIO.OUT, initial=GPIO.LOW)

                self.reset_lights()
            else:
                self.log_info("Tower Light disabled")

        except Exception as e:
            self.log_error(f"Error in GPIO setup: {e}")

    '''
    Plugin Initialization
    '''
    def initialize(self):
        if GPIO_AVAILABLE:
            self.log_info("Running RPi.GPIO version '{0}'".format(GPIO.VERSION))
            if GPIO.VERSION < "0.6":
                raise Exception("RPi.GPIO must be greater than 0.6")
            GPIO.setwarnings(False)
        else:
            self.log_info("RPi.GPIO not available - Tower Light will be UI-only")

    '''
    Event Handling
    '''
    def on_event(self, event, payload):
        # Door Lock Event Handling
        if self.door_lock_enabled and self.auto_lock_on_print:
            if event == Events.PRINT_STARTED:
                self.lock_door()
            elif event in (Events.PRINT_DONE, Events.PRINT_CANCELLED, Events.PRINT_FAILED):
                self.unlock_door()

        # Tower Light Event Handling
        if not self.tower_enabled:
            return
            
        if self.__machine_state == self._printer.get_state_string():
            return
        self.__machine_state = self._printer.get_state_string()
        self.handle_machine_state()

    def on_after_startup(self):
        # self.resetInetrval = int(self._settings.get(["resetInetrval"]))
        self._logger.info("Penrose TouchUI Plugin Started")
        
        # Initialize Tower Light GPIO
        self._gpio_setup()
        self.log_info("PenroseControlCenter Tower Light initialized")
        
        # Check and update xinit file
        self._check_and_update_xinit_file()
        
        # self._worker = RepeatedTimer(self.resetInetrval, self.worker)
        # self._worker.start()
    
    def _check_and_update_xinit_file(self):
        """Check and update the xinit file with the correct path to main.py"""
        xinit_file = "/etc/X11/xinit/xinitrc"
        
        try:
            # Get the current plugin directory path
            plugin_dir = os.path.dirname(os.path.abspath(__file__))
            main_py_path = os.path.join(plugin_dir, "main.py")
            
            # Verify that main.py exists in the plugin directory
            if not os.path.exists(main_py_path):
                self._logger.error(f"main.py not found at expected location: {main_py_path}")
                return
            
            # Expected xinit content - using the detected plugin directory
            expected_content = f"""#!/bin/sh

# /etc/X11/xinit/xinitrc
#
# global xinitrc file, used by all X sessions started by xinit (startx)
cd {plugin_dir}/
sudo chmod +x main.py
sudo python3 main.py
# invoke global X session script
. /etc/X11/Xsession
"""
            
            needs_update = False
            current_content = ""
            
            # Check if xinit file exists and read its content
            try:
                with open(xinit_file, 'r') as f:
                    current_content = f.read()
                    
                # Check if the content contains the correct path to our plugin
                if plugin_dir not in current_content or "octoprint_PenroseControlCenter" not in current_content:
                    needs_update = True
                    self._logger.info(f"xinit file does not contain correct path to {plugin_dir}")
                else:
                    self._logger.info("xinit file already contains correct PenroseControlCenter path")
                    
            except FileNotFoundError:
                needs_update = True
                self._logger.info("xinit file does not exist, will create it")
            except PermissionError as e:
                self._logger.error(f"Permission denied reading xinit file: {e}")
                return
            except IOError as e:
                self._logger.error(f"Error reading xinit file: {e}")
                return
            
            # Update the file if needed
            if needs_update:
                try:
                    # Write the new content to a temporary file first
                    temp_file = "/tmp/xinitrc_temp"
                    with open(temp_file, 'w') as f:
                        f.write(expected_content)
                    
                    # Use sudo to copy the file to the correct location
                    result = subprocess.run(
                        ["sudo", "cp", temp_file, xinit_file], 
                        check=True, 
                        capture_output=True, 
                        text=True,
                        timeout=15
                    )
                    
                    # Set proper permissions
                    subprocess.run(
                        ["sudo", "chmod", "755", xinit_file], 
                        check=True, 
                        capture_output=True, 
                        text=True,
                        timeout=15
                    )
                    
                    # Clean up temp file
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                    
                    self._logger.info(f"Successfully updated xinit file with PenroseControlCenter path: {plugin_dir}")
                    
                    # Restart the X session with the new xinit configuration (in background to not block startup)
                    restart_thread = threading.Thread(target=self._restart_touch_ui, daemon=True)
                    restart_thread.start()
                    
                except subprocess.CalledProcessError as e:
                    self._logger.error(f"Failed to update xinit file: {e}")
                    if e.stderr:
                        self._logger.error(f"Command stderr: {e.stderr}")
                    if e.stdout:
                        self._logger.error(f"Command stdout: {e.stdout}")
                except subprocess.TimeoutExpired as e:
                    self._logger.error(f"Timeout running sudo command for xinit file: {e}")
                except OSError as e:
                    self._logger.error(f"OS error when updating xinit file: {e}")
                except Exception as e:
                    self._logger.error(f"Unexpected error updating xinit file: {e}")
                finally:
                    # Ensure temp file is cleaned up even if there's an error
                    if os.path.exists("/tmp/xinitrc_temp"):
                        try:
                            os.remove("/tmp/xinitrc_temp")
                        except:
                            pass
                    
        except Exception as e:
            self._logger.error(f"Error in _check_and_update_xinit_file: {e}")
            import traceback
            self._logger.error(f"Traceback: {traceback.format_exc()}")
    
    def _restart_touch_ui(self):
        """Restart the touch UI by running sudo startx"""
        try:
            self._logger.info("Restarting touch UI with updated xinit configuration...")
            
            # First, try to kill any existing X sessions
            try:
                # Kill existing X sessions gracefully
                result = subprocess.run(
                    ["sudo", "pkill", "-f", "startx"], 
                    capture_output=True, 
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    self._logger.info("Terminated existing X sessions")
                else:
                    # pkill returns 1 when no processes matched
                    self._logger.info("No existing X sessions found to terminate")
                
                # Give it a moment to clean up
                time.sleep(2)
                
            except subprocess.TimeoutExpired:
                self._logger.warning("Timeout while trying to terminate X sessions")
            except Exception as e:
                self._logger.warning(f"Error terminating X sessions: {e}")
            
            # Start the new X session with startx
            # Use Popen to start it in the background since startx is a long-running process
            try:
                self._logger.info("Starting new X session with sudo startx...")
                
                # Start startx in the background
                process = subprocess.Popen(
                    ["sudo", "startx"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                self._logger.info(f"Started touch UI process with PID: {process.pid}")
                
                # Don't wait for the process to complete since startx runs indefinitely
                # Just log that we started it successfully
                
            except Exception as e:
                self._logger.error(f"Failed to start touch UI with startx: {e}")
                
        except Exception as e:
            self._logger.error(f"Error in _restart_touch_ui: {e}")
            import traceback
            self._logger.error(f"Traceback: {traceback.format_exc()}")

    '''
    Settings Management
    '''
    def on_settings_save(self, data):
        octoprint.plugin.SettingsPlugin.on_settings_save(self, data)
        self._gpio_setup()
        self.handle_machine_state()

    def get_settings_defaults(self):
        return dict(
            # Tower Light settings
            tower_enabled=True,
            strobe=True,
            delay_on=100,
            delay_off=1000,
            # Door Lock settings
            door_lock_enabled=True,
            auto_lock_on_print=True
        )

    '''
    Asset Management
    '''
    def get_assets(self):
        return dict(
            js=["js/PenroseControlCenter_navbar.js", "js/PenroseControlCenter_settings.js"],
            css=["css/towerlight.css"]
        )

    '''
    Template Management
    '''
    def get_template_configs(self):
        return [
            dict(type="navbar", custom_bindings=True),
            dict(type="settings", custom_bindings=True)
        ]

    '''
    Update Management
    '''
    def get_update_information(self):
        # Tracked by commit on the Hybrid IDEX branch, not by release tag:
        # github_release would treat any new tag on the default branch as
        # newer and overwrite this variant's changes on the next update.
        return dict(
            PenroseControlCenter=dict(
                displayName="PenroseControlCenter (Hybrid IDEX)",
                displayVersion=self._plugin_version,
                # version check: github repository branch
                type="github_commit",
                user="FracktalWorks",
                repo="PenroseControlCenter",
                branch="Hybrid-IDEX-Penrose-600",
                current=__commit__,

                # update method: pip
                pip="https://github.com/FracktalWorks/PenroseControlCenter/archive/Hybrid-IDEX-Penrose-600.zip"
            )
        )


__plugin_name__ = "PenroseControlCenter"
__plugin_version__ = __version__
__plugin_pythoncompat__ = ">=3,<4"


def __plugin_load__():
    global __plugin_implementation__
    __plugin_implementation__ = PenroseControlCenter()

    global __plugin_hooks__
    __plugin_hooks__ = {
        "octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information
    }
