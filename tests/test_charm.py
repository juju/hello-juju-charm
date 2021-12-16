# Copyright 2021 Canonical
# See LICENSE file for licensing details.
#
# Learn more about testing at: https://juju.is/docs/sdk/testing

import unittest
from pathlib import Path
from unittest import mock
from unittest.mock import Mock, call, mock_open, patch

from charm import APP_PATH, UNIT_PATH, VENV_ROOT, HelloJujuCharm
from charms.operator_libs_linux.v0 import apt
from ops.model import ActiveStatus, BlockedStatus, MaintenanceStatus
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

    @mock.patch("charm.HelloJujuCharm._install_apt_packages")
    @mock.patch("charm.HelloJujuCharm._setup_application")
    @mock.patch("charm.HelloJujuCharm._render_systemd_unit")
    @mock.patch("charm.check_call")
    def test_on_install(self, _call, _render, _setup, _install):
        self.harness.charm.on.install.emit()
        self.assertEqual(
            self.harness.charm.unit.status, MaintenanceStatus("installing pip and virtualenv")
        )
        _install.assert_called_with(["python3-pip", "python3-virtualenv"])
        _setup.assert_called_once()
        _render.assert_called_once()

    @mock.patch("charms.operator_libs_linux.v0.systemd.service_resume")
    @mock.patch("charm.check_call")
    def test_on_start(self, _call, _resume):
        # This would normally have happened during the install event
        self.harness.charm._stored.port = 80
        # Run the handler
        self.harness.charm.on.start.emit()
        # Ensure we set an ActiveStatus for the charm
        self.assertEqual(self.harness.charm.unit.status, ActiveStatus())
        # Make sure the port is opened and the service is started
        self.assertEqual(_call.call_args_list, [call(["open-port", "80/TCP"])])
        _resume.assert_called_with("hello-juju")

    @mock.patch("charms.operator_libs_linux.v0.systemd.service_restart")
    @mock.patch("charm.check_call")
    @mock.patch("charm.HelloJujuCharm._setup_application")
    @mock.patch("charm.HelloJujuCharm._render_systemd_unit")
    def test_on_config_changed(self, _render, _setup, _call, _restart):
        # Check first run, no change to values set by install/start
        self.harness.charm._stored.repo = "https://github.com/juju/hello-juju"
        self.harness.charm._stored.port = 80
        # Run the handler
        self.harness.charm.on.config_changed.emit()
        _setup.assert_not_called()
        _call.assert_not_called()
        self.assertEqual(self.harness.charm.unit.status, ActiveStatus())

        # Change the application repo, should prompt a restart
        _setup.reset_mock()
        _call.reset_mock()
        self.harness.update_config({"application-repo": "DIFFERENT"})
        self.assertEqual(self.harness.charm._stored.repo, "DIFFERENT")
        _setup.assert_called_once()
        # This also ensures that the port change code wasn't run
        _render.assert_not_called()
        _restart.assert_called_with("hello-juju")
        self.assertEqual(self.harness.charm.unit.status, ActiveStatus())

        # Change the port, should prompt a restart
        _setup.reset_mock()
        _call.reset_mock()
        _restart.reset_mock()
        self.harness.update_config({"port": 8080})
        self.assertEqual(self.harness.charm._stored.port, 8080)
        _render.assert_called_once()
        _setup.assert_not_called()
        # Check the old port is closed, the new is opened and the service restarts
        self.assertEqual(
            _call.call_args_list,
            [
                call(["close-port", "80/TCP"]),
                call(["open-port", "8080/TCP"]),
            ],
        )
        _restart.assert_called_with("hello-juju")

        self.assertEqual(self.harness.charm.unit.status, ActiveStatus())

    @mock.patch("pgsql.opslib.pgsql.client._leader_get")
    @mock.patch("pgsql.opslib.pgsql.client._leader_set")
    def test_on_database_relation_joined_leader(self, _leader_set, _leader_get):
        # Setup the mocks for leader-get and leader-set in the pgsql library
        _leader_get.return_value = {}
        _leader_set.return_value = None
        # Test first as leader
        self.harness.set_leader(True)
        # Define the relation
        relation = self.harness.add_relation("db", "postgresql")
        # Add a unit to the relation
        self.harness.add_relation_unit(relation, "postgresql/0")
        # Ensure that this charm sets it's relation data correctly
        self.assertEqual(
            self.harness.get_relation_data(relation, self.harness.charm.app.name),
            {"database": self.harness.charm.app.name},
        )

    @mock.patch("pgsql.opslib.pgsql.client._leader_get")
    @mock.patch("pgsql.opslib.pgsql.client._leader_set")
    def test_on_database_relation_joined_non_leader(self, _leader_set, _leader_get):
        # Setup the mocks for leader-get and leader-set in the pgsql library
        _leader_get.return_value = {}
        _leader_set.return_value = None
        # Test first as leader
        self.harness.set_leader(False)
        # Define the relation
        relation = self.harness.add_relation("db", "postgresql")
        # Add a unit to the relation
        self.harness.add_relation_unit(relation, "postgresql/0")
        # Ensure that this charm sets it's relation data correctly
        self.assertEqual(
            self.harness.get_relation_data(relation, self.harness.charm.app.name),
            {},
        )

    @mock.patch("charm.HelloJujuCharm._render_settings_file")
    @mock.patch("charm.HelloJujuCharm._create_database_tables")
    @mock.patch("charms.operator_libs_linux.v0.systemd.service_restart")
    @mock.patch("pgsql.opslib.pgsql.client._leader_get")
    @mock.patch("pgsql.opslib.pgsql.client._leader_set")
    def test_on_database_master_changed(
            self, _leader_set, _leader_get, _restart, _createdb, _render):
        # Setup the mocks for leader-get and leader-set in the pgsql library
        _leader_get.return_value = {}
        _leader_set.return_value = None
        # Test as a leader first
        self.harness.set_leader(True)
        # Setup the relation
        relation = self.harness.add_relation("db", "postgresql")
        self.harness.add_relation_unit(relation, "postgresql/0")

        # Trigger the on_database_master_changed event with some data
        test_event = Mock()
        test_event.database = "hello-juju"
        test_event.master.uri = "postgresql://TEST"

        # Run the handler
        self.harness.charm._on_database_master_changed(test_event)
        # Check the connection string was updated to use pg8000
        self.assertEqual(self.harness.charm._stored.conn_str, "postgresql+pg8000://TEST")
        _render.assert_called_once()
        _createdb.assert_called_once()
        _restart.assert_called_with("hello-juju")
        self.assertEqual(self.harness.charm.unit.status, ActiveStatus())

        # Check where the database hasn't yet been set
        # Reset some stuff
        _render.reset_mock()
        test_event = Mock()
        # Run the handler
        self.harness.charm._on_database_master_changed(test_event)
        _render.assert_not_called()

        # Check where the database hasn't yet been set
        # Reset some stuff
        _restart.reset_mock()
        test_event = Mock()
        test_event.database = "hello-juju"
        test_event.master = None
        # Run the handler
        self.harness.charm._on_database_master_changed(test_event)
        _restart.assert_not_called()

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
    @mock.patch("charms.operator_libs_linux.v0.passwd.user_exists")
    def test_render_settings_file(self, _userexists, _chown, _chmod):
        # Set the value that will be written into the settings file
        self.harness.charm._stored.conn_str = "postgresql://test_connection_string"

        # Setup a mock for the `open` method, set returned data to settings template
        with open("templates/settings.py.j2", "r") as f:
            m = mock_open(read_data=f.read())

        # Patch the `open` method with our mock
        with patch("builtins.open", m, create=True):
            # Set the uid/gid return values for lookup of 'www-data' user
            _userexists.return_value.pw_uid = 35
            _userexists.return_value.pw_gid = 35
            # Call the method
            self.harness.charm._render_settings_file()

        # Check the template is opened read-only in the first call to open
        self.assertEqual(m.call_args_list[0][0], ("templates/settings.py.j2", "r"))
        # Check the settings file is opened with "w+" mode in the second call to open
        self.assertEqual(m.call_args_list[1][0], (f"{APP_PATH}/settings.py", "w+"))
        # Ensure the correct rendered template is written to file
        m.return_value.write.assert_called_with(RENDERED_SETTINGS)
        # Ensure that the correct user is lookup up
        _userexists.assert_called_with("www-data")
        # Ensure the file is chmod'd correctly
        _chmod.assert_called_with(f"{APP_PATH}/settings.py", 0o644)
        # Ensure the file is chown'd correctly
        _chown.assert_called_with(f"{APP_PATH}/settings.py", uid=35, gid=35)

    @mock.patch("charms.operator_libs_linux.v0.systemd.daemon_reload")
    @mock.patch("os.chmod")
    def test_render_systemd_unit(self, _chmod, _reload):
        # Create a mock for the `open` method, set the return value of `read` to
        # the contents of the systemd unit template
        with open("templates/hello-juju.service.j2", "r") as f:
            m = mock_open(read_data=f.read())

        # Patch the `open` method with our mock
        with patch("builtins.open", m, create=True):
            # Ensure the stored value is clear to test it's set properly
            self.harness.charm._stored.port = ""
            # Mock the return value of the `check_call`
            _reload.return_value = 0
            # Call the method
            self.harness.charm._render_systemd_unit()

        # Check the unit path is correct
        self.assertEqual(UNIT_PATH, Path("/etc/systemd/system/hello-juju.service"))
        # Check the state was updated with the port from the config
        self.assertEqual(self.harness.charm._stored.port, self.harness.charm.config["port"])
        # Check the template is opened read-only in the first call to open
        self.assertEqual(m.call_args_list[0][0], ("templates/hello-juju.service.j2", "r"))
        # Check the systemd unit file is opened with "w+" mode in the second call to open
        self.assertEqual(m.call_args_list[1][0], (UNIT_PATH, "w+"))
        # Ensure the correct rendered template is written to file
        m.return_value.write.assert_called_with(RENDERED_SYSTEMD_UNIT)
        # Check the file permissions are set correctly
        _chmod.assert_called_with(UNIT_PATH, 0o755)
        # Check that systemd is reloaded to register the changes to the unit
        _reload.assert_called_once()

        # Now check that any existing port in state is respected
        # Patch the `open` method with our mock
        with patch("builtins.open", m, create=True):
            # Ensure the stored value is clear to test it's set properly
            self.harness.charm._stored.port = 8080
            # Mock the return value of the `check_call`
            _reload.return_value = 0
            # Call the method
            self.harness.charm._render_systemd_unit()
        # Ensure the rendered template is adjusted to take into consideration the port
        m.return_value.write.assert_called_with(RENDERED_SYSTEMD_UNIT.replace(":80", ":8080"))
        self.assertEqual(self.harness.charm._stored.port, 8080)

    @mock.patch("charms.operator_libs_linux.v0.apt.update")
    @mock.patch("charms.operator_libs_linux.v0.apt.add_package")
    # @mock.patch("charm.check_output")
    def test_install_apt_packages(self, _add_package, _update):
        # Call the method with some packages to install
        self.harness.charm._install_apt_packages(["curl", "vim"])
        # Check that apt is called with the correct arguments
        _update.assert_called_once()
        _add_package.assert_called_with(["curl", "vim"])
        # Now check that if an exception is raised we do the right logging
        _add_package.reset_mock()
        _add_package.return_value = 1
        _add_package.side_effect = apt.PackageNotFoundError
        self.harness.charm._install_apt_packages(["curl", "vim"])
        self.assertEqual(
            self.harness.charm.unit.status, BlockedStatus("Failed to install packages")
        )
        # Now check that if an exception is raised we do the right logging
        _add_package.reset_mock()
        _add_package.return_value = 1
        _add_package.side_effect = apt.PackageError
        self.harness.charm._install_apt_packages(["curl", "vim"])
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
        # Check the default paths
        self.assertEqual(APP_PATH, Path("/srv/app"))
        self.assertEqual(VENV_ROOT, Path(f"{APP_PATH}/venv"))
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
                call(["python3", "-m", "virtualenv", f"{VENV_ROOT}"]),
                call([f"{VENV_ROOT}/bin/pip3", "install", "gunicorn"]),
                call(
                    [
                        f"{VENV_ROOT}/bin/pip3",
                        "install",
                        "-r",
                        f"{APP_PATH}/requirements.txt",
                        "--force",
                    ]
                ),
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
