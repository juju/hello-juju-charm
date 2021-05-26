# Hello, Juju! Charm

This [charm](https://charmhub.io/hello-juju) is a demonstration machine charm
written with the [Charmed Operator Framework](https://github.com/canonical/operator).

It deploys a simple Python [Flask](https://flask.palletsprojects.com/en/2.0.x/)
[web application](https://github.com/juju/hello-juju). The application itself is
simple, and counts the number of times the root URL has been requested and stores the
count in a database. With no database relation defined, this information is stored in
a sqlite database.

This charm also supports a [relation](https://juju.is/docs/sdk/relations) to the
[PostgreSQL charm](https://charmhub.io/postgresql). When this relation is established
the Flask application is automatically configured to use the PostgreSQL database
to store its count.

## Quickstart

Assuming you already have Juju installed and bootstrapped on a cloud, such as LXD:

```bash
# Create a model
$ juju add-model dev
# Deploy the charm
$ juju deploy hello-juju
# Wait for the deployment to complete
$ juju status
Model  Controller  Cloud/Region         Version  SLA          Timestamp
dev    lxd         localhost/localhost  2.9.1    unsupported  14:46:51+01:00

App         Version  Status  Scale  Charm       Store  Channel  Rev  OS      Message
hello-juju           active      1  hello-juju  local             0  ubuntu

Unit           Workload  Agent  Machine  Public address  Ports   Message
hello-juju/0*  active    idle   0        10.14.25.117    80/tcp

Machine  State    DNS           Inst id        Series  AZ  Message
0        started  10.14.25.117  juju-9f46aa-0  focal       Running
```

You should be able to visit [http://10.14.25.117](http://10.14.25.117)
in your browser.

Once you've visited/refreshed a couple of times, visit
[http://10.14.25.117/greetings](http://10.14.25.117/greetings) to see a count
of how many times the page has been requested.

## Using PostgreSQL

To use PostgreSQL as the backing database, deploy the charm, then deploy PostgreSQL
and relate the two applications, specifying the `db` interface.

Assuming you already have the `hello-juju` charm deployed, you can start using
PostgreSQL like so:

```bash
# Deploy PostgreSQL
$ juju deploy postgresql
# Relate the two applications
$ juju relate hello-juju postgresql:db
# Check the status:
$ juju status --relations
Model  Controller  Cloud/Region         Version  SLA          Timestamp
dev    lxd         localhost/localhost  2.9.1    unsupported  14:55:47+01:00

App         Version  Status  Scale  Charm       Store     Channel  Rev  OS      Message
hello-juju           active      1  hello-juju  local                1  ubuntu
postgresql  12.6     active      1  postgresql  charmhub  stable   233  ubuntu  Live master (12.6)

Unit           Workload  Agent  Machine  Public address  Ports     Message
hello-juju/0*  active    idle   2        10.14.25.117    80/tcp
postgresql/0*  active    idle   1        10.14.25.157    5432/tcp  Live master (12.6)

Machine  State    DNS           Inst id        Series  AZ  Message
1        started  10.14.25.157  juju-9f46aa-1  focal       Running
2        started  10.14.25.117  juju-9f46aa-2  focal       Running

Relation provider       Requirer                Interface    Type     Message
postgresql:coordinator  postgresql:coordinator  coordinator  peer
postgresql:db           hello-juju:db           pgsql        regular
postgresql:replication  postgresql:replication  pgpeer       peer
```

The application will behave exactly as before, but now the request store will
be stored in the PostgreSQL database

## Development Setup

To set up a local test environment with [LXD](https://linuxcontainers.org/lxd/introduction/):

```bash
# Install LXD
$ sudo snap install --classic lxd
# Configure LXD with defaults
$ sudo lxd init --auto
# (Optional) Add your user to the LXD group
$ newgrp lxd
$ sudo adduser $(whoami) lxd
# Install Charmcraft
$ sudo snap install charmcraft
# Install juju
$ sudo snap install --classic juju
# Bootstrap the Juju controller on lxd
$ juju bootstrap localhost lxd
# Add a new model to Juju
$ juju add-model dev
```

## Build and Deploy Locally

```bash
# Clone the charm code
$ git clone https://github.com/juju/hello-juju && cd hello-juju
# Build the charm package
$ charmcraft pack
# Deploy!
$ juju deploy ./hello-juju.charm
# Wait for the deployment to complete
$ watch -n1 --color juju status --color
```

## Testing

```bash
# Clone the charm code
$ git clone https://github.com/juju/hello-juju && cd hello-juju
# Install python3-virtualenv
$ sudo apt update && sudo apt install -y python3-virtualenv
# Create a virtualenv for the charm code
$ virtualenv venv
# Activate the venv
$ source ./venv/bin/activate
# Install dependencies
$ pip install -r requirements-dev.txt
# Run the tests
$ ./run_tests
```

## Get Help & Community

If you get stuck deploying this charm, or would like help with charming
generally, come and join the charming community!

- [Community Discourse](https://discourse.charmhub.io)
- [Community Chat](https://chat.charmhub.io/charmhub/channels/creating-charmed-operators)

## More Information/Related

Below are some links related to this demo charm:

- [Charmed Operator Framework Documentation](https://juju.is/docs/sdk)
- [Charmed Operator Framework Source](https://github.com/canonical/operator)
- [Juju Documentation](https://juju.is/docs/olm)
- [Charmhub](https://charmhub.io)
