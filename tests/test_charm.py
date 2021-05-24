# Copyright 2021 Canonical
# See LICENSE file for licensing details.
#
# Learn more about testing at: https://juju.is/docs/sdk/testing

import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

import mock
from charm import APP_PATH, VENV_ROOT, HelloJujuCharm
from ops.model import MaintenanceStatus
from ops.testing import Harness

TMP_DIR = tempfile.mkdtemp()

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
WorkingDirectory = /app
Restart = always
RestartSec = 5
ExecStart=/app/venv/bin/gunicorn \
            -u www-data \
            -g www-data \
            --access-logfile /app/access.log \
            --error-logfile /app/error.log \
            --bind 0.0.0.0:80 \
            hello_juju:app
ExecReload = /bin/kill -s HUP $MAINPID
ExecStop = /bin/kill -s TERM $MAINPID
ExecStartPre = /bin/mkdir /app/run
PIDFile = /app/run/hello-juju.pid
ExecStopPost = /bin/rm -rf /app/run

[Install]
WantedBy = multi-user.target
"""


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

    @mock.patch("charm.APP_PATH", TMP_DIR)
    def test_render_settings_file(self):
        # Make a new temp directory for the tests
        os.makedirs(TMP_DIR, exist_ok=True)
        settings_file = f"{TMP_DIR}/settings.py"

        # Set the value that will be written into the settings file
        self.harness.charm._stored.conn_str = "postgresql://test_connection_string"

        with patch("pwd.getpwnam") as mock:
            # Make sure the uid/gid returned is the current user for the test
            mock.return_value.pw_uid = os.getuid()
            mock.return_value.pw_gid = os.getgid()
            # Call the method
            self.harness.charm._render_settings_file()

        # Check the rendered file is as expected
        with open(settings_file, "r") as f:
            self.assertEqual(RENDERED_SETTINGS, f.read())

        # Ensure the correct file mode/owner was set
        status = os.stat(settings_file)
        file_mode = oct(status.st_mode & 0o777)
        self.assertEqual(file_mode, oct(0o644))
        self.assertEqual(status.st_uid, os.getuid())
        self.assertEqual(status.st_gid, os.getgid())
        # Remove the temporary directory
        shutil.rmtree(TMP_DIR)
