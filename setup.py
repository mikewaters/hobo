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

setup(
    name='hobo',
    version='0.1',
    description="Wrapper around libguestfs/libvirt for specific workflow.",
    author="Mike Waters",
    author_email='robert.waters@gmail.com',
    url='https://github.com/mikewaters/hobo',
    packages=[
        'hobo',
    ],
    package_dir={'hobo': 'hobo'},
    include_package_data=True,
    license="MIT",
    zip_safe=False,
    keywords='hobo',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
    ],
    entry_points={
        'console_scripts': ['hobo = hobo.cli:main'],
    },
    install_requires=['pyyaml', 'pyxdg', 'boltons', 'six', 'commandsession'],
    data_files=[
        (XDG_HOBO_HOME, ['build/hobo.ini'])
    ]
)
