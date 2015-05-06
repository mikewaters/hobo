import os
import pytest
import tempfile

from hobo.command import CommandSessionMixin, CommandSession, CommandError
from hobo.command import ParamDict
from hobo import config
from hobo.libvirt import Libguestfs, Libvirt
import hobo
from hobo.api import Hobo

def test_args():
    import argparse
    a = argparse.ArgumentParser()
    
    gg = a.add_mutually_exclusive_group()
    g1 = gg.add_argument_group('group1')
    gg.add_argument('--foo')
    g2 = gg.add_argument_group('group2')

    gg.add_argument('--bar')
    gg.add_argument('--baz')
    args = a.parse_args(['--foo=1', '--baz=2'])
    print args
def test_yml():
    import yaml
    with open('boxes.yml', 'r') as fh:

        print yaml.load(fh.read())

def test_build(monkeypatch):
    session = CommandSession(stream=True)
    def get_session():
        return session
    monkeypatch.setattr(hobo.api, 'CommandSession', get_session)
    ret = build(
        'mikewaters',
        'mike',
        'mikeiscool',
        '10G'
        '2048'
    )
    assert ret

def test_baseimg(monkeypatch):
    session = CommandSession(stream=True)
    def get_session():
        return session
    srcf = '/home/mike/hobo/test-inject'  #os.path.join(config.files_dir, 'test-inject')
    monkeypatch.setattr(hobo.api, 'CommandSession', get_session)
    ret = baseimg(
        'mike',
        'mike_os',
        'centos-6',
        firstboot=[srcf]
    )
    assert ret

def test_virt_build():
    sess = CommandSession(stream=True)
    pd = ParamDict()
    pd.add('firstboot', 'test-inject')

    pd.add('firstboot_command', "echo 'waters'")
    l = Libguestfs(session=sess,libvirt=Libvirt(images_dir='/tmp'))
    ret = l.virt_build('mike', 'centos-6', params=pd)
    assert ret

def test_vararg_unpacking():
    def unpack(*args, **kwargs):
        gnu = kwargs.pop('gnu', False)
        assert isinstance(gnu, bool)
        def _transform(argname):
            """Transform a python identifier into a 
            shell-appropriate argument name
            """
            if len(argname) == 1:
                return '-{}'.format(argname)

            return '--{}'.format(argname.replace('_', '-'))

        ret = []
        for k, v in kwargs.items():
            if isinstance(v, list):
                for item in v:
                    if gnu:
                        ret.append('{}={}'.format(
                            _transform(k),
                            str(item)
                        ))
                    else:
                        ret.extend([
                            _transform(k),
                            str(item)
                        ])
            else:
                if gnu:
                    ret.append('{}={}'.format(_transform(k), str(v)))
                else:
                    ret.extend([
                        _transform(k),
                        str(v)
                    ])

        if len(args): 
            for item in args:    
                ret.append(_transform(item))

        return ret

    def f(*args, **kwargs):
        print(unpack(*args, **kwargs))

    p = ParamDict()
    p.add('mike', '1')
    p.add('mike', 2)

    f('m', 'mikew', **p)
def test_arg_unpacking():
    raise Exception('unpack args moved')
    pd = ParamDict()

    pd.add('multiple', 'one')
    pd.add('multiple', 'two')
    pd['single'] ='arg'

    pos = ('v', 'flag')

    ret = unpack_args(pd, pos)

    assert ret == [
        '--multiple', 'one', 
        '--multiple', 'two',
        '--single', 'arg',
        '-v', '--flag'
    ]

    ret = unpack_args(pd, pos, gnu=True)

    assert ret == [
        '--multiple=one', 
        '--multiple=two',
        '--single=arg',
        '-v', '--flag'
    ]

def test_bad_template_file():
    raise Exception('no worky')
    badfile = """
[xx]
name=xxx
arch=x86_64
file=NOTFOUND.qcow2
format=qcow2
size=10739318784
"""
    sess = CommandSession()
    with tempfile.NamedTemporaryFile() as fh:
        fh.write(badfile)

        lf = Libguestfs(session=sess, template_file=fh.name)
        ret = lf.check_template_file()

        assert not ret

def test_libguestfs():
    sess = CommandSession()
    l = Libguestfs(session=sess)

    # centos-6 should always be install{ed,able} in a system
    # with libguestfs
    ret = l.template_available('centos-6')
    assert ret

    ret = l.template_available('xxx')
    assert not ret


def test_comand_session():
    class SessionTest(CommandSessionMixin):
        def call_echo(self, what):
            return self.session.call("echo '{}'".format(what))
        def check_echo(self, what):
            return self.session.check_output("echo '{}'".format(what))
        def call_exit(self, returncode):
            return self.session.call("exit {}".format(returncode))
        def check_exit(self, returncode):
            return self.session.check_output("exit {}".format(returncode))

    test = SessionTest()
    sess = CommandSession()
    test.session = sess

    ret = test.call_echo('hello')
    assert ret == 0
    assert len(sess.log) == 1
    assert sess.log[0][0] == "echo 'hello'"
    assert sess.log[0][1] == 0
    assert sess.log[0][2] == ['hello']
    assert sess.last_returncode == 0
    assert sess.output == 'hello'
    assert sess.last_error == ''

    ret = test.check_echo('hello')
    assert ret == 'hello'

    ret = test.call_exit(1)
    assert ret == 1

    with pytest.raises(CommandError):
        ret = test.check_exit(1)
        assert ex.returncode == 1
