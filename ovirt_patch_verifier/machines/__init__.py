from abc import ABCMeta, abstractmethod, abstractproperty
from importlib import import_module
import os

cwd = os.path.dirname(os.path.abspath(__file__))


class BaseMachine(object):

    __metaclass__ = ABCMeta

    memory = 2048
    distro = 'el7.3'  # FIXME
    root_password = '123456'
    service_provider = 'systemd'

    def __init__(self, settings):
        pieces = [i.strip() for i in settings.split(',')]
        pieces.pop(0)

        kwargs = {}
        for piece in pieces:
            kv = piece.split('=', 1)
            if len(kv) == 2:
                kwargs[kv[0]] = kv[1]
            else:
                kwargs[kv[0]] = True

        # set common properties by default
        if 'name' not in kwargs:
            raise RuntimeError('Machine name not defined!')
        self.name = kwargs.pop('name')
        if 'memory' in kwargs:
            self.memory = int(kwargs.pop('memory'))
        if 'distro' in kwargs:
            self.distro = kwargs.pop('distro')
        if 'root_password' in kwargs:
            self.root_password = kwargs.pop('root_password')
        if 'service_provider' in kwargs:
            self.service_provider = kwargs.pop('service_provider')

        # nics are predefined for now. will support bonding and
        # storage-dedicated network later
        self.nics = [{'net': 'ovirt-patch-verifier'}]

        # root disk for any machine
        self.disks = [
            {
                'template_name': '%s-base' % self.distro,
                'type': 'template',
                'name': 'root',
                'dev': 'vda',
                'format': 'qcow2',
            }
        ]

        self.metadata = {'deploy-scripts': []}
        self.add_deploy_script('add_local_repo.sh')
        self.set_properties(**kwargs)

    @abstractmethod
    def set_properties(self, **kwargs):
        pass

    @abstractproperty
    def vm_type(self):
        pass

    @classmethod
    def supported(cls, settings):
        pieces = [i.strip() for i in settings.split(',')]
        return 'ovirt-%s' % pieces[0] == cls.vm_type

    def add_deploy_script(self, script):
        self.metadata['deploy-scripts'].append(
            os.path.join(cwd, 'deploy-scripts', script))

    def to_dict(self):
        return {
            'vm-type': self.vm_type,
            'memory': int(self.memory),
            'service-provider': self.service_provider,
            'root_password': self.root_password,
            'nics': self.nics,
            'disks': self.disks,
            'metadata': self.metadata,
        }


def get_machines():
    imported = []
    for class_file in os.listdir(cwd):
        name, ext = os.path.splitext(class_file)
        if ext not in ['.py', '.pyc', '.pyo']:
            continue
        if name in ['__init__']:
            continue
        if name not in imported:
            import_module('%s.%s' % (__name__, name))
            imported.append(name)
    return BaseMachine.__subclasses__()


def get_definition_from_settings(settings):
    for klass in get_machines():
        if klass.supported(settings):
            return klass(settings)
