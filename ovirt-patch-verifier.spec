%{!?__python2: %global __python2 /usr/bin/python2}
%{!?python2_sitelib: %global python2_sitelib %(%{__python2} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")}
%{!?python2_sitearch: %global python2_sitearch %(%{__python2} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib(1))")}
%{!?py2_build: %global py2_build %{expand: CFLAGS="%{optflags}" %{__python2} setup.py %{?py_setup_args} build --executable="%{__python2} -s"}}
%{!?py2_install: %global py2_install %{expand: CFLAGS="%{optflags}" %{__python2} setup.py %{?py_setup_args} install -O1 --skip-build --root %{buildroot}}}

Version: 0.0.1
Release: 1%{?dist}
Name: python-ovirt-patch-verifier
Summary: Simple lago plugin to aid with patch verification
BuildArch: noarch
Group: System Environment/Libraries
License: GPLv2+
URL: https://github.com/rafaelmartins/ovirt-patch-verifier
Source0: https://github.com/rafaelmartins/ovirt-patch-verifier/releases/download/v%{version}/ovirt-patch-verifier-%{version}.tar.gz

BuildRequires: python2-devel
BuildRequires: python-setuptools
Requires: python-lago >= 0.33
Requires: python-ovirt-lago >= 0.33
Requires: python2-requests
Requires: ovirt-engine-sdk-python

%description
Simple lago plugin to aid with patch verification

%prep
%setup -q -n ovirt-patch-verifier-%{version}

%build
%py2_build

%install
%py2_install

%files

%doc LICENSE README.md
%{python2_sitelib}/ovirt_patch_verifier/*.py*
%{python2_sitelib}/ovirt_patch_verifier/answer-files/*.conf
%{python2_sitelib}/ovirt_patch_verifier/machines/*.py*
%{python2_sitelib}/ovirt_patch_verifier/machines/deploy-scripts/*.sh
%{python2_sitelib}/ovirt_patch_verifier-%{version}-py*.egg-info

%changelog
