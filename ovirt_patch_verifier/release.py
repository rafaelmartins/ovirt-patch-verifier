import os
import re
import StringIO
import subprocess
import tarfile
import tempfile

import requests


class OvirtRelease(object):

    RESOURCES_BASE_URL = 'http://plain.resources.ovirt.org/pub/yum-repo/'

    def __init__(self, version):
        self.version = None
        for rpm, _version in self.get_available_releases():
            if version == _version:
                self.version = _version
                self.rpm = rpm
        if self.version is None:
            raise RuntimeError('Invalid release version: %s' % version)

    @classmethod
    def get_available_releases(cls):
        '''Returns a tuple for each release: First item is the RPM file name,
        second item is the release version'''

        r = requests.get(cls.RESOURCES_BASE_URL)
        r.raise_for_status()
        for match in re.finditer(r'[\'"](ovirt-release-?([^\'"]+).rpm)[\'"]',
                                 r.content):
            yield match.groups()

    def _fetch(self):
        r = requests.get(self.RESOURCES_BASE_URL + self.rpm)
        r.raise_for_status()
        rpm_files = ''
        with tempfile.NamedTemporaryFile() as tmp:
            tmp.file.write(r.content)
            tmp.file.flush()
            try:
                rpm_files = subprocess.check_output(
                    'rpm2cpio %s | cpio -idmv' % tmp.name,
                    shell=True,
                    stderr=subprocess.STDOUT,
                )
            except subprocess.CalledProcessError as e:
                raise RuntimeError((
                    'Failed to extract RPM, maybe you don\'t have rpm2cpio '
                    'installed: %s') % e)
        for f in rpm_files.splitlines():
            f = f.strip()
            if f.endswith('.repo'):
                filename = os.path.basename(f)
                with open(f) as fp:
                    filecontent = fp.read()
                yield filename, filecontent

    def get_repofile(self, distver):
        dist = None
        snapshot = None
        dependencies = None
        dependencies_fname = None

        fc_match = re.match(r'fc([0-9]{2})', distver)
        if fc_match is not None:
            dist = 'fc'
            dependencies_fname = 'ovirt-f%s-deps.repo' % fc_match.group(1)
        if re.match(r'el([0-9]+)', distver):
            dist = 'el'
            dependencies_fname = 'ovirt-%s-deps.repo' % distver

        if dist is None:
            raise RuntimeError('Invalid distver: %s', distver)

        for fname, content in self._fetch():
            if fname == dependencies_fname:
                dependencies = content
            elif fname == 'ovirt-snapshot.repo':
                snapshot = content.replace('@DIST@', dist)
                snapshot = snapshot.replace('@URLKEY@', 'mirrorlist')

        if dependencies is None:
            raise RuntimeError('Failed to find repofile for distro: %s' %
                               distver)

        file_content = dependencies
        if snapshot is not None:
            file_content += '\n'
            file_content += snapshot

        rv = tempfile.NamedTemporaryFile(delete=False)

        with rv as fp:
            fp.write(dependencies)
            if snapshot is not None:
                fp.write('\n')
                fp.write(snapshot)

        return rv.name
