import os
from subprocess import check_call

from charmhelpers.core.templating import render
from charmhelpers.core.host import service, service_running, service_available
from charmhelpers.core.hookenv import open_port, config
from charmhelpers.core.hookenv import status_set
from charmhelpers.core.hookenv import application_name
from charms.reactive import when, when_not, set_flag, set_state, endpoint_from_flag, when_file_changed
from charms.reactive.flags import register_trigger

def dbname():
    return f'hello-juju_{application_name()}'

def port():
    return int(config('port'))

@when('codebase.available')
@when_not('hello_juju.installed')
def install_hello_juju():
    # If your charm has other dependencies before it can install,
    # add those as @when() clauses above., or as additional @when()
    # decorated handlers below
    #
    # See the following for information about reactive charms:
    #
    #  * https://jujucharms.com/docs/devel/developer-getting-started
    #  * https://github.com/juju-solutions/layer-basic#overview
    #

    # further links
    # - https://ubuntu.com/blog/charming-discourse-with-the-reactive-framework

    app = application_name()
    venv_root = f"/srv/hello-juju/venv"
    status_set("maintenance", "Creating Python virtualenv")
    check_call(['/usr/bin/python3', '-m', 'venv', venv_root])
    status_set("maintenance", "Installing Python requirements")
    check_call([f'{venv_root}/bin/pip', 'install', 'gunicorn'])
    check_call([f'{venv_root}/bin/pip', 'install', '-r', '/srv/hello-juju/current/requirements.txt'])
    create_database_tables() # hello-juju can operate without a relation via SQLite via its default settings
    set_state('hello_juju.installed')


@when('hello_juju.installed')
@when_not('hello_juju.gunicorn_configured')
def configure_gunicorn():
    status_set("maintenance", "Configuring gunicorn service")
    render(
        'hello-juju.service.j2',
        '/etc/systemd/system/hello-juju.service',
        perms=0o755,
        context={
            'port': port(),
            'project_root': '/srv/hello-juju/current',
            'user': 'www-data',
            'group': 'www-data',
        }
    )
    service("enable", "hello-juju")
    status_set("active", "Serving HTTP from gunicorn")


def create_database_tables():
    status_set('maintenance', 'Creating database tables')
    check_call('sudo -u www-data /srv/hello-juju/venv/bin/python3 /srv/hello-juju/current/init.py'.split())


@when('db.connected')
def request_db(pgsql):
    status_set('maintenance', 'Ensuring database is available')
    pgsql.set_database(dbname())
    set_state('hello_juju.database_requested')


@when_file_changed('/srv/hello-juju/current/settings.py', '/etc/systemd/system/hello-juju.service')
def restart():
    open_port(port())
    if service_running('hello-juju'):
        service('restart', 'hello-juju')
    else:
        service('start', 'hello-juju')
    status_set("active", "")

@when_not('db.master.available')
@when('hello_juju.database_requested')
def pending():
    status_set('waiting', 'Awaiting database creation')

@when('db.master.available', 'codebase.available')
@when_not('hello_juju.database_configured')
def create_and_configure_database():
    pgsql = endpoint_from_flag('db.master.available')

    render(
        'settings.py.j2',
        '/srv/hello-juju/current/settings.py',
        {'db': pgsql.master},
        owner='www-data',
        perms=0o644,
    )
    create_database_tables()
    set_state('hello_juju.database_configured')
    status_set('active', '')

@when('config.changed.port')
def port_updated():
    configure_gunicorn()
    restart()
