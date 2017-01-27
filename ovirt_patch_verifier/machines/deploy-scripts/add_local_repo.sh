set -xe
DIST=$(uname -r | sed -r  's/^.*\.([^\.]+)\.[^\.]+$/\1/')
ADDR=$(ip -4 addr show scope global up |grep -m1 inet | awk '{split($4,a,"."); print a[1] "." a[2] "." a[3] ".1"}')

cat > /etc/yum.repos.d/local-ovirt.repo <<EOF
[alocalsync]
name=Latest oVirt nightly
baseurl=http://$ADDR:8585/$DIST/
enabled=1
skip_if_unavailable=1
gpgcheck=0
repo_gpgcheck=0
cost=1
keepcache=1
ip_resolve=4
EOF

sed -i "s/var\/cache/dev\/shm/g" /etc/yum.conf
echo "persistdir=/dev/shm" >> /etc/yum.conf
