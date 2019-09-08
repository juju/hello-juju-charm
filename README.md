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
    >
    > Machine  State    DNS           Inst id        Series  AZ  Message
    > 0        started  <ip-address>  <instance-id>  bionic      Running

    
Now from another computer, you'll be able to make HTTP requests to it.
    
    curl <ip-address>
    > Hello Juju!

If you don't have `curl`, open your browser at `<ip-address>`.  
The charm also installs `curl` on `hello-juju/0`, so you could try that too.

    juju ssh hello-juju/0
    > ubuntu@<instance-id>:~$

    curl localhost
    > Hello Juju!

## Endpoints supported

- `/`: returns the plain text string `Hello Juju!\r\n\r\n`
- `/greetings`: returns a JSON object with a count of the greetings that have been sent, e.g. `{"greetings": 1}`


## Relating to other charms

Applications can negotiate their own configuration via Juju relations.
A relation is 

### Changing databases via `pgsql`

By default, `hello-juju` uses a SQLite database.
When related to a charm that provides the `pgsql` relation, `hello-juju` will store its data there.

    juju deploy postgresql
    juju relate postgresql:db hello-juju 


## Scaling out

This charm is not able to be used with multiple units.


## Configuration

`hello-juju` does not support custom configuration.


# Project Information

`hello-juju` charm is maintained by Canonical. Please create a post in our [Discourse forum][] if you encounter any issues.


  [Getting Started]: https://jaas.ai/docs/getting-started-with-juju
  [Discourse forum]: https://discourse.jujucharms.com/
