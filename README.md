# README
Hobo - do stuff.

## Install
Only ubuntu >=14.10 is currently working.

### Ubuntu 14.10
    
    ./install/ubuntu.sh

### Network bridge
Hobo requires a network bridge named 'hob0' (configurable).

#### Creating the bridge
Replace:

    auto em1
    iface em1 inet dhcp

With:
    auto em1
    iface em1 inet manual

    auto br0
    iface br0 inet dhcp
        bridge_ports em1
        bridge_stp off
        bridge_fd 0
        bridge_maxwait 0

#### Configuring the bridge

Add to /etc/sysctl.conf:

    net.bridge.bridge-nf-call-ip6tables = 0
    net.bridge.bridge-nf-call-iptables = 0
    net.bridge.bridge-nf-call-arptables = 0


Run:  

    sysctl -p /etc/sysctl.conf  

#### Using openvswitch
It's possible, see bridge-ovs.txt

### Local configuration
Keep site-specific config in local/ directory.
