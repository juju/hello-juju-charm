# Overview

This charm is intended to be used with Juju's [Getting Started][] documentation.

# Usage

Deploying `hello-juju`:

    juju deploy cs:~juju/hello-juju
    juju expose hello-juju

You can now access the application by connecting to the unit's public address field from the `juju status` output:

    juju status
    > ...
    > App         Version  Status  Scale  Charm       Store  Rev  OS      Notes
    > hello-juju           active      1  hello-juju  local    0  ubuntu  exposed
    >
    > Unit           Workload  Agent  Machine  Public address  Ports   Message
    > hello-juju/0*  active    idle   0        <ip-address>    80/tcp  
    > ...
    
    curl <ip-address>
    > Hello Juju!

## Scaling out

This charm is not able to be used with multiple units.


## Known Limitations and Issues

`hello-juju` does not provide or consume any relations.


# Configuration

`hello-juju` does not support custom configuration.


# Project Information

## Maintainer

This charm is maintained by Canonical, Ltd. Please create a post in our [Discourse forum][] if you encounter any issues.


## Upstream Project Name

- Upstream website
- Upstream bug tracker
- Upstream mailing list or contact information
- Feel free to add things if it's useful for users

  [Getting Started]: https://jaas.ai/docs/getting-started-with-juju
  [Discourse forum]: https://discourse.jujucharms.com/
