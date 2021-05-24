#!/usr/bin/env python3
# Copyright 2021 Canonical
# See LICENSE file for licensing details.
#
# Learn more at: https://juju.is/docs/sdk

"""Hello, Juju example charm.

This charm is a demonstration of a machine charm written using the Charmed
Operator Framework. It deploys a simple Python Flask web application and
implements a relation to the PostgreSQL charm.
"""

import logging
import os
import pwd
import shutil
from pathlib import Path
from subprocess import CalledProcessError, check_call, check_output

import ops.lib
from git import Repo
from jinja2 import Template
from ops.charm import CharmBase
from ops.framework import StoredState
from ops.main import main
from ops.model import ActiveStatus, BlockedStatus, MaintenanceStatus

# See: https://github.com/canonical/ops-lib-pgsql
pgsql = ops.lib.use("pgsql", 1, "postgresql-charmers@lists.launchpad.net")

logger = logging.getLogger(__name__)

APP_PATH = Path("/srv/app")
VENV_ROOT = Path(f"{APP_PATH}/venv")


class HelloJujuCharm(CharmBase):
    """Main 'Hello, Juju' charm class"""

    _stored = StoredState()

    def __init__(self, *args):
        super().__init__(*args)
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.start, self._on_start)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self._stored.set_default(repo="", port="", conn_str="")

        # Initialise the PostgreSQL Client for the "db" relation
        self.db = pgsql.PostgreSQLClient(self, "db")
        self.framework.observe(
            self.db.on.database_relation_joined, self._on_database_relation_joined
        )
        self.framework.observe(self.db.on.master_changed, self._on_database_master_changed)

    def _on_install(self, _):
        """Install prerequisites for the application"""
        # Install some Python packages using apt
        self.unit.status = MaintenanceStatus("installing pip and virtualenv")
        self._install_apt_packages(["python3-pip", "python3-virtualenv"])
        # Clone application code and install dependencies, setup initial db
        self._setup_application()
        # Template out the systemd service file
        self._render_systemd_unit()
        # Enable the systemd unit that drives `hello-juju`
        check_call(["systemctl", "enable", "hello-juju"])

    def _on_start(self, _):
        """Start the workload"""
        check_call(["open-port", f"{self._stored.port}/TCP"])
        check_call(["systemctl", "start", "hello-juju"])
        self.unit.status = ActiveStatus()

    def _on_config_changed(self, _):
        """Handle changes to the application configuration"""
        restart = False

        # Check if the application repo has been changed
        if self.config["application-repo"] != self._stored.repo:
            logger.info("application repo changed, installing")
            self._stored.repo = self.config["application-repo"]
            self._setup_application()
            restart = True

        if self.config["port"] != self._stored.port:
            logger.info("port config changed, configuring")
            # Close the existing application port
            check_call(["close-port", f"{self._stored.port}/TCP"])
            # Reconfigure the systemd unit to specify the new port
            self._stored.port = self.config["port"]
            self._render_systemd_unit()
            # Ensure the correct port is opened for the application
            check_call(["open-port", f"{self._stored.port}/TCP"])
            restart = True

        if restart:
            logger.info("restarting hello-juju application")
            check_call(["systemctl", "restart", "hello-juju"])

        self.unit.status = ActiveStatus()

    def _on_database_relation_joined(self, event):
        """Handle the event where this application is joined with a database"""
        if self.unit.is_leader():
            # Ask the database to create a database with this app's name
            event.database = self.app.name
        elif event.database != self.app.name:
            # Application leader has not yet set requirements, defer this event
            # in case this unit becomes leader and needs to perform this op
            event.defer()
            return

    def _on_database_master_changed(self, event):
        """Handler the case where a new PostgreSQL DB master is available"""
        if event.database != self.app.name:
            # Leader has not yet set the database name/requirements.
            return

        # event.master will be none if the master database is unavailable,
        # or a pgsql.ConnectingString instance
        if event.master:
            self.unit.status = MaintenanceStatus("configuring database settings")
            # Store the connection uri in state
            self._stored.conn_str = event.master.uri
            # Render the settings file with the database connection details
            self._render_settings_file()
            # Ensure the database tables are created in the master
            self._create_database_tables()
            # Restart the service
            check_call(["systemctl", "restart", "hello-juju"])
            # Set back to active status
            self.unit.status = ActiveStatus()
        else:
            # Defer this event until the master is available
            event.defer()
            return

    def _setup_application(self):
        """Clone a Flask application into place and setup it's dependencies"""
        self.unit.status = MaintenanceStatus("fetching application code")

        # Delete the application directory if it exists already
        if Path(APP_PATH).is_dir():
            shutil.rmtree("/srv/app")

        # If this is the first time, set the repo in the stored state
        if not self._stored.repo:
            self._stored.repo = self.config["application-repo"]

        # Fetch the code using git
        Repo.clone_from(self._stored.repo, APP_PATH)

        # Install application dependencies
        check_output(["python3", "-m", "virtualenv", VENV_ROOT])
        check_output([f"{VENV_ROOT}/bin/pip3", "install", "gunicorn"])
        check_output([f"{VENV_ROOT}/bin/pip3", "install", "-r", f"{APP_PATH}/requirements.txt"])

        # If a connection string exists (and relation is defined) then
        # render the settings file for the new app with the connection details
        if self._stored.conn_str:
            self._render_settings_file()

        # Create required database tables
        self._create_database_tables()

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

        # If this is the first time, set the port in the stored state
        if not self._stored.port:
            self._stored.port = self.config["port"]

        # Render the template files with the correct values
        rendered = template.render(
            port=self._stored.port, project_root=APP_PATH, user="www-data", group="www-data"
        )
        # Write the rendered file out to disk
        with open("/etc/systemd/system/hello-juju.service", "w+") as t:
            t.write(rendered)

        # Ensure correct permissions are set on the service
        os.chmod("/etc/systemd/system/hello-juju.service", 0o755)
        # Reload systemd units
        check_call(["systemctl", "daemon-reload"])

    def _render_settings_file(self):
        """Render the application settings file with database connection details"""
        # Open the template settings files
        with open("templates/settings.py.j2", "r") as t:
            template = Template(t.read())

        # Render the template file with the correct values
        rendered = template.render(conn_str=self._stored.conn_str)

        # Write the rendered file out to disk
        with open(f"{APP_PATH}/settings.py", "w+") as t:
            t.write(rendered)
        # Ensure correct permissions are set on the file
        os.chmod(f"{APP_PATH}/settings.py", 0o644)
        # Get the uid/gid for the www-data user
        u = pwd.getpwnam("www-data")
        # Set the correct ownership for the settings file
        os.chown(f"{APP_PATH}/settings.py", uid=u.pw_uid, gid=u.pw_gid)

    def _create_database_tables(self):
        """Initialise the database and populate with initial tables required"""
        self.unit.status = MaintenanceStatus("creating database tables")
        # Call the application's `init.py` file to instantiate the database tables
        check_call(["sudo", "-u", "www-data", f"{VENV_ROOT}/bin/python3", f"{APP_PATH}/init.py"])


if __name__ == "__main__":
    main(HelloJujuCharm)
