from __future__ import print_function
import os
import sys
import time
import signal
import itertools
import subprocess

from commandsession import CommandError, CommandSession, ParamDict

from hobo.util import is_rh_family, Timeout, timeout, tempname, Config
from hobo.net import mac_in_arp_cache, populate_arp_cache, get_hostname
from hobo.libvirt import Libvirt, Libguestfs

config = Config()

class Hobo(object):
    """
    TODO:
        - refactor
        - better exception handling, and cleanup of templates
        - add vms to known_hosts
        - inject environment vars to debug libguestf (commandsession) 
    """
    images_dir = config.images_dir
    template_file = config.template_file
    db = config.db

    def __init__(self, verbose=False, debug=False):
        self.session = CommandSession(stream=verbose)
        self.libvirt = Libvirt(
            images_dir=self.images_dir,
            session=self.session
        )
        self.libgf = Libguestfs(
            template_file=self.template_file,
            libvirt=self.libvirt,
        )
        self.debug = debug
        self._check_template_file()

    def base(self, image_name, image_desc, base_os, upload=None, install=None, run=None, size=None, compress=True):
        """Generate a base os image built upon another base image.
        """

        if image_desc is None:
            image_desc = image_name

        if self.libgf.template_available(image_name):
            raise ValueError('Template for base image {} exists.'.format(image_name))

        if self.libvirt.disk_exists(image_name):
            raise ValueError('Disk for base image {} exists.'.format(image_name))
        
        params = ParamDict()

        if self.debug:
            params['root_password'] = '.hobo'

        if install: params['install'] = install

        if run:
            if not isinstance(run, list):
                run = [run]
            for item in run:
                assert os.path.exists(item)
                params.add('run', item)

        if upload:
            if not isinstance(upload, list):
                upload = [upload]
            for item in upload:
                params.add('upload', item)

        if size: params['size'] = size

        #TODO: add a keypair for root
        #params.add('run_command', 'cat /dev/zero | ssh-keygen -q -N ""')

        try:
            print('Building image')
            self.libgf.virt_build(
                image_name,
                base_os,
                # required for RHEL after messing around with authorized keys
                # might be able to use restorecon instead, in a run_command
                'selinux_relabel',
                **params
            )
        except (Exception, KeyboardInterrupt) as ex:
            try:
                self.libvirt.delete_disk(image_name)
            except: pass
            print(ex)
        else:

            try:

                image_path = self.libvirt.disk_path(image_name)
                print('Running sysprep')
                self.libgf.virt_sysprep_img(
                    ['udev-persistent-net'], image_name
                )

                image_sz = os.stat(os.path.join(image_path)).st_size
                ## compress the image?
                compressed_size = None
                if compress:
                    print('Compressing using {}'.format(config.compress_flags)
                    print('Warning: this can take a long time.')
                    _stream = self.session._stream
                    self.session._stream = True
                    self.session.call("xz {} {}".format(config.compress_flags, image_path))
                    self.session._stream = _stream
                    image_path = self.libvirt.disk_path(image_name) + '.xz'
                    compressed_size = os.stat(os.path.join(image_path)).st_size

                # manually remove this template from the cache, it is flaky 
                self.libgf.delete_cache(image_name)
                
                # get arch of base os to populate arch of our new image
                arch = self.libgf.get_arch(base_os)

                self.libgf.generate_template(
                    image_name,
                    image_desc,
                    arch,
                    image_sz,
                    self.template_file,
                    csz=compressed_size
                )
            except CommandError as ex:
                print(ex)
                raise
            except (Exception, KeyboardInterrupt) as ex:
                print(ex.message)
                # remove the image we created
                try:
                    #FIXME - sometimes this doesnt work
                    print('Cleanup after error')
                    self.session.call('rm -f {}'.format(image_path))
                except: pass
                raise

            print('Done building image')
            return True


    def build(self, base_os, name, hostname=None, size=None, ram=None, cpus=None, tags=None):
        """clone a base image
        TODO: the image for this clone should not go into the images dir, it should
        instead go into the current dirextory, or somewhere else.
        TODO: if size is not provided, get size somehow to store in db
        TODO: need to add users pubkey to auth keys automatically
        TODO: need to add a github privkey to the root account in v
        """

        params = ParamDict()
        
        if self.debug:
            params['root_password'] = '.hobo'

        if size:
            print((
                'Note: providing custom size requires virt-resize and virt-sparsify, '
                'so this may take some time.'
            ))
            params['size'] = size
        
        # inject user's pubkey
        pubkey = os.path.join(os.path.expanduser('~'), '.ssh', 'id_rsa.pub')
        assert os.path.exists(pubkey)
        #FIXME only supported on libguestfs >= 1.29
        #params['ssh_inject'] = 'root:file:{}'.format(pubkey)
        params.add('mkdir', '/root/.ssh')
        #FIXME: this will overwrite any existing authorized keys
        params.add('upload', "{}:/root/.ssh/authorized_keys".format(pubkey))
        params.add('run_command', "chmod 0700 /root/.ssh")
        params.add('run_command', "chmod 0600 /root/.ssh/authorized_keys")
        params.add('run_command', "chown root:root /root/.ssh/authorized_keys")
        params.add('run_command', "restorecon -FRvv /root/.ssh")
        
        bridge = config.bridge_device
        ram = ram or config.base_mem
        cpus = cpus or config.base_cpu
        hostname = hostname or '{}.local'.format(name)

        print('Importing image for {}'.format(name))
        self.libgf.virt_build(
            name,
            base_os,
            hostname=hostname,
            **params
        )
        
        try:
            if size:
                print('Creating sparse image')
                self.libgf.virt_sparsify(image_path)

            print('Creating domain')
            self.libgf.virt_import(
                name,
                name,
                bridge=bridge,
                ram=ram,
                vcpus=cpus
            )

            try:
                self.libvirt.get_domain(name)
            except ValueError:
                print('domain was not created!')
                raise

        except (Exception, KeyboardInterrupt):
            self.libvirt.delete_disk(name)
            raise

        else:
            if tags and not isinstance(tags, list):
                tags = [tags]
            elif not tags:
                tags = []

            self.db.write(
                'domains', 
                name,
                {
                    'user': 'root', 
                    'hostname': hostname,
                    'disk_size': size, 
                    'bridge_iface': bridge, 
                    'memory': ram, 
                    'cpus': cpus, 
                    'tags': tags
                }
            )

        return True

    def info(self, domain=None, format=None):
        """Print some info about a domain"""
        if not self.db.read('domains'):
            return False

        if domain:
            assert domain in self.db.read('domains').keys()
            domains = [domain]
        else:
            domains = self.db.read('domains').keys()

        records = {}
        for item in domains:
            domain_obj = self.libvirt.get_domain(item)
            state = domain_obj.state
            if not domain_obj.ip_address and state=='running':
                state = 'booting'

            info = self.db.read('domains', item)
            info.update({
                'mac': domain_obj.mac_address, 
                'ip': domain_obj.ip_address if state=='running' else '',  # if not running, it may not still have cached ip 
                'state': state
            })
            records[item] = info

        if not format:
            for k, v in records.items():
                print('{}: {}'.format(k, v))

        elif format == 'ansible':
            # generate a hosts file
            #MAYBE use inventory script
            def ansible_host(record):
                args = [record['hostname']]
                if record['user']: args.append('ansible_ssh_user={}'.format(record['user']))
                if record['ip']: args.append('ansible_ssh_host={}'.format(record['ip']))
                return ' '.join(args)

            running = [d for d in records.keys() if records[d]['state'] == 'running']
            for dom in running:
                rec = records[dom]
                print(ansible_host(rec))

            if len(running): print()

            tags = list(set(itertools.chain(*[t['tags'] for t in records.values()])))
            for tag in tags:
                matches = [k for k in records.keys() if tag in records[k]['tags'] and k in running]
                if len(matches):
                    print('[{}]'.format(tag))
                for dom in matches:
                    print(ansible_host(records[dom]))
                if len(matches):
                    print()

        return True

    def destroy(self, domain=None):
        """Remove a domain fro the system completely.
        :returns: False if all calls have failed, else True
        """
        if not self.db.read('domains'):
            print('No domains exist')
            return False

        if domain:
            assert domain in self.db.read('domains').keys()
            domains = [domain]
        else:
            domains = self.db.read('domains').keys()
        
        for domain in domains:
            try:
                self.session.call(
                    'virsh shutdown {}'.format(domain)
                )
                self.session.call(
                    'virsh destroy {}'.format(domain)
                )
                self.session.call(
                    'virsh undefine {}'.format(domain)
                )
                #FIXME
                self.session.call('rm -f /home/mike/hobo/images/{}.qcow2'.format(domain))
            except CommandError: pass
            finally:
                self.db.delete('domains', domain)

        print('{} deleted.'.format(domains))

        return True

    def _check_template_file(self):
        """Verify that template file is present, configured, and is well-formed."""
        #TODO: this is an install task, belongs in Makefile
        if not os.path.exists('/etc/virt-builder/repos.d/hobo.conf'):
            with open('/etc/virt-builder/repos.d/hobo.conf', 'w') as fh:
                fh.write('[hobo]\n')
                fh.write('uri=file:///{}\n'.format(
                    os.path.abspath(self.template_file)
                ))
                fh.write('proxy=off\n')

        # virt-builder will raise an error if existing template
        # file is not valid, but it will return a success error code,
        # which will allow this function to continue but eventually fail.
        if not self.libgf.check_template_file():
            raise RuntimeError('Base template file {}'.format(self.template_file))

