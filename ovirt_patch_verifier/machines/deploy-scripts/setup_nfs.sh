#!/bin/bash -xe
set -xe
MAIN_NFS_DEV="disk/by-id/scsi-0QEMU_QEMU_HARDDISK_2"

setup_device() {
    local device=$1
    local mountpath=$2
    mkdir -p ${mountpath}
    mkfs.xfs -K /dev/${device}
    echo -e "/dev/${device}\t${mountpath}\txfs\tdefaults,discard\t0 0" >> /etc/fstab
    mount /dev/${device} ${mountpath}
}

setup_nfs() {
    local exportpath=$1
    mkdir -p ${exportpath}
    chmod a+rwx ${exportpath}
    echo "${exportpath} *(rw,sync,no_root_squash,no_all_squash)" >> /etc/exports
    exportfs -a
}


setup_main_nfs() {
    setup_device ${MAIN_NFS_DEV} /exports/nfs
    setup_nfs /exports/nfs/share1
}


setup_export() {
    setup_nfs /exports/nfs/exported
}


setup_iso() {
    setup_nfs /exports/nfs/iso
}


install_deps() {
    systemctl disable --now kdump.service
    yum install -y --downloaddir=/dev/shm \
                   nfs-utils \
                   rpcbind
}

disable_firewalld() {
    if rpm -q firewalld > /dev/null; then
            systemctl disable --now firewalld || true
    fi
}

setup_services() {
    systemctl disable --now postfix
    systemctl disable --now wpa_supplicant
    disable_firewalld

    # Allow use of NFS v4.2. oVirt still uses 4.1 though
    sed -i "s/RPCNFSDARGS=\"\"/RPCNFSDARGS=\"-V 4.2\"/g" /etc/sysconfig/nfs

    systemctl enable --now rpcbind.service
    systemctl enable --now  nfs-server.service
    systemctl start nfs-lock.service
    systemctl start nfs-idmap.service
}

main() {
    # Prepare storage
    install_deps
    setup_services
    setup_main_nfs
    setup_export
    setup_iso

    fstrim -va
}

main
