$(function() {
    function VM_PenroseControlCenter_settings(parameters) {
        var self = this;

        self.Config = undefined;
        self.VM_settings = parameters[0];

        // Tower Light observables
        self.towerEnabled = ko.observable(false);
        self.strobeEnabled = ko.observable(false);

        // Door Lock observables
        self.doorLockEnabled = ko.observable(false);
        self.doorState = ko.observable("unlocked");

        // Computed properties for door state display
        self.doorStateText = ko.computed(function() {
            return self.doorState() === "locked" ? "Locked" : "Unlocked";
        });

        self.doorStateCss = ko.computed(function() {
            return self.doorState() === "locked" ? "label-warning" : "label-success";
        });

        // Helper function to check enabled state (handles string/number/boolean)
        var isEnabled = function(value) {
            return value == 1 || value === "1" || value === true;
        };

        self.onBeforeBinding = function() {
            console.log('Binding VM_PenroseControlCenter_settings');

            self.Config = self.VM_settings.settings.plugins.PenroseControlCenter;

            // Tower Light subscriptions
            self.Config.tower_enabled.subscribe(function(value) {
                self.towerEnabled(isEnabled(value));
            });
            self.Config.strobe.subscribe(function(value) {
                self.strobeEnabled(isEnabled(value));
            });

            // Door Lock subscriptions
            self.Config.door_lock_enabled.subscribe(function(value) {
                self.doorLockEnabled(isEnabled(value));
            });
        };

        self.onSettingsShown = function() {
            self.towerEnabled(isEnabled(self.Config.tower_enabled()));
            self.strobeEnabled(isEnabled(self.Config.strobe()));
            self.doorLockEnabled(isEnabled(self.Config.door_lock_enabled()));

            // Fetch current door status
            $.ajax({
                url: API_BASEURL + "plugin/PenroseControlCenter/door_status",
                type: "GET",
                dataType: "json",
                success: function(data) {
                    self.doorState(data.door_state);
                }
            });
        };

        self.toggleDoorLock = function() {
            $.ajax({
                url: API_BASEURL + "plugin/PenroseControlCenter/lock_override",
                type: "GET",
                success: function() {
                    // State will be updated via plugin message
                }
            });
        };

        self.onDataUpdaterPluginMessage = function(plugin, data) {
            if (plugin != "PenroseControlCenter") {
                return;
            }

            if (data.type == "machine_state") {
                var led = $("#settings_machine_state");
                led.removeClass();

                if (!self.Config.tower_enabled()) {
                    return;
                }

                if (!data.machine_state)
                    return;
                led.addClass(data.machine_state);
            } else if (data.type == "door_state") {
                self.doorState(data.door_state);
            } else {
                console.log(data);
            }
        };
    }

    // Register the plugin with OctoPrint
    OCTOPRINT_VIEWMODELS.push([
        VM_PenroseControlCenter_settings,
        ["settingsViewModel"],
        ["#settings_PenroseControlCenter"]
    ]);
});
