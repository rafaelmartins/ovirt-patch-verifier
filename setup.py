#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

setup(
    name='ovirt-patch-verifier',
    version='0.0.1',
    license='GPL-3',
    description='A lago plugin to help with ovirt patch verification',
    author='Rafael Martins',
    author_email='rmartins@redhat.com',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'configparser',
        'lago',
        'requests',
    ],
    entry_points={
        'lago.plugins.cli': [
            'opv = ovirt_patch_verifier:OvirtPatchVerifierCLI',
        ],
        'lago.plugins.opv.cli': [
            'deploy = ovirt_patch_verifier:do_deploy',
            'destroy = ovirt_patch_verifier:do_destroy',
        ],
    },
)
