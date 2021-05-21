#!/usr/bin/env python3
# Copyright 2021 Canonical
# See LICENSE file for licensing details.
#
# Learn more at: https://juju.is/docs/sdk

"""Charm the service.

Refer to the following post for a quick-start guide that will help you
develop a new k8s charm using the Operator Framework:

    https://discourse.charmhub.io/t/4208
"""

import logging
import os
from pathlib import Path
from subprocess import CalledProcessError, check_call, check_output

from git import Repo
from jinja2 import Template
from ops.charm import CharmBase
from ops.framework import StoredState
from ops.main import main
from ops.model import ActiveStatus, BlockedStatus, MaintenanceStatus

logger = logging.getLogger(__name__)

APP_PATH = Path("/srv/app")
VENV_ROOT = Path("/srv/app/venv")
REPO = "https://github.com/juju/hello-juju"


class HelloJujuCharm(CharmBase):
    """Charm the service."""

    _stored = StoredState()

    def __init__(self, *args):
        super().__init__(*args)
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.start, self._on_start)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self._stored.set_default(things=[])

    def _on_install(self, event):
        """Install prerequisites for the application"""
        # Install some Python packages using apt
        self.unit.status = MaintenanceStatus("installing pip and virtualenv")
        self._install_apt_packages(["python3-pip", "python3-virtualenv"])

        # Fetch the code using git
        self.unit.status = MaintenanceStatus("fetching application code")
        Repo.clone_from(REPO, APP_PATH)

        # Install application dependencies
        check_output(["python3", "-m", "virtualenv", VENV_ROOT])
        check_output([f"{VENV_ROOT}/bin/pip3", "install", "gunicorn"])
        check_output([f"{VENV_ROOT}/bin/pip3", "install", "-r", f"{APP_PATH}/requirements.txt"])

        # Create the database
        self._create_database_tables()

        # Template out the systemd service file
        self._render_systemd_unit()
        check_call(["systemctl", "enable", "hello-juju"])

    def _on_start(self, event):
        """Start the workload"""
        check_call(["systemctl", "start", "hello-juju"])
        self.unit.status = ActiveStatus()

    def _on_config_changed(self, _):
        """Just an example to show how to deal with changed configuration.

        Learn more about config at https://juju.is/docs/sdk/config
        """
        self.unit.status = ActiveStatus()

    def _install_apt_packages(self, packages: list):
        """Simple wrapper around 'apt-get install -y"""
        try:
            logger.debug("updating apt cache")
            check_output(["apt-get", "update"])
            logger.debug("installing apt packages: %s", ", ".join(packages))
            check_output(["apt-get", "install", "-y"] + packages)
        except CalledProcessError as e:
            logger.error("failed to install packages: %s", ", ".join(packages))
            logger.debug("apt error: %s", e.output)
            self.unit.status = BlockedStatus("Failed to install packages")

    def _render_systemd_unit(self):
        """Render the systemd unit for Gunicorn to a file"""
        # Open the template systemd unit file
        with open("templates/hello-juju.service.j2", "r") as t:
            template = Template(t.read())
        # Render the template files with the correct values
        rendered = template.render(
            port=self.config["port"], project_root=APP_PATH, user="www-data", group="www-data"
        )
        # Write the rendered file out to disk
        with open("/etc/systemd/system/hello-juju.service", "w+") as t:
            t.write(rendered)

        # Ensure correct permissions are set on the service
        os.chmod("/etc/systemd/system/hello-juju.service", 0o755)

    def _create_database_tables(self):
        """Initialise the database and populate with initial tables required"""
        self.unit.status = MaintenanceStatus("creating database tables")
        check_call(["sudo", "-u", "www-data", f"{VENV_ROOT}/bin/python3", f"{APP_PATH}/init.py"])


if __name__ == "__main__":
    main(HelloJujuCharm)
