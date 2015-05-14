import fcntl
import socket
import struct
import subprocess
try:
    from subprocess import DEVNULL # py3k
except ImportError:
    import os
    DEVNULL = open(os.devnull, 'wb')

def get_hostname():
    return(socket.gethostname())

def get_netmask(ifname):
    """Get the netmask for a given interface"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    return socket.inet_ntoa(fcntl.ioctl(
        s.fileno(),
        35099,
        struct.pack('256s', ifname)
    )[20:24])


def get_network_size(netmask):
    """Get cidr size of network from netmask"""
    b = ''
    for octet in netmask.split('.'):
        b += bin(int(octet))[2:].zfill(8)
    return str(len(b.rstrip('0')))


def get_network(ip, netmask):
    """Get network address from ip and netmask"""
    ip_octets = ip.split('.')
    nm_octets = netmask.split('.')
    return '.'.join(
        [str(int(ip_octets[x]) & int(nm_octets[x])) for x in range(0,4)]
    )


def cidr_calc(ip, netmask):
    """Calc cidr from netmask and ip."""
    return '{}/{}'.format(
        get_network(ip, netmask),
        get_network_size(netmask)
    )


def get_ip_address(ifname):
    """Get the ip for a given interface"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    return socket.inet_ntoa(fcntl.ioctl(
        s.fileno(),
        0x8915,  # SIOCGIFADDR
        struct.pack('256s', ifname[:15])
    )[20:24])


def mac_in_arp_cache(mac):
    """Determine if we know the ip of a given mac."""
    return bool(not subprocess.call(
        'arp -an |grep {}'.format(mac),
        shell=True, stdout=DEVNULL
    ))


def populate_arp_cache(dev='hob0'):
    """Scan the local subnet, which should populate arp cache.
    Cache duration is at cat /proc/sys/net/ipv4/neigh/default/gc_stale_time
    """
    cidr = cidr_calc(
        get_ip_address(dev),
        get_netmask(dev)
    )
    cmd = ['nmap', '-T5', '-sP', cidr]
    ret = subprocess.call(cmd, stdout=DEVNULL)
    if not ret == 0:
        print('nmap returned {}'.format(ret))
        return False

    return True
