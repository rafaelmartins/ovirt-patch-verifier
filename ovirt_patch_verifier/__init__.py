#!/usr/bin/env python

import logging
import os
import shutil
import sys

from lago.config import config
from lago.log_utils import setup_prefix_logging
from lago.plugins import load_plugins
from lago.plugins.cli import CLIPlugin, cli_plugin, cli_plugin_add_argument
from lago.templates import TemplateRepository, TemplateStore
from lago.utils import func_vector, in_prefix, with_logging, VectorThread
from lago.workdir import Workdir
from ovirtlago import LogTask, OvirtPrefix, OvirtWorkdir
from ovirtsdk.xml import params

from .release import OvirtRelease
from .machines import get_definition_from_settings

LOGGER = logging.getLogger(__name__)

CURDIR = os.path.dirname(os.path.abspath(__file__))

in_ovirt_prefix = in_prefix(
    prefix_class=OvirtPrefix,
    workdir_class=OvirtWorkdir,
)


@cli_plugin(help='deploy ovirt-patch-verifier machines')
@cli_plugin_add_argument(
    '--vm',
    help='virtual machine(s) to start',
    metavar='NAME=TYPE',
    action='append',
    required=True,
)
@cli_plugin_add_argument(
    '--custom-source',
    help=(
        'add an extra rpm source to the repo (will have priority over the '
        'repos), allows any source string allowed by repoman'
    ),
    action='append',
    dest='custom_sources',
)
@cli_plugin_add_argument(
    '--release',
    help='define which oVirt release should be used as base',
    default='master',
)
@cli_plugin_add_argument(
    'workdir',
    help=(
        'workdir directory of the deployment, if none passed, it will use '
        '$PWD/deployment_ovirt-patch-verifier'
    ),
    metavar='WORKDIR',
    type=os.path.abspath,
    nargs='?',
    default=None,
)
def do_deploy(vm, custom_sources, release, workdir, **kwargs):
    release = OvirtRelease(release)
    release_script = release.get_install_script()

    dist = None
    domains = {}
    for v in vm:
        m = get_definition_from_settings(v)
        if m is None:
            raise RuntimeError('Invalid VM definition: %s' % v)

        if dist is None:
            dist = m.distro.split('.')[0]
        elif dist != m.distro.split('.')[0]:
            raise RuntimeError('All the VMs must use the same distro')

        domains[m.name] = m.to_dict()
        domains[m.name]['metadata']['deploy-scripts'].insert(0, release_script)

    if dist is None:
        raise RuntimeError('Failed to detect distro')

    conf = {
        'domains': domains,
        'nets': {
            'ovirt-patch-verifier': {
                'type': 'nat',
                'dhcp': {
                    'start': 100,
                    'end': 254,
                },
                'management': True,
                'dns_domain_name': 'lago.local',
            },
        },
    }

    prefix_name = 'ovirt-patch-verifier'
    if workdir is None:
        workdir = os.path.abspath('deployment_ovirt-patch-verifier')
    LOGGER.debug('Using workdir %s', workdir)
    workdir = Workdir(workdir)
    if not os.path.exists(workdir.path):
        LOGGER.debug(
            'Initializing workdir %s with prefix %s',
            workdir.path,
            prefix_name,
        )
        prefix = workdir.initialize(prefix_name)
    else:
        raise RuntimeError('Prefix already initialized. Please cleanup.')

    setup_prefix_logging(prefix.paths.logs())

    try:
        repo = TemplateRepository.from_url(
            'http://templates.ovirt.org/repo/repo.metadata'
        )

        template_store_path = config.get('template_store',
                                         '/var/lib/lago/store')
        store = TemplateStore(template_store_path)

        prefix.virt_conf(conf, repo, store, do_bootstrap=True)
        workdir.set_current(new_current=prefix_name)
    except:
        shutil.rmtree(prefix.paths.prefixed(''), ignore_errors=True)
        raise

    rpm_repo = config.get('reposync_dir', '/var/lib/lago/reposync')

    prefix = OvirtPrefix(os.path.join(workdir.path, prefix_name))
    prefix.prepare_repo(
        rpm_repo=rpm_repo,
        skip_sync=False,
        custom_sources=custom_sources or [],
    )

    prefix.start()

    prefix.deploy()


@cli_plugin(help='setup ovirt-engine machine')
@cli_plugin_add_argument(
    '--answer-file',
    help='use custom ovirt-engine answer-file',
    metavar='ANSWER-FILE',
)
@in_ovirt_prefix
@with_logging
def do_engine_setup(prefix, answer_file=None, **kwargs):
    engine = prefix.virt_env.engine_vm()
    answer_file_src = os.path.join(CURDIR, 'answer-files', 'default.conf')
    if answer_file is not None:
        answer_file_src = answer_file
    engine.copy_to(answer_file_src, '/tmp/answer-file')

    with LogTask('Run engine-setup'):
        result = engine.ssh(['engine-setup',
                             '--config-append=/tmp/answer-file'])
        if result.code != 0:
            raise RuntimeError('Failed to run engine-setup')

        engine.ssh(['rm', '-rf', '/dev/shm/yum', '/dev/shm/yumdb',
                    '/dev/shm/*.rpm'])
        engine.ssh(['systemctl', 'stop', 'firewalld'])

    with LogTask('Configuring hosts'):
        api = prefix.virt_env.engine_vm().get_api()

        def _add_host(vm):
            p = params.Host(
                name=vm.name(),
                address=vm.ip(),
                cluster=params.Cluster(
                    name='Default',
                ),
                root_password=vm.root_password(),
                override_iptables=True,
            )
            return api.hosts.add(p)

        hosts = prefix.virt_env.host_vms()

        vec = func_vector(_add_host, [(h,) for h in hosts])
        vt = VectorThread(vec)
        vt.start_all()
        vt.join_all()

        for host in hosts:
            host.ssh(['rm', '-rf', '/dev/shm/yum', '/dev/shm/*.rpm'])


def _populate_parser(cli_plugins, parser):
    verbs_parser = parser.add_subparsers(dest='opvverb', metavar='VERB', )
    for cli_plugin_name, plugin in cli_plugins.items():
        plugin_parser = verbs_parser.add_parser(
            cli_plugin_name, **plugin.init_args
        )
        plugin.populate_parser(plugin_parser)

    return parser


class OvirtPatchVerifierCLI(CLIPlugin):
    init_args = {'help': 'ovirt-patch-verifier related actions', }

    def populate_parser(self, parser):
        self.cli_plugins = load_plugins('lago.plugins.opv.cli')
        _populate_parser(self.cli_plugins, parser)
        return parser

    def do_run(self, args):
        try:
            self.cli_plugins[args.opvverb].do_run(args)

        except Exception:
            logging.exception('Error occured, aborting')
            sys.exit(1)
