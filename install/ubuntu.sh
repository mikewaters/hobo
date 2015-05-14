#!/bin/bash

# Base install of hobo.
# This does not install hob0 bridge, as I do not want to
# break somebody's network in a script.
#
# Only ubuntu >=utopic/14.10 supported currently, as there
# is a minimum required version of libguestfs-tools
#
#TODO verify required version >=1.26 of guestfish
#
# @mikewaters 

if [[ $EUID -ne 0 ]]; then
    echo "error: root required"
    exit 1
fi

apt-get -y --force-yes install nmap libguestfs-tools bridge-utils virtinst

# Set up the local virt-builder OS template file
if [[ ! -d /etc/virt-builder/repos.d/ ]]; then
    echo 'error: libguestfs-tools install error?'
    exit 1
fi
if [[ ! -f /etc/virt-builder/repos.d/hobo.conf ]]; then
    cat << EOF > /etc/virt-builder/repos.d/hobo.conf
[hobo]
uri=file://${HOME}/.local/share/hobo/images/hobo.templates
proxy=off
EOF
fi

# virt-builder must be able to read kernel image
# ref: https://bugs.launchpad.net/ubuntu/+source/linux/+bug/759725
chmod +r /boot/vmlinuz-`uname -r`

# virt-builder requires user have permission on /dev/kvm
#usermod -aG kvm `logname`  # may not work if using `sudo su -`
#^^DOESNT WORK, USING NUCLEAR OPTION
chmod 0666 /dev/kvm


