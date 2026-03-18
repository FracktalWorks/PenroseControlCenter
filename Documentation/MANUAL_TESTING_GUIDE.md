# Manual Testing Guide for OctoPrint ControlCenter TouchUI

## Overview

This document provides a comprehensive manual testing checklist for the OctoPrint ControlCenter TouchUI application. The testing process ensures all user interactions work correctly across different printer configurations and operating conditions.

## Prerequisites

### Hardware Requirements
- 3D Printer with Klipper firmware
- OctoPrint server running and accessible
- TouchUI device (Raspberry Pi with touchscreen)
- Network connectivity
- USB storage device (for file transfer tests)
- Test filament for sensor tests
- Test G-code files with different configurations

### Software Requirements
- OctoPrint ControlCenter TouchUI application
- OctoPrint with required plugins:
  - PenrosePrintRestore plugin
  - Klipper plugin
- Test G-code files with embedded metadata

### Test Environment Setup
1. Ensure printer is properly configured and homed
2. Load test filament in both extruders (for dual nozzle printers)
3. Verify network connectivity
4. Have test G-code files ready on local storage and USB
5. Ensure sufficient bed clearance for calibration tests

## Testing Methodology

### Test Execution Guidelines
- Execute tests in the order presented for optimal flow
- Document all failures with screenshots and logs
- Verify both positive and negative test cases
- Test on both single and dual nozzle configurations where applicable
- Test in both connected and minimal UI modes

### Bug Reporting Format
When documenting issues, include:
- Test case name and number
- Steps to reproduce
- Expected behavior
- Actual behavior
- Screenshots/videos if applicable
- Log entries (check `/logs/` directory)
- Printer configuration details

---

## Test Cases

## 1. Startup & Loading Screen Tests

### 1.1 Initial Startup Tests

| Test ID | Test Case | Steps | Expected Result | Status |
|---------|-----------|-------|-----------------|---------|
| START-001 | Application Launch | 1. Power on device<br>2. Wait for application to start | Loading screen appears with progress bar | ☐ |
| START-002 | Connection Success | 1. Ensure OctoPrint is running<br>2. Start application | Progress reaches 100%, switches to home screen | ☐ |
| START-003 | Connection Failure | 1. Stop OctoPrint service<br>2. Start application | Shows failsafe dialog with restore option | ☐ |
| START-004 | Failsafe Restore | 1. Trigger connection failure<br>2. Click "Yes" on failsafe dialog | Attempts to restore settings and restart service | ☐ |
| START-005 | Minimal UI Mode | 1. Trigger connection failure<br>2. Click "No" on failsafe dialog | Loads minimal UI with limited functionality | ☐ |
| START-006 | Virtual Printer Fallback | 1. Disconnect printer<br>2. Start application | Shows virtual printer warning dialog | ☐ |

---

## 2. Home Screen Tests

### 2.1 Navigation Tests

| Test ID | Test Case | Steps | Expected Result | Status |
|---------|-----------|-------|-----------------|---------|
| HOME-001 | Menu Button | Click menu button | Navigates to menu screen | ☐ |
| HOME-002 | Control Button | Click control button | Navigates to control screen | ☐ |

### 2.2 Temperature Display Tests

| Test ID | Test Case | Steps | Expected Result | Status |
|---------|-----------|-------|-----------------|---------|
| HOME-003 | Tool0 Temperature | 1. Heat Tool0 to 200°C<br>2. Observe display | Shows actual/target temperatures correctly | ☐ |
| HOME-004 | Tool1 Temperature | 1. Heat Tool1 to 200°C (dual nozzle only)<br>2. Observe display | Shows actual/target temperatures correctly | ☐ |
| HOME-005 | Bed Temperature | 1. Heat bed to 60°C<br>2. Observe display | Shows actual/target temperatures correctly | ☐ |
| HOME-006 | Temperature Bars | Heat various components | Progress bars update with temperature changes | ☐ |
| HOME-007 | Single Nozzle Mode | Test on single nozzle printer | Tool1 elements are hidden | ☐ |

### 2.3 Print Status Tests

| Test ID | Test Case | Steps | Expected Result | Status |
|---------|-----------|-------|-----------------|---------|
| HOME-008 | File Name Display | Start a print job | Current file name displays correctly | ☐ |
| HOME-009 | Print Time | During active print | Elapsed time updates every second | ☐ |
| HOME-010 | Time Left | During active print | Estimated time remaining updates | ☐ |
| HOME-011 | Progress Bar | During active print | Progress bar reflects completion percentage | ☐ |
| HOME-012 | Feed Rate Display | Change feed rate from control screen | Feed rate percentage updates on home screen | ☐ |
| HOME-013 | Flow Rate Display | Change flow rate from control screen | Flow rate percentage updates on home screen | ☐ |

### 2.4 Control Button Tests

| Test ID | Test Case | Steps | Expected Result | Status |
|---------|-----------|-------|-----------------|---------|
| HOME-014 | Play from Operational | 1. Ensure printer is operational<br>2. Click play button | Starts selected print job | ☐ |
| HOME-015 | Pause During Print | 1. Start print<br>2. Click pause button | Pauses current print job | ☐ |
| HOME-016 | Resume from Pause | 1. Pause print<br>2. Click play button | Resumes paused print job | ☐ |
| HOME-017 | Stop with Confirmation | 1. During print<br>2. Click stop<br>3. Click "Yes" | Shows confirmation, cancels print when confirmed | ☐ |
| HOME-018 | Stop Cancel | 1. During print<br>2. Click stop<br>3. Click "No" | Shows confirmation, continues print when cancelled | ☐ |
| HOME-019 | Door Lock Toggle | Click door lock button (when enabled) | Toggles door lock state | ☐ |

### 2.5 Status Display Tests

| Test ID | Test Case | Steps | Expected Result | Status |
|---------|-----------|-------|-----------------|---------|
| HOME-020 | Connected Status | Ensure OctoPrint connection | Shows "Connected" with green indicator | ☐ |
| HOME-021 | Disconnected Status | Disconnect from OctoPrint | Shows "Disconnected" with red indicator | ☐ |
| HOME-022 | Printing Status | Start print job | Status changes to "Printing" | ☐ |
| HOME-023 | IP Address Display | Check network settings | Correct IP address is displayed | ☐ |
| HOME-024 | Status Colors | Various printer states | Colors match state (green=ok, red=error, amber=warning) | ☐ |

### 2.6 Button State Tests

| Test ID | Test Case | Steps | Expected Result | Status |
|---------|-----------|-------|-----------------|---------|
| HOME-025 | Operational State | Printer in operational state | All buttons enabled appropriately | ☐ |
| HOME-026 | Printing State | During active print | Stop and pause enabled, door lock enabled | ☐ |
| HOME-027 | Paused State | During paused print | Stop and play enabled, door lock enabled | ☐ |
| HOME-028 | Minimal UI State | Start in minimal UI mode | Most buttons disabled with visual indication | ☐ |

---

## 3. Menu Screen Tests

### 3.1 Navigation Tests

| Test ID | Test Case | Steps | Expected Result | Status |
|---------|-----------|-------|-----------------|---------|
| MENU-001 | Print Button | Click print button | Navigates to print location screen | ☐ |
| MENU-002 | Control Button | Click control button | Navigates to control screen | ☐ |
| MENU-003 | Calibrate Button | Click calibrate button | Navigates to calibrate screen | ☐ |
| MENU-004 | Filament/Nozzle Button | Click filament/nozzle button | Navigates to filament management screen | ☐ |
| MENU-005 | Settings Button | Click settings button | Navigates to settings screen | ☐ |
| MENU-006 | Back Button | Click back button | Returns to home screen | ☐ |

### 3.2 Button State Tests

| Test ID | Test Case | Steps | Expected Result | Status |
|---------|-----------|-------|-----------------|---------|
| MENU-007 | Printing State | Start print, go to menu | Calibrate and print buttons disabled | ☐ |
| MENU-008 | Paused State | Pause print, go to menu | Calibrate and print buttons disabled | ☐ |
| MENU-009 | Operational State | Printer operational | All buttons enabled | ☐ |
| MENU-010 | Minimal UI State | In minimal UI mode | Most buttons disabled | ☐ |

---

## 4. Control Screen Tests

### 4.1 Motion Control Tests

| Test ID | Test Case | Steps | Expected Result | Status |
|---------|-----------|-------|-----------------|---------|
| CTRL-001 | Step Selection | Click 1mm, 10mm, 100mm buttons | Step size changes, buttons highlight correctly | ☐ |
| CTRL-002 | X-Axis Movement | Click X+ and X- buttons | Extruder moves in X direction by selected step | ☐ |
| CTRL-003 | Y-Axis Movement | Click Y+ and Y- buttons | Extruder moves in Y direction by selected step | ☐ |
| CTRL-004 | Z-Axis Movement | Click Z+ and Z- buttons | Extruder moves in Z direction by selected step | ☐ |
| CTRL-005 | Home XY | Click home XY button | X and Y axes home to endstops | ☐ |
| CTRL-006 | Home Z | Click home Z button | Z axis homes to endstop | ☐ |
| CTRL-007 | Motors Off | Click motors off button | All stepper motors disable (can move manually) | ☐ |
| CTRL-008 | Baby Steps Z+ | Click Z+ baby step button | Z moves up by 0.025mm | ☐ |
| CTRL-009 | Baby Steps Z- | Click Z- baby step button | Z moves down by 0.025mm | ☐ |
| CTRL-010 | Tool Motion Toggle | Click tool toggle button | Switches active tool for motion (T0/T1) | ☐ |
| CTRL-011 | Motion During Print | Start print, try motion controls | Motion controls disabled during printing | ☐ |

### 4.2 Temperature Control Tests

| Test ID | Test Case | Steps | Expected Result | Status |
|---------|-----------|-------|-----------------|---------|
| CTRL-012 | Tool Temperature Set | 1. Set temperature value<br>2. Click set button | Tool heats to target temperature | ☐ |
| CTRL-013 | Bed Temperature Set | 1. Set bed temperature<br>2. Click set button | Bed heats to target temperature | ☐ |
| CTRL-014 | Temperature Toggle | Click temperature toggle button | Switches between T0 and T1 temperature control | ☐ |
| CTRL-015 | Preheat 180°C | Click 180°C preheat button | Tool heats to 180°C | ☐ |
| CTRL-016 | Preheat 250°C | Click 250°C preheat button | Tool heats to 250°C | ☐ |
| CTRL-017 | Bed 60°C | Click bed 60°C button | Bed heats to 60°C | ☐ |
| CTRL-018 | Bed 100°C | Click bed 100°C button | Bed heats to 100°C | ☐ |
| CTRL-019 | Fan On | Click fan on button | Part cooling fan turns on at 100% | ☐ |
| CTRL-020 | Fan Off | Click fan off button | Part cooling fan turns off | ☐ |
| CTRL-021 | Cooldown | Click cooldown button | All heaters and fans turn off immediately | ☐ |

### 4.3 Extrusion Control Tests

| Test ID | Test Case | Steps | Expected Result | Status |
|---------|-----------|-------|-----------------|---------|
| CTRL-022 | Extrude T0 | 1. Heat T0 to 200°C<br>2. Select T0<br>3. Click extrude | Filament extrudes from T0 nozzle | ☐ |
| CTRL-023 | Retract T0 | 1. Heat T0 to 200°C<br>2. Select T0<br>3. Click retract | Filament retracts into T0 | ☐ |
| CTRL-024 | Extrude T1 | 1. Heat T1 to 200°C<br>2. Select T1<br>3. Click extrude | Filament extrudes from T1 nozzle (dual nozzle only) | ☐ |
| CTRL-025 | Retract T1 | 1. Heat T1 to 200°C<br>2. Select T1<br>3. Click retract | Filament retracts into T1 (dual nozzle only) | ☐ |

### 4.4 Feed/Flow Rate Tests

| Test ID | Test Case | Steps | Expected Result | Status |
|---------|-----------|-------|-----------------|---------|
| CTRL-026 | Feed Rate Change | 1. Change feed rate value<br>2. Click set | Feed rate changes, displays on home screen | ☐ |
| CTRL-027 | Flow Rate Change | 1. Change flow rate value<br>2. Click set | Flow rate changes, displays on home screen | ☐ |

### 4.5 Sensor & Feature Toggle Tests

| Test ID | Test Case | Steps | Expected Result | Status |
|---------|-----------|-------|-----------------|---------|
| CTRL-028 | Filament Runout Toggle | Click runout sensor toggle | Button state changes, preference saves | ☐ |
| CTRL-029 | Filament Jam Toggle | Click jam sensor toggle | Button state changes, preference saves | ☐ |
| CTRL-030 | Print Compatibility Toggle | Click compatibility check toggle | Button state changes, preference saves | ☐ |
| CTRL-031 | Print Restore Toggle | Click print restore toggle | Button state changes, preference saves | ☐ |
| CTRL-032 | Auto Resume Toggle | Click auto resume toggle | Button state changes, preference saves | ☐ |
| CTRL-033 | Auto Resume Dependency | Disable print restore | Auto resume toggle becomes disabled | ☐ |
| CTRL-034 | Settings Persistence | Restart application | All toggle states persist across restarts | ☐ |

---

## 5. Print Location Screen Tests

### 5.1 Location Selection Tests

| Test ID | Test Case | Steps | Expected Result | Status |
|---------|-----------|-------|-----------------|---------|
| PRINT-001 | Local Storage Access | Click local storage button | Displays list of local G-code files | ☐ |
| PRINT-002 | USB Storage Access | 1. Insert USB with G-code files<br>2. Click USB storage | Displays list of USB G-code files | ☐ |
| PRINT-003 | No USB Device | Click USB storage without USB | Shows appropriate message about no USB | ☐ |

### 5.2 File Management Tests

| Test ID | Test Case | Steps | Expected Result | Status |
|---------|-----------|-------|-----------------|---------|
| PRINT-004 | File List Display | Access file storage | Files display with names, sizes, and dates | ☐ |
| PRINT-005 | File Selection | Click on various files | Selection highlighting works correctly | ☐ |
| PRINT-006 | Scroll Navigation | Use scroll up/down buttons | Can navigate through long file lists | ☐ |
| PRINT-007 | Thumbnail Display | Files with thumbnails | Thumbnails display correctly when available | ☐ |
| PRINT-008 | File Details | Select files | File size and metadata display correctly | ☐ |

### 5.3 Print Operations Tests

| Test ID | Test Case | Steps | Expected Result | Status |
|---------|-----------|-------|-----------------|---------|
| PRINT-009 | Select and Print | 1. Select file<br>2. Click print | Print starts immediately | ☐ |
| PRINT-010 | Upload from USB | 1. Select USB file<br>2. Click upload | File copies to local storage | ☐ |
| PRINT-011 | Delete Local File | 1. Select local file<br>2. Click delete<br>3. Confirm | File removed from local storage | ☐ |
| PRINT-012 | Print Without Selection | Click print without selecting file | Shows error message | ☐ |
| PRINT-013 | Large File Handling | Select very large G-code file | Handles large files without crashing | ☐ |

### 5.4 File Compatibility Tests

| Test ID | Test Case | Steps | Expected Result | Status |
|---------|-----------|-------|-----------------|---------|
| PRINT-014 | Compatible File | Print file matching current config | Prints without warnings | ☐ |
| PRINT-015 | Wrong Nozzle Size | Print file with different nozzle size | Shows nozzle mismatch warning | ☐ |
| PRINT-016 | Wrong Material | Print file with different material | Shows material mismatch warning | ☐ |
| PRINT-017 | Override Warning | 1. Get compatibility warning<br>2. Click "Yes" | Print continues despite warning | ☐ |
| PRINT-018 | Cancel Due to Warning | 1. Get compatibility warning<br>2. Click "No" | Print is cancelled | ☐ |
| PRINT-019 | Compatibility Disabled | 1. Disable compatibility check<br>2. Print incompatible file | No warnings shown | ☐ |

---

## 6. Calibrate Screen Tests

### 6.1 Main Calibration Menu Tests

| Test ID | Test Case | Steps | Expected Result | Status |
|---------|-----------|-------|-----------------|---------|
| CAL-001 | Bed Leveling Access | Click bed leveling button | Navigates to bed leveling wizard | ☐ |
| CAL-002 | Nozzle Offset Access | Click nozzle offset button | Navigates to nozzle offset screen | ☐ |
| CAL-003 | Tool Offset Z Access | Click tool offset Z button | Navigates to Z offset calibration | ☐ |
| CAL-004 | Tool Offset XY Access | Click tool offset XY button | Navigates to XY offset calibration | ☐ |
| CAL-005 | IDEX Calibration Access | Click IDEX calibration button | Navigates to IDEX calibration wizard | ☐ |
| CAL-006 | Input Shaper | Click input shaper button | Starts input shaper calibration | ☐ |
| CAL-007 | Back to Menu | Click back button | Returns to main menu screen | ☐ |

### 6.2 Bed Leveling Wizard Tests

| Test ID | Test Case | Steps | Expected Result | Status |
|---------|-----------|-------|-----------------|---------|
| CAL-008 | Wizard Start | Enter bed leveling wizard | Heaters turn on, axes home, shows step 1 | ☐ |
| CAL-009 | Step 1 Completion | Click next on step 1 | Moves to first calibration point | ☐ |
| CAL-010 | Step 2 - First Point | At first point, click next | Moves to second calibration point | ☐ |
| CAL-011 | Step 3 - Second Point | At second point, click next | Moves to third calibration point | ☐ |
| CAL-012 | Step 4 - Third Point | At third point, click next | Moves to nozzle height calibration | ☐ |
| CAL-013 | Single Nozzle Skip | On single nozzle printer | Skips nozzle height, goes to completion | ☐ |
| CAL-014 | Dual Nozzle T0 | On dual nozzle, nozzle height step | Shows T0 height adjustment controls | ☐ |
| CAL-015 | Dual Nozzle T1 | Complete T0, proceed | Shows T1 height adjustment controls | ☐ |
| CAL-016 | Z Adjustment Controls | Use Z+ and Z- buttons | Bed moves up/down by 0.025mm increments | ☐ |
| CAL-017 | Calibration Completion | Click done after calibration | Returns to calibrate menu, saves settings | ☐ |
| CAL-018 | Cancel Calibration | Click cancel at any step | Safely returns to menu, homes axes, cools down | ☐ |
| CAL-019 | GIF Animations | During calibration steps | Instructional GIFs play correctly | ☐ |

### 6.3 IDEX Calibration Tests (Dual Nozzle Only)

| Test ID | Test Case | Steps | Expected Result | Status |
|---------|-----------|-------|-----------------|---------|
| CAL-020 | IDEX Step 1 | Start IDEX calibration | Heaters turn on, shows welcome step | ☐ |
| CAL-021 | IDEX Step 2 | Proceed to step 2 | Moves to first calibration position | ☐ |
| CAL-022 | IDEX Step 3 | Proceed to step 3 | Moves to second calibration position | ☐ |
| CAL-023 | IDEX Step 4 | Proceed to step 4 | Moves to third calibration position | ☐ |
| CAL-024 | IDEX Step 5 | Proceed to step 5 | Final positioning and calibration | ☐ |
| CAL-025 | IDEX Completion | Complete IDEX calibration | Saves offset values, returns to menu | ☐ |
| CAL-026 | IDEX Cancel | Cancel at any step | Homes axes, cools down, returns safely | ☐ |
| CAL-027 | IDEX GIFs | Throughout IDEX process | All instructional GIFs display correctly | ☐ |

### 6.4 Offset Calibration Tests

| Test ID | Test Case | Steps | Expected Result | Status |
|---------|-----------|-------|-----------------|---------|
| CAL-028 | Z Offset Entry | Enter Z offset values manually | Values are accepted and applied | ☐ |
| CAL-029 | XY Offset Entry | Enter XY offset values manually | Values are accepted and applied | ☐ |
| CAL-030 | Invalid Offset Values | Enter extreme/invalid values | System prevents invalid entries | ☐ |
| CAL-031 | Offset Application | Apply new offset values | Changes take effect immediately | ☐ |

---

## 7. Filament Management Screen Tests

### 7.1 Material Bay Tests

| Test ID | Test Case | Steps | Expected Result | Status |
|---------|-----------|-------|-----------------|---------|
| FIL-001 | T0 Material Change | Click T0 material change button | Opens filament change wizard for T0 | ☐ |
| FIL-002 | T1 Material Change | Click T1 material change button | Opens filament change wizard for T1 | ☐ |
| FIL-003 | Material State Display | Check material indicators | Current material types display correctly | ☐ |
| FIL-004 | Color Indicators | Check status colors | Color indicators show correct states | ☐ |
| FIL-005 | Edit Material T0 | Click edit button for T0 | Opens material selection dialog | ☐ |
| FIL-006 | Edit Material T1 | Click edit button for T1 | Opens material selection dialog | ☐ |

### 7.2 Nozzle Change Tests

| Test ID | Test Case | Steps | Expected Result | Status |
|---------|-----------|-------|-----------------|---------|
| FIL-007 | T0 Nozzle Change | Click T0 nozzle change button | Opens nozzle change wizard for T0 | ☐ |
| FIL-008 | T1 Nozzle Change | Click T1 nozzle change button | Opens nozzle change wizard for T1 | ☐ |
| FIL-009 | Current Nozzle Display | Check nozzle size display | Current nozzle sizes show correctly | ☐ |

### 7.3 Change Filament Wizard Tests

| Test ID | Test Case | Steps | Expected Result | Status |
|---------|-----------|-------|-----------------|---------|
| FIL-010 | Filament Heating | Start filament change | Nozzle heats to appropriate temperature | ☐ |
| FIL-011 | Filament Unload | Proceed through unload steps | Old filament unloads correctly | ☐ |
| FIL-012 | Filament Load | Insert new filament, proceed | New filament loads correctly | ☐ |
| FIL-013 | Filament Purge | Complete loading process | Purges old material, confirms new color | ☐ |
| FIL-014 | Color Change Process | Change filament color | Properly purges until color change complete | ☐ |
| FIL-015 | Wizard Cancel | Cancel wizard at various stages | Safely cancels and cools down | ☐ |
| FIL-016 | Emergency Stop | Use emergency stop during change | Immediately stops all movement and heating | ☐ |

### 7.4 Nozzle Change Wizard Tests

| Test ID | Test Case | Steps | Expected Result | Status |
|---------|-----------|-------|-----------------|---------|
| FIL-017 | Safety Instructions | Start nozzle change wizard | Displays safety warnings clearly | ☐ |
| FIL-018 | Heating for Removal | Proceed through heating step | Heats to appropriate removal temperature | ☐ |
| FIL-019 | Cool Down Step | After removal heating | Cools down for safe handling | ☐ |
| FIL-020 | Installation Steps | Follow installation guide | Clear step-by-step instructions | ☐ |
| FIL-021 | Size Verification | Complete nozzle change | Prompts for/detects new nozzle size | ☐ |
| FIL-022 | Configuration Update | Confirm new nozzle size | Updates printer configuration accordingly | ☐ |

---

## 8. Settings Screen Tests

### 8.1 Main Settings Menu Tests

| Test ID | Test Case | Steps | Expected Result | Status |
|---------|-----------|-------|-----------------|---------|
| SET-001 | Network Settings Access | Click network settings | Opens network configuration screen | ☐ |
| SET-002 | Software Update Access | Click software update | Opens update interface | ☐ |
| SET-003 | Printer Setup Access | Click printer setup | Opens printer type selection | ☐ |
| SET-004 | Restore Print Settings | Click restore print settings | Restores print-related preferences | ☐ |
| SET-005 | Factory Defaults | Click factory defaults | Shows confirmation dialog | ☐ |
| SET-006 | System Restart | Click restart | Shows restart confirmation dialog | ☐ |
| SET-007 | Settings Back | Click back button | Returns to main menu screen | ☐ |

### 8.2 Network Settings Tests

| Test ID | Test Case | Steps | Expected Result | Status |
|---------|-----------|-------|-----------------|---------|
| SET-008 | WiFi Network List | Open network settings | Displays available WiFi networks | ☐ |
| SET-009 | WiFi Connection | 1. Select network<br>2. Enter password<br>3. Connect | Successfully connects to WiFi | ☐ |
| SET-010 | WiFi Disconnection | Disconnect from current network | Successfully disconnects | ☐ |
| SET-011 | Ethernet Status | Check wired connection | Shows ethernet connection status | ☐ |
| SET-012 | IP Address Display | Check network info | Displays current IP address correctly | ☐ |
| SET-013 | Network Keyboard | Enter WiFi password | On-screen keyboard works properly | ☐ |

### 8.3 Software Update Tests

| Test ID | Test Case | Steps | Expected Result | Status |
|---------|-----------|-------|-----------------|---------|
| SET-014 | Check for Updates | Click check updates button | Queries server for available updates | ☐ |
| SET-015 | Available Updates List | When updates available | Lists all available updates clearly | ☐ |
| SET-016 | Update Installation | Install available update | Update downloads and installs correctly | ☐ |
| SET-017 | Update Progress | During update process | Progress bar and status update correctly | ☐ |
| SET-018 | Update Log Display | During/after update | Update log displays detailed information | ☐ |
| SET-019 | Update Failure Handling | Simulate update failure | Handles failures gracefully with error info | ☐ |
| SET-020 | Update Success | Successful update completion | Shows success message and prompts restart | ☐ |

### 8.4 Printer Setup Tests

| Test ID | Test Case | Steps | Expected Result | Status |
|---------|-----------|-------|-----------------|---------|
| SET-021 | Printer Model List | Open printer setup | Displays available printer models | ☐ |
| SET-022 | Current Printer Highlight | Check current selection | Current printer model is highlighted | ☐ |
| SET-023 | Printer Model Selection | Select different printer model | Selection updates correctly | ☐ |
| SET-024 | Configuration Application | Apply new printer config | Configuration changes are applied | ☐ |
| SET-025 | Firmware Compatibility | Check firmware status | Verifies firmware compatibility | ☐ |
| SET-026 | Cancel Printer Change | Cancel configuration change | Returns without applying changes | ☐ |

---

## 9. Sensor & Safety Tests

### 9.1 Filament Sensor Tests

| Test ID | Test Case | Steps | Expected Result | Status |
|---------|-----------|-------|-----------------|---------|
| SENS-001 | T0 Runout Detection | 1. Enable runout sensor<br>2. Start print<br>3. Remove T0 filament | Sensor triggers, print pauses | ☐ |
| SENS-002 | T1 Runout Detection | 1. Enable runout sensor<br>2. Start print<br>3. Remove T1 filament | Sensor triggers, print pauses | ☐ |
| SENS-003 | T0 Jam Detection | 1. Enable jam sensor<br>2. Start print<br>3. Simulate jam on T0 | Sensor triggers, print pauses | ☐ |
| SENS-004 | T1 Jam Detection | 1. Enable jam sensor<br>2. Start print<br>3. Simulate jam on T1 | Sensor triggers, print pauses | ☐ |
| SENS-005 | Sensor Enable/Disable | Toggle sensors on/off | Sensors only active when enabled and printing | ☐ |
| SENS-006 | Sensor Persistence | Restart application | Sensor preferences persist across restarts | ☐ |
| SENS-007 | No Print State | Remove filament when not printing | Sensors don't trigger when not printing | ☐ |

### 9.2 Print Restore Tests

| Test ID | Test Case | Steps | Expected Result | Status |
|---------|-----------|-------|-----------------|---------|
| SENS-008 | Power Failure Simulation | 1. Start print<br>2. Cut power during print | System saves print state | ☐ |
| SENS-009 | Restore Dialog | Restart after power failure | Shows print restore dialog | ☐ |
| SENS-010 | Accept Restore | Click "Yes" on restore dialog | Print resumes from saved position | ☐ |
| SENS-011 | Decline Restore | Click "No" on restore dialog | Print is cleared, no restoration | ☐ |
| SENS-012 | Auto Resume Enable | Enable auto-resume setting | Automatic restoration without dialog | ☐ |
| SENS-013 | Settings Sync | Change settings in OctoPrint web | TouchUI reflects OctoPrint settings | ☐ |

### 9.3 Error Handling Tests

| Test ID | Test Case | Steps | Expected Result | Status |
|---------|-----------|-------|-----------------|---------|
| SENS-014 | Printer Error Dialog | Trigger printer firmware error | Error dialog appears with error message | ☐ |
| SENS-015 | Emergency Stop | Press emergency stop (if available) | All motion and heating stops immediately | ☐ |
| SENS-016 | Temperature Fault | Disconnect temperature sensor | Temperature fault detected and reported | ☐ |
| SENS-017 | Probing Failed | Simulate Z-probe failure | Probing failure detected during bed leveling | ☐ |
| SENS-018 | Communication Loss | Disconnect OctoPrint during operation | Communication loss detected and handled | ☐ |
| SENS-019 | Recovery Actions | After various errors | Recovery options work correctly | ☐ |

---

## 10. Door Lock & Security Tests

### 10.1 Door Lock Tests

| Test ID | Test Case | Steps | Expected Result | Status |
|---------|-----------|-------|-----------------|---------|
| DOOR-001 | Lock Toggle | Click door lock button | Door physically locks/unlocks | ☐ |
| DOOR-002 | Lock Status Display | Check lock indicator | Lock status displays correctly on UI | ☐ |
| DOOR-003 | Lock During Print | Lock/unlock during active print | Door lock operates during printing | ☐ |
| DOOR-004 | Safety Operation | Test lock mechanism | Door lock provides intended safety function | ☐ |

---

## 11. Keyboard & Input Tests

### 11.1 On-Screen Keyboard Tests

| Test ID | Test Case | Steps | Expected Result | Status |
|---------|-----------|-------|-----------------|---------|
| KEY-001 | Alphabetic Input | Type alphabetic characters | Characters appear in text field | ☐ |
| KEY-002 | Numeric Input | Type numeric characters | Numbers appear in text field | ☐ |
| KEY-003 | Special Characters | Type special characters | Special chars appear correctly | ☐ |
| KEY-004 | Case Switching | Toggle upper/lowercase | Case changes affect typed characters | ☐ |
| KEY-005 | Backspace Function | Use backspace key | Characters delete from cursor position | ☐ |
| KEY-006 | Cursor Movement | Use cursor left/right | Cursor moves within text field | ☐ |
| KEY-007 | Clear Text | Clear entire text field | All text is removed | ☐ |
| KEY-008 | Enter/Confirm | Confirm text input | Input is accepted and keyboard closes | ☐ |

---

## 12. Performance & Stress Tests

### 12.1 Long Running Tests

| Test ID | Test Case | Steps | Expected Result | Status |
|---------|-----------|-------|-----------------|---------|
| PERF-001 | Extended Print | Run 24+ hour print | UI remains stable throughout | ☐ |
| PERF-002 | Multiple Heat Cycles | Perform 50+ heat/cool cycles | No memory leaks or crashes | ☐ |
| PERF-003 | Continuous Operation | Run printer for 1 week | System maintains stability | ☐ |
| PERF-004 | Memory Usage | Monitor during long operations | Memory usage remains reasonable | ☐ |

### 12.2 Network Tests

| Test ID | Test Case | Steps | Expected Result | Status |
|---------|-----------|-------|-----------------|---------|
| PERF-005 | Network Disconnection | Disconnect network during operation | Graceful handling of network loss | ☐ |
| PERF-006 | Network Reconnection | Reconnect after disconnection | Automatic recovery when network returns | ☐ |
| PERF-007 | Slow Network | Test with slow/unstable connection | UI remains responsive | ☐ |
| PERF-008 | High Latency | Test with high network latency | Acceptable response times maintained | ☐ |

### 12.3 Edge Case Tests

| Test ID | Test Case | Steps | Expected Result | Status |
|---------|-----------|-------|-----------------|---------|
| PERF-009 | Rapid Button Clicking | Rapidly click various buttons | No race conditions or crashes | ☐ |
| PERF-010 | Simultaneous Operations | Try multiple operations at once | System handles concurrent operations | ☐ |
| PERF-011 | Invalid Input Values | Enter invalid data in fields | Proper validation and error messages | ☐ |
| PERF-012 | Storage Full | Fill storage completely | Graceful handling of storage limitations | ☐ |
| PERF-013 | Large File Handling | Load very large G-code files (>100MB) | System handles large files without issues | ☐ |

---

## Test Completion Summary

### Overall Test Results

| Category | Total Tests | Passed | Failed | Skipped |
|----------|------------|--------|--------|---------|
| Startup & Loading | 6 | | | |
| Home Screen | 28 | | | |
| Menu Screen | 10 | | | |
| Control Screen | 34 | | | |
| Print Location | 19 | | | |
| Calibrate Screen | 31 | | | |
| Filament Management | 22 | | | |
| Settings Screen | 26 | | | |
| Sensor & Safety | 19 | | | |
| Door Lock | 4 | | | |
| Keyboard & Input | 8 | | | |
| Performance & Stress | 13 | | | |
| **TOTAL** | **220** | | | |

### Test Environment Details

| Item | Details |
|------|---------|
| Test Date | |
| Tester Name | |
| Software Version | |
| Hardware Model | |
| Network Configuration | |
| OctoPrint Version | |
| Klipper Version | |

### Known Issues & Limitations

Document any known issues discovered during testing:

1. **Issue #1**: [Description]
   - Severity: [High/Medium/Low]
   - Workaround: [If available]

2. **Issue #2**: [Description]
   - Severity: [High/Medium/Low]
   - Workaround: [If available]

### Recommendations

Based on testing results, provide recommendations for:
- Critical fixes needed before release
- Performance improvements
- User experience enhancements
- Additional testing requirements

---

## Appendix

### A. Log File Locations
- Application logs: `/logs/`
- OctoPrint logs: `/home/pi/.octoprint/logs/`
- System logs: `/var/log/`

### B. Configuration Files
- Printer configurations: `/firmware/`
- Application config: `/config/`
- User preferences: Stored in printer model

### C. Test Data Files
- Sample G-code files with various configurations
- Test thumbnails and metadata
- Network configuration test cases

### D. Emergency Procedures
- Emergency stop procedures
- Safe shutdown process
- Recovery from critical errors

---

*This document should be updated with each software release to reflect new features and functionality.*
