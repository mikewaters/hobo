#TODO: implement cahed_property, but only if the return value is
# available (ip address is an expensive lookup and may fail)
import os
import six
import time
import subprocess
from copy import deepcopy

from commandsession import CommandSessionMixin

from hobo.util import cached_property, mkdir_all
from hobo.net import mac_in_arp_cache, populate_arp_cache

__all__ = ['Libvirt', 'Libguestfs']

LIBVIRT_IMAGES_DIR = '/var/lib/libvirt/images'

class Libguestfs(CommandSessionMixin):

    def __init__(self, template_file=None, libvirt=None, session=None):
        assert not session, 'do i need this feature?'
        if not libvirt:
            self.libvirt = Libvirt()
        else:
            self.libvirt = libvirt
        super(Libguestfs, self).__init__(session or self.libvirt.session)

    def get_arch(self, os_version):
        """Get the arch for a given os template."""

        cmd = "virt-builder --list |grep {} |awk '{{print $2}}'".format(os_version)
        out = self.session.check_output(cmd)
        return out

    def list_templates(self):
        return self.session.check_output(
            ['virt-builder', '--list']
        )

    def check_template_file(self):
        """Check to see if template file is valid.
        virt-builder will fail if there is a missing image or something.
        Sometimes it fails with a returncode of 0, sometimes not.  wtf?"""
        ret, output = self.session._exec(
            ['virt-builder', '--list']
        )
        # if returncode is nonzero, fail
        if not ret == 0:
            return False

        # if returncode is zero, but error is in stdout, fail
        try:
            output.index('parse error')
        except ValueError:
            return True

        return False

    def template_available(self, os_version):
        """Discover whether or not an os template is available."""
        """Get the arch for a given os template."""
        returncode = self.session.call(
            "virt-builder --list |grep {}".format(os_version)
        )
        return returncode==0

    def get_os_template_info(self, template):
        """Wrapper for virt-builder --list
        :returns: list [name, arch, description] or None
        """
        templates = self.session.check_output(
            "virt-builder --list"
        )
        
        for row in templates.splitlines():
            record = row.split()
            if record[0] == template:
                return record

    def generate_template(self, image_name, image_desc, arch, image_sz, template_file, csz=None):
        """Add an os template to the template file.
        There are more fields that I am not using, see:
            http://libguestfs.org/virt-builder.1.html#create-the-templates
        """
        #TODO: write this atomically, so the record can be removed if there
        # is a problem

        template = '\n'.join((
            "[{name}]",
            "name={desc}",
            "arch={arch}",
            "file={path}",
            "format={fmt}",
            "size={size}",
            #TODO is this always the same? what are the preconditions?
            "expand={expand}"
        ))
        if csz:
            template = template + "\ncompressed_size={csize}"
        template = template + '\n'

        image_path = self.libvirt.disk_path(image_name)
        #TODO: can use qemu-img info <path> to get this info
        #image_sz = os.stat(os.path.join(image_path)).st_size

        with open(template_file, 'a') as fh:
            fh.write(template.format(
                name = image_name, 
                desc = image_desc,
                arch = arch, 
                # this is expected to be a path *relative* to this file
                path = '{}.qcow2{}'.format(image_name, '.xz' if csz else ''), 
                fmt = 'qcow2',
                size = image_sz,
                csize = csz,
                expand = '/dev/vda3',
            ))
            fh.write('\n')  # required

        if not self.check_template_file():
            raise RuntimeError('Template corrupt, image file may be bad')

    def delete_cache(self, template=None):
        """Delete a template from the cache"""
        #TODO: delete only selected template, by parsing --print-cache
        self.session.call(['virt-builder', '--delete-cache'])

    def virt_sysprep_img(self, operations, image_name):
        """Run sysprep on an image.
        :param operations: list of sysprep ops
        :param image_name: the image to operate upon
        """
        if not operations:
            return True

        args = [
            '--operations', ' '.join(operations),
        ]

        args.extend([
            '-a', os.path.join(
                self.libvirt.images_dir, 
                '{}.qcow2'.format(image_name)
            )
        ])

        cmd = ['virt-sysprep']
        cmd.extend(args)
        return self.session.call(cmd) == 0

    def virt_build(self, img_name, base_image, *flags, **params):
        """Run virt-builder to create a disk image using appropriate os base.
        :param flags, kwargs: extra arguments to pass to virt-builder
        """
        if self.libvirt.disk_exists(img_name):
            raise ValueError('error: disk {} already exists'.format(img_name))

        args = self.session.unpack_args(*flags, **params)
        args.extend([
            #'--root-password', 'password:ihateguestfish',
            '--network',
            '--format', 'qcow2',
            '--output', '{}.qcow2'.format(
                os.path.join(self.libvirt.images_dir, img_name)),
        ])
        cmd = ['virt-builder', base_image]
        cmd.extend(args)
        #ret, output = self.session._exec(cmd)
        
        # virt-builder return exit 0 on some failures...
        #if not ret == 0 or 'virt-builder: exception' in output:
        #    return False

        #return True
        return self.session.check_call(cmd) == 0

    def virt_import(self, domain_name, img_name, *flags, **params):
        """Run virt-install --import to create a domain based on an image."""
        args = self.session.unpack_args(*flags, **params)
        args.extend([
            #'--bridge', BRIDGE_DEV,
            #'--ram', BASE_MEM,
            ###'--cpu', 'host',
            #'--vcpus', BASE_CPU,
            '--nographics',
            ###'--os-type', 'linux',
            '--force',
            '--noreboot',
            '--name', domain_name,
            '--disk', 'path={},size=10,bus=virtio,format=qcow2'.format(
                self.libvirt.disk_path(img_name)
            )
        ])
        cmd = ['virt-install', '-d', '--import']
        cmd.extend(args)
        return self.session.check_call(cmd) == 0

    def virt_sparsify(self, img_path):
        """Sparsify an image
        """
        sparse = img_path + '.sparse'

        cmd = ['virt-sparsify', '--compress', img_path, sparse]  
        self.session.check_call(cmd)
        os.rename(sparse, img_path)


class NotBooted(Exception):
    pass


class Domain(CommandSessionMixin):

    def __init__(self, name, session=None):
        super(Domain, self).__init__(session)
        self.name = name
        if not self.exists:
            raise ValueError('invalid domain name')
        self.states = [(time.time(), self.state)]

    def stop(self):
        """Check if a domain is running."""
        if self.running:
            cmd = ['virsh', 'shutdown', self.name]
            self.session.check_call(cmd)

        # update state if no error occurred
        self._update_state()

    def start(self):
        """Check if a domain is running."""
        if not self.running:
            cmd = ['virsh', 'start', self.name]
            self.session.check_call(cmd)

        # update state if no error occurred
        self._update_state()

    def undefine(self):
        """Undefine a domain."""
        if self.running:
            self.stop()

        cmd = ['virsh', 'undefine', self.name]
        self.session.check_call(cmd)
        self._update_state('undefined')

    def _update_state(self, state=None):
        """Update state table with given state or current state."""
        self.states.append((
            time.time(), state or self.state
        ))

    def was(self, state):
        """Was the domain in a given state, as far as we are aware?"""
        return state in [
            s[1] for s in self.states
        ]

    def ping(self):
        return self.session.call('ping {}'.format(
            self.ip_address
        )) == 0

    @property
    def state(self):
        """Get current state."""
        cmd = "virsh list --all | grep {}".format(self.name)
        output = self.session.check_output(cmd)
        # assume the domain exists
        return ' '.join(output.split()[2:])

    @property
    def stopped(self):
        return self.state == 'shut off'

    @property
    def running(self):
        return self.state == 'running'

    @property
    def exists(self):
        """Check if a domain is created."""
        cmd = "virsh list --all | grep {}".format(self.name)
        return self.session.check_call(cmd) == 0

    @property
    def booted(self):
        """See if a domain has booted yet, by checking if it's available
        on the network.
        """
        #DONTUSE
        if self.ping():
            return True

        mac = self.mac_address

        # if we don't have the domain's mac address in local arp cache,
        # try to populate the arp cache.  if it's still not cached.
        # assume the domain's network iface is not up yet.
        if not mac_in_arp_cache(mac):
            populate_arp_cache()

        return mac_in_arp_cache(mac)

    @property
    def mac_address(self):
        """Get the mac address of a domain.
        TODO: suppress the priting of the mac address when stream=True,
        or at least add a newline or something. This is called in a long loop .
        """
        cmd = "virsh domiflist {} |grep {} |awk '{{print $5}}' |perl -pe 'chomp'".format(
            self.name, config.bridge_device
        )

        return self.session.check_output(cmd)

    @property
    def ip_address(self):
        """get the IP for a domain.
        Harder than you think, if you are using a bridge.
        """
        #if not self.booted:
        #    raise NotBooted

        mac = self.mac_address
        # if we don't have the domain's mac address in local arp cache,
        # try to populate the arp cache.  if it's still not cached.
        # assume the domain's network iface is not up yet.
        if not mac_in_arp_cache(mac):
            populate_arp_cache()

        cmd = "arp -an |grep {} |awk '{{print $2}}' |sed 's/[()]//g' |perl -pe 'chomp'".format(mac)
        return self.session.check_output(cmd)
        

    def Qsetcpu(self, cpu):
        #stub
        #http://earlruby.org/2014/05/increase-a-vms-vcpu-count-with-virsh/
        pass

    def Qsetmem(self, mem):
        """Set memiry for a domain."""
        if not self.stop():
            _warn('could not stop domain {}'.format(self.name))
            return False

        cmd = ['virsh', 'setmaxmem', self.name, str(mem), '--config']
        ret = subprocess.call(cmd)
        if not ret == 0:
            _warn('setmaxmem error {}'.format(ret))
            return False

        cmd = ['virsh', 'setmem', self.name, str(mem), '--config']
        ret = subprocess.call(cmd)
        if not ret == 0:
            _warn('setmem error {}'.format(ret))
            return False

        return True

class Libvirt(CommandSessionMixin):

    def __init__(self, images_dir=None, session=None):
        super(Libvirt, self).__init__(session)
        self.images_dir = images_dir or LIBVIRT_IMAGES_DIR
        if not os.path.exists(self.images_dir):
            mkdir_all(self.images_dir)

    def get_domain(self, name):
        return Domain(name, session=self.session)

    def get_domains(self, running=True):
        """Get a list of all current domains."""
        cmd = ['virsh', 'list']
        if not running:
            cmd.append('--all')

        ret = self.session.check_output(cmd)
        data = [row.split() for row in ret.split('\n')[2:] if row]
        return data

    def check_perms(self):
        """Check if user can access libvirt images directory.
        :raises: RuntimeError if failed.
        """
        cmd = ['test', '-r', self.images_path]
        ret = self.session.call(cmd)
        if ret:
            # libvirt not installed, or we are not root
            raise RuntimeError('error reading libvirt images directory')

    def disk_path(self, name):
        return os.path.join(
            self.images_dir, 
            '{}.qcow2'.format(name)
        )

    def disk_exists(self, name):
        """Check if a domain backing disk exists."""
        cmd = ['test', '-f', self.disk_path(name)]
        return self.session.call(cmd) == 0

    def delete_disk(self, name):
        os.remove(self.disk_path(name))

    def undefine_with_prejudice(self, domain):
        """Undefine a domain.
        This functionality exists on Domain obj also, but
        this impl takes a scorched-earth approach.
        """
        self.session.call(['virsh', 'shutdown', domain])
        self.session.call(['virsh', 'destroy', domain])
        self.session.check_call(['virsh', 'undefine', domain])
        self._update_state('undefined')
