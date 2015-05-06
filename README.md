# README
note that data_files does not work with pip -e
## Install
### Ubuntu 14.10

    yum install nmap
    sudo chmod +r /boot/vmlinuz-`uname -r`  # ref: https://bugs.launchpad.net/ubuntu/+source/linux/+bug/759725

For jow, pip install --process-dependency-links -e ../hobo --upgrade until commandsession is in pypi

	chmod o+w /etc/virt-builder/repos.d
### Hacks
On ubuntu:


NOPE:
##Download libguestfs 1.29 and use /usr as prefix for ./configure,
##because the (old-ass) ubuntu package is installed there, but
##libguestfs defaults to /usr/local (so you will have two versions)
Just install package version


MAY Need to make libvirt images dir r/w/x for non-root users.
Currently thid means chmod 777.  

However, the right way to do this is to have libvirtd run
as a specific low-priv user, try specifying user/group in /etc/libvirt/qemu.conf.
^ didnt work, couldnt get the hypervisor to start.

see: http://libvirt.org/drvqemu.html#securityselinux
