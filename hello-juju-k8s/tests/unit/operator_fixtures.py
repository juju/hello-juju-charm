#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
# Copyright © 2020 Tim McNamara tsm@canonical.com
# Distributed under terms of the GPL license.
"""Operator Charm test fixtures."""

import os
import tempfile
import unittest

import setuppath  # noqa:F401
import mock
import ops
import ops.main
from src.charm import Hello-Juju-K8SCharm


class OperatorTestCase(unittest.TestCase):
    """Fixtures for unit testing operator charms."""

    @classmethod
    def setUpClass(cls):
        """Setup class fixture."""
        # Setup a tmpdir
        cls.tmpdir = tempfile.TemporaryDirectory()

        # Store patchers for test cases that want them
        cls.patchers = {}

        # Prevent framwork from trying to call subprocesses
        run_patcher = mock.patch("ops.model.ModelBackend._run")
        cls.patchers["ops.model.ModelBackend._run"] = run_patcher.start()

        # Stop unit test from calling fchown
        fchown_patcher = mock.patch("os.fchown")
        cls.patchers["os.fchown"] = fchown_patcher.start()
        chown_patcher = mock.patch("os.chown")
        cls.patchers["os.chown"] = chown_patcher.start()

        # Setup mock JUJU Environment variables
        os.environ["JUJU_UNIT_NAME"] = "mock/0"
        os.environ["JUJU_CHARM_DIR"] = "."

    @classmethod
    def tearDownClass(cls):
        """Tear down class fixture."""
        mock.patch.stopall()
        cls.tmpdir.cleanup()

    def setUp(self):
        """Setup test fixture."""
        # Create a charm instance
        model_backend = ops.model.ModelBackend()
        ops.main.setup_root_logging(model_backend)
        charm_dir = ops.main._get_charm_dir()
        metadata, actions_metadata = ops.main._load_metadata(charm_dir)
        meta = ops.charm.CharmMeta(metadata, actions_metadata)
        unit_name = os.environ["JUJU_UNIT_NAME"]
        model = ops.model.Model(unit_name, meta, model_backend)
        framework = ops.framework.Framework(":memory:", charm_dir, meta, model)
        charm = Hello-Juju-K8SCharm(framework, None)
        self.charm = charm

    def tearDown(self):
        """Clean up test fixture."""
        # Remove runtime class attributes to avoid error on next setUp

        for relation_name in self.charm.framework.meta.relations:
            relation_name = relation_name.replace("-", "_")
            delattr(ops.charm.CharmEvents, relation_name + "_relation_joined")
            delattr(ops.charm.CharmEvents, relation_name + "_relation_changed")
            delattr(ops.charm.CharmEvents, relation_name + "_relation_departed")
            delattr(ops.charm.CharmEvents, relation_name + "_relation_broken")

        for storage_name in self.charm.framework.meta.storages:
            storage_name = storage_name.replace("-", "_")
            delattr(ops.charm.CharmEvents, storage_name + "_storage_attached")
            delattr(ops.charm.CharmEvents, storage_name + "_storage_detaching")

        for action_name in self.charm.framework.meta.actions:
            action_name = action_name.replace("-", "_")
            delattr(ops.charm.CharmEvents, action_name + "_action")

    def emit(self, event):
        """Emit the named hook on the charm."""
        self.charm.framework.reemit()

        if "_relation_" in event:
            relation_name = event.split("_relation")[0].replace("_", "-")
            with mock.patch.dict(
                "os.environ",
                {
                    "JUJU_RELATION": relation_name,
                    "JUJU_RELATION_ID": "1",
                    "JUJU_REMOTE_APP": "mock",
                    "JUJU_REMOTE_UNIT": "mock/0",
                },
            ):
                ops.main._emit_charm_event(self.charm, event)
        else:
            ops.main._emit_charm_event(self.charm, event)

    def get_notice_count(self, hook):
        """Return the notice count for a given charm hook."""
        notice_count = 0
        handle = "Hello-Juju-K8SCharm/on/{}".format(hook)

        for event_path, _, _ in self.charm.framework._storage.notices(None):
            if event_path.startswith(handle):
                notice_count += 1

        return notice_count
