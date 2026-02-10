$(function() {
    function VM_PenroseControlCenter_navbar(parameters) {
        var self = this;

        self.Config = undefined;
        self.VM_settings = parameters[0];

        // Tower Light observables
        self.towerEnabled = ko.observable(false);

        // Door Lock observables
        self.doorLockEnabled = ko.observable(false);
        self.doorState = ko.observable("unlocked");

        // Computed properties for door state display
        self.doorStateCss = ko.computed(function() {
            return self.doorState() === "locked" ? "door-locked" : "door-unlocked";
        });

        self.doorIconCss = ko.computed(function() {
            return self.doorState() === "locked" ? "fa fa-lock" : "fa fa-unlock";
        });

        self.onBeforeBinding = function() {
            console.log('Binding VM_PenroseControlCenter_navbar');

            self.Config = self.VM_settings.settings.plugins.PenroseControlCenter;

            // Tower Light subscriptions - handle both string and number values
            self.Config.tower_enabled.subscribe(function(value) {
                self.towerEnabled(value == 1 || value === "1" || value === true);
            });
            self.towerEnabled(self.Config.tower_enabled() == 1 || self.Config.tower_enabled() === "1" || self.Config.tower_enabled() === true);

            // Door Lock subscriptions - handle both string and number values
            self.Config.door_lock_enabled.subscribe(function(value) {
                self.doorLockEnabled(value == 1 || value === "1" || value === true);
            });
            self.doorLockEnabled(self.Config.door_lock_enabled() == 1 || self.Config.door_lock_enabled() === "1" || self.Config.door_lock_enabled() === true);
        };

        self.onDataUpdaterPluginMessage = function(plugin, data) {
            if (plugin != "PenroseControlCenter") {
                return;
            }

            if (data.type == "machine_state") {
                var led = $("#machine_state");
                led.removeClass();

                if (!self.Config.tower_enabled()) {
                    led.hide();
                    return;
                } else {
                    led.show();
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
        VM_PenroseControlCenter_navbar,
        ["settingsViewModel"],
        ["#navbar_PenroseControlCenter"]
    ]);
});
