import cuisine
from fabric.api import *
from fabric.colors import green, red, blue
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
env.user = "root"
env.password = "gogomid0"
cuisine.select_package('yum')


def setup_tempest():
    """
change tempest fork
checkout tempest branch
pull code
"""
    with cd('/var/lib/tempest/'):
        run('git remote add midokura git@github.com:midokura/tempest.git ')
        run('git fetch midokura')
        run('git branch --set-upstream albert midokura/albert')
        run('git pull')


def pull_tempest():
    """
    TODO: Check tempest is on the correct branch
    pull the code
"""
    run('git pull')


def run_tempest():
    tests = "test_network_basic_multisubnet"
    with cd('/var/lib/tempest/'):
        run('nosetests -q {0}'.format(tests))