from . import BaseMachine


class EngineMachine(BaseMachine):

    vm_type = 'ovirt-engine'
    memory = 4096

    def set_properties(self, iscsi=False, engine_password=None):
        self.disks.append({
            'size': '101G',
            'type': 'empty',
            'name': 'nfs',
            'dev': 'sda',
            'format': 'raw',
        })
        self.add_deploy_script('setup_nfs.sh')

        if iscsi:
            self.disks.append({
                'size': '101G',
                'type': 'empty',
                'name': 'iscsi',
                'dev': 'sdc',
                'format': 'raw',
            })
            self.add_deploy_script('setup_iscsi.sh')

        self.metadata['ovirt-engine-password'] = '123'
        if engine_password is not None:
            self.metadata['ovirt-engine-password'] = engine_password

        self.add_deploy_script('setup_engine.sh')
