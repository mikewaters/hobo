import os.path
import errno
from setuptools import setup

def get_xdg_hobo_config():
    #TODO: figure this out
    xdg_config_home = os.path.join(
        os.path.expanduser("~"), ".config", "hobo"
    )
    if not os.path.exists(xdg_config_home):
        
        try:
            os.makedirs(xdg_config_home)
        except OSError as ex:
            if ex.errno == errno.EEXIST and os.path.is_dir(xdg_config_home):
                pass
            else:
                raise
    return xdg_config_home

XDG_HOBO_HOME = get_xdg_hobo_config()
print XDG_HOBO_HOME
setup(
    name='hobo',
    entry_points={
        'console_scripts': ['hobo = hobo.cli:main'],
    },
    install_requires=['pyyaml', 'pyxdg', 'boltons', 'six', 'commandsession'],
    dependency_links=[
        "git+ssh://git@github.com/mikewaters/command-session.git#egg=commandsession-0.1",
    ],
    data_files=[
        (XDG_HOBO_HOME, ['build/hobo.ini'])
    ]
)
