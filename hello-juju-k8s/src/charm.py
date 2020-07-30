#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
# Copyright © 2020 Tim McNamara tsm@canonical.com

"""Operator Charm main library."""
# Load modules from lib directory
import logging

import setuppath  # noqa:F401
from ops.charm import CharmBase
from ops.framework import StoredState
from ops.main import main
from ops.model import ActiveStatus, MaintenanceStatus


class HelloJujuCharm(CharmBase):
    """Class reprisenting this Operator charm."""

    state = StoredState()

    def __init__(self, *args):
        """Initialize charm and configure states and events to observe."""
        super().__init__(*args)
        # -- standard hook observation
        # self.framework.observe(self.on.install, self.on_install)
        self.framework.observe(self.on.start, self.on_start)
        # self.framework.observe(self.on.config_changed, self.on_config_changed)
        # # -- initialize states --
        # self.state.set_default(installed=False)
        # self.state.set_default(configured=False)
        # self.state.set_default(started=False)

    def _make_pod_spec(self):
        spec = {
            "containers": [{
                "name": self.framework.model.app.name,
                "image": "hello-juju:latest",
                "ports": [
                    {"name": "hello-juju", "containerPort": 8000, "protocol": "TCP"}
                ],
            }],
        }

        return spec

    def apply_pod_spec(self):
        # Only apply the spec if this unit is a leader
        if not self.framework.model.unit.is_leader():
            return
        spec = self._make_pod_spec()
        self.framework.model.pod.set_spec(spec)
        self.state.spec = spec

    # def on_install(self, event):
    #     """Handle install state."""
    #     self.unit.status = MaintenanceStatus("Installing charm software")
    #     # Perform install tasks
    #     self.unit.status = MaintenanceStatus("Install complete")
    #     logging.info("Install of software complete")
    #     self.state.installed = True

    # def on_config_changed(self, event):
    #     """Handle config changed."""

    #     if not self.state.installed:
    #         logging.warning("Config changed called before install complete, deferring event: {}.".format(event.handle))
    #         self._defer_once(event)

    #         return

    #     if self.state.started:
    #         # Stop if necessary for reconfig
    #         logging.info("Stopping for configuration, event handle: {}".format(event.handle))
    #     # Configure the software
    #     logging.info("Configuring")
    #     self.state.configured = True

    def on_start(self, event):
        """Handle start state."""
        self.unit.status = MaintenanceStatus("Starting charm software")
        self.apply_pod_spec()
        self.unit.status = ActiveStatus("Unit is ready")
        # self.state.started = True
        # logging.info("Started")

    # def _defer_once(self, event):
    #     """Defer the given event, but only once."""
    #     notice_count = 0
    #     handle = str(event.handle)

    #     for event_path, _, _ in self.framework._storage.notices(None):
    #         if event_path.startswith(handle.split('[')[0]):
    #             notice_count += 1
    #             logging.debug("Found event: {} x {}".format(event_path, notice_count))

    #     if notice_count > 1:
    #         logging.debug("Not deferring {} notice count of {}".format(handle, notice_count))
    #     else:
    #         logging.debug("Deferring {} notice count of {}".format(handle, notice_count))
    #         event.defer()

    # # -- Example relation interface for MySQL, not observed by default:
    # def on_db_relation_changed(self, event):
    #     """Handle an example db relation's change event."""
    #     self.password = event.relation.data[event.unit].get("password")
    #     self.unit.status = MaintenanceStatus("Configuring database")
    #     if self.mysql.is_ready:
    #         event.log("Database relation complete")
    #     self.state._db_configured = True

    # def on_example_action(self, event):
    #     """Handle the example_action action."""
    #     event.log("Hello from the example action.")
    #     event.set_results({"success": "true"})


if __name__ == "__main__":
    from ops.main import main
    main(HelloJujuCharm)
