#!/bin/bash -xe
set -xe
ISCSI_DEV="disk/by-id/scsi-0QEMU_QEMU_HARDDISK_3"
NUM_LUNS=5


install_deps() {
    systemctl disable --now kdump.service
    yum install -y --downloaddir=/dev/shm \
                   lvm2 \
                   targetcli \
                   sg3_utils \
                   iscsi-initiator-utils \
                   lsscsi
}


setup_iscsi() {
    pvcreate /dev/${ISCSI_DEV}
    vgcreate vg1_storage /dev/${ISCSI_DEV}
    targetcli /iscsi create iqn.2014-07.org.ovirt:storage
    targetcli /iscsi/iqn.2014-07.org.ovirt:storage/tpg1/portals \
        delete 0.0.0.0 3260
    targetcli /iscsi/iqn.2014-07.org.ovirt:storage/tpg1/portals \
        create ::0

    create_lun () {
       local ID=$1
        lvcreate -L20G -n lun${ID}_bdev vg1_storage
        targetcli \
            /backstores/block \
            create name=lun${ID}_bdev dev=/dev/vg1_storage/lun${ID}_bdev
        targetcli \
            /backstores/block/lun${ID}_bdev \
            set attribute emulate_tpu=1
        targetcli \
            /iscsi/iqn.2014-07.org.ovirt:storage/tpg1/luns/ \
            create /backstores/block/lun${ID}_bdev
    }


    for I in $(seq $NUM_LUNS);
    do
        create_lun $(($I - 1));
    done;

    targetcli /iscsi/iqn.2014-07.org.ovirt:storage/tpg1 \
        set auth userid=username password=password
    targetcli /iscsi/iqn.2014-07.org.ovirt:storage/tpg1 \
        set attribute demo_mode_write_protect=0 generate_node_acls=1 cache_dynamic_acls=1 default_cmdsn_depth=64
    targetcli saveconfig

    systemctl enable --now target
    sed -i 's/#node.session.auth.authmethod = CHAP/node.session.auth.authmethod = CHAP/g' /etc/iscsi/iscsid.conf
    sed -i 's/#node.session.auth.username = username/node.session.auth.username = username/g' /etc/iscsi/iscsid.conf
    sed -i 's/#node.session.auth.password = password/node.session.auth.password = password/g' /etc/iscsi/iscsid.conf

    iscsiadm -m discovery -t sendtargets -p 127.0.0.1
    iscsiadm -m node -L all
    rescan-scsi-bus.sh
    lsscsi -i |grep 36 |awk '{print $NF}' |sort > /root/multipath.txt
    iscsiadm -m node -U all
    iscsiadm -m node -o delete
    systemctl disable --now iscsi.service

}

main() {
    # Prepare storage
    install_deps
    setup_iscsi

    fstrim -va
}

main
