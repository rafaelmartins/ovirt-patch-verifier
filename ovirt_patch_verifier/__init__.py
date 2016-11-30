#!/usr/bin/env python

import logging
import os
import shutil
import sys

from lago.config import config
from lago.log_utils import setup_prefix_logging
from lago.plugins import load_plugins
from lago.plugins.cli import CLIPlugin, cli_plugin, cli_plugin_add_argument, \
     cli_plugin_add_help
from lago.templates import TemplateRepository, TemplateStore
from lago.utils import in_prefix, with_logging
from lago.workdir import Workdir
from ovirtlago import OvirtPrefix, OvirtWorkdir

from .release import OvirtRelease


VM_CONF = {
    'engine': {
        'vm-type': 'ovirt-engine',
        'memory': 4096,
        'nics': [
            {
                'net': 'ovirt-patch-verifier',
            },
        ],
        'disks': [
            {
                'template_name': '##',
                'type': 'template',
                'name': 'root',
                'dev': 'vda',
                'format': 'qcow2',
            },
            {
                'comment': 'Main NFS device',
                'size': '101G',
                'type': 'empty',
                'name': 'nfs',
                'dev': 'vdb',
                'format': 'qcow2',
            },
            {
                'comment': 'Main iSCSI device',
                'size': '101G',
                'type': 'empty',
                'name': 'iscsi',
                'dev': 'vdc',
                'format': 'qcow2',
            },
        ],
        'metadata': {
            'ovirt-engine-password': '123',
            'deploy-scripts': [],
        },
    },

    'host': {
        'vm-type': 'ovirt-host',
        'memory': 2047,
        'nics': [
            {
                'net': 'ovirt-patch-verifier',
            },
        ],
        'disks': [
            {
                'template_name': '##',
                'type': 'template',
                'name': 'root',
                'dev': 'vda',
                'format': 'qcow2',
            },
        ],
        'metadata': {
            'ovirt-capabilities': 'snapshot-live-merge',
            'deploy-scripts': [],
        },
    },
}


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
    '--dist',
    help='define which distribution and version should be used as base',
    default='el7',
)
@cli_plugin_add_argument(
    '--release',
    help='define which oVirt release should be used as base',
    default='master',
)
@cli_plugin_add_argument(
    'workdir',
    help=(
        'orkdir directory of the deployment, if none passed, it will use '
        '$PWD/deployment_ovirt-patch-verifier'
    ),
    metavar='WORKDIR',
    type=os.path.abspath,
    nargs='?',
    default=None,
)
def do_deploy(vm, custom_sources, dist, release, workdir, **kwargs):
    # fix VM_CONF templates
    for vm_type in VM_CONF:
        for disk in VM_CONF[vm_type]['disks']:
            if 'template_name' in disk and disk['template_name'] == '##':
                disk['template_name'] = '%s-base' % dist

    domains = {}
    for v in vm:
        try:
            name, type_ = v.split('=', 1)
            domains[name] = VM_CONF[type_]
        except ValueError:
            raise RuntimeError('Invalid value for --vm: %s' % v)
        except KeyError:
            raise RuntimeError('Invalid vm type for "%s": %s' % (name, type))

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

    rpm_repo = config.get('reposync_dir', '/var/lib/lago/reposync')  # FIXME

    release = OvirtRelease(release)
    reposync_config = release.get_repofile(dist)

    prefix = OvirtPrefix(os.path.join(workdir.path, prefix_name))

    prefix.prepare_repo(
        rpm_repo=rpm_repo,
        reposync_yum_config=reposync_config,
        skip_sync=False,
        custom_sources=custom_sources,
    )

    prefix.start()
    prefix.deploy()


@cli_plugin(help='destroy ovirt-patch-verifier machines')
@cli_plugin_add_argument(
    '-y',
    '--yes',
    help="don't ask for confirmation, assume yes",
    action='store_true',
)
@in_ovirt_prefix
def do_destroy(yes, parent_workdir, **kwargs):
    if not yes:
        response = raw_input(
            'Do you really want to destroy ovirt-patch-verifier workdir? '
            '[Yn] '
        )
        if response and response[0] not in 'Yy':
            LOGGER.info('Aborting on user input')
            return

    parent_workdir.destroy()


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
