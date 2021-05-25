# Copyright 2021 Canonical
# See LICENSE file for licensing details.
#
# Learn more about testing at: https://juju.is/docs/sdk/testing

import subprocess
import unittest
from unittest import mock
from unittest.mock import Mock, call, mock_open, patch

from charm import APP_PATH, VENV_ROOT, HelloJujuCharm
from ops.model import BlockedStatus, MaintenanceStatus
from ops.testing import Harness

RENDERED_SETTINGS = """

###############################################
# Warning:                                    #
#     this file has been written by Juju,     #
#     any updates may be overwritten          #
###############################################

DATABASE_URI = "postgresql://test_connection_string"
TRACK_MODIFICATIONS = False"""

RENDERED_SYSTEMD_UNIT = """[Unit]
Description=Hello Juju web application
After=network.target

[Service]
WorkingDirectory = /srv/app
Restart = always
RestartSec = 5
ExecStart=/srv/app/venv/bin/gunicorn \\
            -u www-data \\
            -g www-data \\
            --access-logfile /srv/app/access.log \\
            --error-logfile /srv/app/error.log \\
            --bind 0.0.0.0:80 \\
            hello_juju:app
ExecReload = /bin/kill -s HUP $MAINPID
ExecStop = /bin/kill -s TERM $MAINPID
ExecStartPre = /bin/mkdir /srv/app/run
PIDFile = /srv/app/run/hello-juju.pid
ExecStopPost = /bin/rm -rf /srv/app/run

[Install]
WantedBy = multi-user.target"""


class TestCharm(unittest.TestCase):
    def setUp(self):
        self.harness = Harness(HelloJujuCharm)
        self.addCleanup(self.harness.cleanup)
        self.harness.begin()

    @mock.patch("subprocess.call")
    def test_create_database_tables(self, _mock):
        # Define the args that 'check_call' should be called with
        args = ["sudo", "-u", "www-data", f"{VENV_ROOT}/bin/python3", f"{APP_PATH}/init.py"]
        # Successful command execution returns 0
        _mock.return_value = 0
        # Execute the method
        self.harness.charm._create_database_tables()
        # Check that check_call was invoked with the correct args
        _mock.assert_called_once_with(args)
        # Ensure the unit status is set correctly
        self.assertEqual(
            self.harness.charm.unit.status, MaintenanceStatus("creating database tables")
        )

    @mock.patch("os.chmod")
    @mock.patch("os.chown")
    @mock.patch("pwd.getpwnam")
    def test_render_settings_file(self, _pwnam, _chown, _chmod):
        # Set the value that will be written into the settings file
        self.harness.charm._stored.conn_str = "postgresql://test_connection_string"

        # Setup a mock for the `open` method, set returned data to settings template
        with open("templates/settings.py.j2", "r") as f:
            m = mock_open(read_data=f.read())

        # Patch the `open` method with our mock
        with patch("builtins.open", m, create=True):
            # Set the uid/gid return values for lookup of 'www-data' user
            _pwnam.return_value.pw_uid = 35
            _pwnam.return_value.pw_gid = 35
            # Call the method
            self.harness.charm._render_settings_file()

        # Check the template is opened read-only in the first call to open
        self.assertEqual(m.call_args_list[0][0], ("templates/settings.py.j2", "r"))
        # Check the settings file is opened with "w+" mode in the second call to open
        self.assertEqual(m.call_args_list[1][0], (f"{APP_PATH}/settings.py", "w+"))
        # Ensure the correct rendered template is written to file
        m.return_value.write.assert_called_with(RENDERED_SETTINGS)
        # Ensure that the correct user is lookup up
        _pwnam.assert_called_with("www-data")
        # Ensure the file is chmod'd correctly
        _chmod.assert_called_with(f"{APP_PATH}/settings.py", 0o644)
        # Ensure the file is chown'd correctly
        _chown.assert_called_with(f"{APP_PATH}/settings.py", uid=35, gid=35)

    @mock.patch("charm.check_call")
    @mock.patch("os.chmod")
    def test_render_systemd_unit(self, _chmod, _call):
        # Create a mock for the `open` method, set the return value of `read` to
        # the contents of the systemd unit template
        with open("templates/hello-juju.service.j2", "r") as f:
            m = mock_open(read_data=f.read())

        # Patch the `open` method with our mock
        with patch("builtins.open", m, create=True):
            # Ensure the stored value is clear to test it's set properly
            self.harness.charm._stored.port = ""
            # Mock the return value of the `check_call`
            _call.return_value = 0
            # Call the method
            self.harness.charm._render_systemd_unit()

        # Check the state was updated with the port from the config
        self.assertEqual(self.harness.charm._stored.port, self.harness.charm.config["port"])
        # Check the template is opened read-only in the first call to open
        self.assertEqual(m.call_args_list[0][0], ("templates/hello-juju.service.j2", "r"))
        # Check the systemd unit file is opened with "w+" mode in the second call to open
        self.assertEqual(m.call_args_list[1][0], ("/etc/systemd/system/hello-juju.service", "w+"))
        # Ensure the correct rendered template is written to file
        m.return_value.write.assert_called_with(RENDERED_SYSTEMD_UNIT)
        # Check the file permissions are set correctly
        _chmod.assert_called_with("/etc/systemd/system/hello-juju.service", 0o755)
        # Check that systemd is reloaded to register the changes to the unit
        _call.assert_called_with(["systemctl", "daemon-reload"])

        # Now check that any existing port in state is respected
        # Patch the `open` method with our mock
        with patch("builtins.open", m, create=True):
            # Ensure the stored value is clear to test it's set properly
            self.harness.charm._stored.port = 8080
            # Mock the return value of the `check_call`
            _call.return_value = 0
            # Call the method
            self.harness.charm._render_systemd_unit()
        # Ensure the rendered template is adjusted to take into consideration the port
        m.return_value.write.assert_called_with(RENDERED_SYSTEMD_UNIT.replace(":80", ":8080"))
        self.assertEqual(self.harness.charm._stored.port, 8080)

    @mock.patch("charm.check_output")
    def test_install_apt_packages(self, _call: Mock):
        # Set the return code for subprocess.check_output
        _call.return_code = 0
        # Call the method with some packages to install
        self.harness.charm._install_apt_packages(["curl", "vim"])
        # Ensure the log output is correct
        self.assertLogs("updating apt cache", level="DEBUG")
        self.assertLogs("installing apt packages: curl, vim", level="DEBUG")
        # Check that apt is called with the correct arguments
        self.assertEqual(
            _call.call_args_list,
            [call(["apt-get", "update"]), call(["apt-get", "install", "-y", "curl", "vim"])],
        )
        # Now check that if an exception is raised we do the right logging
        _call.reset_mock()
        _call.return_value = 1
        _call.side_effect = subprocess.CalledProcessError(1, "apt")
        self.harness.charm._install_apt_packages(["curl", "vim"])
        self.assertLogs("failed to install packages: curl, vim", level="ERROR")
        self.assertEqual(
            self.harness.charm.unit.status, BlockedStatus("Failed to install packages")
        )

    @mock.patch("charm.HelloJujuCharm._create_database_tables")
    @mock.patch("charm.HelloJujuCharm._render_settings_file")
    @mock.patch("charm.check_output")
    @mock.patch("charm.Repo.clone_from")
    @mock.patch("charm.Path")
    @mock.patch("shutil.rmtree")
    def test_setup_application(self, _rmtree, _path, _clone, _check_output, _render, _createdb):
        # Setup to dive into all the if branches on the first run
        # Make sure we try to remove the directory that "exists"
        _path.return_value.is_dir.return_value = True
        # Set a connection string so that we render the settings file
        self.harness.charm._stored.conn_str = "my_connection_string"
        # Call the method
        self.harness.charm._setup_application()
        # Ensure we set the charm status correctly
        self.assertEqual(
            self.harness.charm.unit.status, MaintenanceStatus("fetching application code")
        )
        # Check we try to remove the directory
        _rmtree.assert_called_with("/srv/app")
        # Check we set the stored repository where none exists
        self.assertEqual(self.harness.charm._stored.repo, "https://github.com/juju/hello-juju")
        # Ensure we clone the repo
        _clone.assert_called_with("https://github.com/juju/hello-juju", APP_PATH)
        # Ensure we initialise the Python deps correctly
        self.assertEqual(
            _check_output.call_args_list,
            [
                call(["python3", "-m", "virtualenv", VENV_ROOT]),
                call([f"{VENV_ROOT}/bin/pip3", "install", "gunicorn"]),
                call([f"{VENV_ROOT}/bin/pip3", "install", "-r", f"{APP_PATH}/requirements.txt"]),
            ],
        )
        # Check we render the settings file with the stored connection string
        _render.assert_called_once()
        # Check that the database table method is called
        _createdb.assert_called_once()
        #
        # Run again covering different branches
        #
        # Make sure we don't try to remove the directory
        _path.return_value.is_dir.return_value = False
        self.harness.charm._stored.repo = "https://myrepo"
        self.harness.charm._stored.conn_str = ""
        _rmtree.reset_mock()
        _render.reset_mock()
        # Call the method
        self.harness.charm._setup_application()
        _render.assert_not_called()
        _rmtree.assert_not_called()
        self.assertEqual(self.harness.charm._stored.repo, "https://myrepo")
