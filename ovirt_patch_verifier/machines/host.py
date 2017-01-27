from . import BaseMachine


class HostMachine(BaseMachine):

    vm_type = 'ovirt-host'

    def set_properties(self):
        self.add_deploy_script('setup_host.sh')
