# PyQt 3D Printer Application

This project is a PyQt application designed for controlling a 3D printer via a touchscreen interface. It connects to an OctoPrint instance using the OctoPrint client API, providing an intuitive user experience for managing print jobs and monitoring printer status.

## Features

- Touchscreen-friendly interface for easy navigation and control.
- Start, stop, and pause print jobs directly from the application.
- Real-time monitoring of printer status, including progress and current state.
- Integration with OctoPrint API for seamless communication with the 3D printer.

## Project Structure

```
pyqt-3d-printer-app
├── octoprint_PenroseControlCenter
│   ├── main.py                # Entry point of the application
│   ├── ui
│   │   ├── main_window        # Main window directory
│   │   │   ├── main_window.py # Main user interface definition
│   │   │   └── main_window.ui # Main window UI file
│   │   ├── home_screen        # Home screen directory
│   │   │   ├── home_screen.py # Home screen UI
│   │   │   └── home_screen.ui # Home screen UI file
│   │   ├── loading_screen     # Loading screen directory
│   │   │   ├── loading_screen.py # Loading screen UI
│   │   │   └── loading_screen.ui # Loading screen UI file
│   │   ├── settings_screen    # Settings screen directory
│   │   │   ├── __init__.py    # Package marker for settings_screen
│   │   │   ├── settings_screen.py # Settings screen UI logic
│   │   │   ├── settings_screen.ui # Settings screen UI file
│   │   │   ├── general        # General settings directory
│   │   │   │   ├── general.py # General settings UI
│   │   │   │   └── general.ui # General settings UI file
│   │   │   ├── network        # Network settings directory
│   │   │   │   ├── network.py # Network settings UI
│   │   │   │   └── network.ui # Network settings UI file
│   │   │   └── advanced       # Advanced settings directory
│   │   │       ├── advanced.py # Advanced settings UI
│   │   │       └── advanced.ui # Advanced settings UI file
│   │   └── resources
│   │       └── resource_rc.py # Resource file
│   ├── octoprint_client
│   │   ├── __init__.py        # Package marker for octoprint_client
│   │   └── client.py          # OctoPrint API client
│   ├── models
│   │   └── printer_status.py  # Printer status representation
│   └── utils
│       └── helpers.py         # Utility functions
├── requirements.txt           # Project dependencies
└── README.md                  # Project documentation
```

## Setup Instructions

1. Clone the repository:
   ```
   git clone <repository-url>
   cd pyqt-3d-printer-app
   ```

2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Run the application:
   ```
   python octoprint_PenroseControlCenter/main.py
   ```

## Usage

- Launch the application on your Raspberry Pi with a touchscreen.
- Use the main interface to control your 3D printer.
- Monitor the printer's status and progress in real-time.

## Code Flow and Architecture

The architecture used in this code is closest to the Model-View-Presenter (MVP) pattern. Here's a brief explanation of why this is the case:

### Model-View-Presenter (MVP)

- **Model**: Represents the data and business logic of the application. In this case, it would be the classes and modules that handle the data and interactions with the OctoPrint API (e.g., `octoprint_client`, `models`).
- **View**: Represents the UI components. In this case, it is the `.ui` files created using Qt Designer and the corresponding PyQt widgets (e.g., `settings_screen.ui`, `example_widget.ui`).
- **Presenter**: Acts as an intermediary between the Model and the View. It retrieves data from the Model, formats it, and updates the View. In this case, it is the Python classes that load the UI files and handle the logic (e.g., `SettingsScreen`, `ExampleWidget`).

### Why MVP?

- **Separation of Concerns**: The UI (View) is separated from the business logic (Model), and the Presenter handles the communication between them.
- **Dynamic Loading**: The `SettingsScreen` class dynamically loads different settings widgets, which is a typical responsibility of the Presenter in the MVP pattern.
- **UI Logic in Presenter**: The logic for handling UI events (e.g., button clicks) and updating the UI is placed in the Presenter classes (`SettingsScreen`, `ExampleWidget`), which is characteristic of the MVP pattern.

### Main Components

1. **Main Window**: The main entry point of the application. It initializes the main window and sets up the UI.
   - `main_window.py`: Contains the logic for the main window.
   - `main_window.ui`: The UI file for the main window.

2. **Home Screen**: The initial screen displayed to the user. It provides options to start, stop, and pause print jobs.
   - `home_screen.py`: Contains the logic for the home screen.
   - `home_screen.ui`: The UI file for the home screen.

3. **Loading Screen**: A screen displayed while the application is loading or performing background tasks.
   - `loading_screen.py`: Contains the logic for the loading screen.
   - `loading_screen.ui`: The UI file for the loading screen.

4. **Settings Screen**: A screen for configuring various settings of the application.
   - `settings_screen.py`: Contains the logic for the settings screen.
   - `settings_screen.ui`: The UI file for the settings screen.
   - **General Settings**: General application settings.
     - `general.py`: Contains the logic for general settings.
     - `general.ui`: The UI file for general settings.
   - **Network Settings**: Network-related settings.
     - `network.py`: Contains the logic for network settings.
     - `network.ui`: The UI file for network settings.
   - **Advanced Settings**: Advanced configuration options.
     - `advanced.py`: Contains the logic for advanced settings.
     - `advanced.ui`: The UI file for advanced settings.

5. **OctoPrint Client**: Handles communication with the OctoPrint API.
   - `client.py`: Contains the logic for interacting with the OctoPrint API.

6. **Models**: Represents the data structures used in the application.
   - `printer_status.py`: Represents the status of the printer.

7. **Utilities**: Contains helper functions used throughout the application.
   - `helpers.py`: Utility functions.

### Application Flow

1. **Initialization**: The application starts by running `main.py`, which initializes the main window.
2. **Loading Screen**: The loading screen is displayed while the application initializes and connects to the OctoPrint instance.
3. **Home Screen**: Once initialization is complete, the home screen is displayed. The user can start, stop, and pause print jobs from this screen.
4. **Settings Screen**: The user can navigate to the settings screen to configure various settings. The settings screen dynamically loads different settings widgets based on the user's selection.
5. **OctoPrint Communication**: The `octoprint_client` handles communication with the OctoPrint API, sending commands and receiving status updates.
6. **Real-time Monitoring**: The application continuously monitors the printer's status and updates the UI in real-time.

## Adding New Settings Widgets

The application supports dynamically loading new settings widgets. To add a new settings widget, follow these steps:

1. Create a new subfolder in the `settings_screen` directory with the name of the widget.
2. Create the `.ui` file using Qt Designer and save it in the subfolder.
3. Create the `.py` file with the backend logic and save it in the subfolder.
4. Ensure the class name in the `.py` file matches the widget name in title case with underscores removed.
5. The new widget will be dynamically loaded and integrated into the main settings screen.

For more details, refer to the [Settings Screen README](octoprint_PenroseControlCenter/ui/settings_screen/README.md).

## Contributing

Contributions are welcome! Please open an issue or submit a pull request for any enhancements or bug fixes.

## Developing

- Download QT Designer from: [QT Designer Download](https://build-system.fman.io/qt-designer-download)
- You can refer to the readme file at [Julia-Touch-UI-Documentation](https://github.com/FracktalWorks/Julia-Touch-UI-Documentation). For this project, I'm using VSCode and Copilot to develop, so taking a slightly different approach to the toolchain.
- Refer to this to understand how to properly use images inside a QT project: [text](https://www.youtube.com/watch?v=LceWgvYSVkQ)
- Convert the resource file: `pyrcc5 -o octoprint_VolterraControlCenter/ui/resources/resource_rc.py octoprint_VolterraControlCenter/ui/resources/resource.qrc`
- https://stackoverflow.com/questions/26698628/mvc-design-with-qt-designer-and-pyqt-pyside MVC architecture example
- https://medium.com/@mark_huber/a-clean-architecture-for-a-pyqt-gui-using-the-mvp-pattern-78ecbc8321c0 MVC details
- https://developer.mantidproject.org/MVPTutorial/Introduction.html MVP tutorial
- https://developer.mantidproject.org/MVPTutorial/Presenter.html MVP Example
- https://developer.mantidproject.org/MVPTutorial/Mocking.html mocking/automatic testing

