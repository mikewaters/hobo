import os
from six.moves import input
import yaml
from copy import deepcopy
from argparse import ArgumentParser

from hobo.api import Hobo


def main():
    """cli entry point.
    """
    argparser = ArgumentParser()
    argparser.add_argument('--verbose', action='store_true', help='stream stdout/stderr', default=False)
    argparser.add_argument('--debug', action='store_true', help='debug', default=False)

    subparsers = argparser.add_subparsers(dest='command')

    base_parser = subparsers.add_parser(
        'base',
        help="Prepare a base image to clone from"
    )
    base_parser.add_argument(
        'image_name',
        help='Name of resultant image.'
    )
    base_parser.add_argument(
        'image_desc',
        help='Image description.'
    )
    base_parser_grp = base_parser.add_mutually_exclusive_group(required=True)
    
    base_parser_grp.add_argument(
        '--base-os', dest='base_os',
        help='Desired os/platform to base image on.'
    )
    base_parser.add_argument(
        '--install', 
        help='Packages to install.'
    )
    base_parser.add_argument(
        '--run', nargs='?', action='append',
        help='Scripts to run.'
    )
    base_parser.add_argument(
        '--upload', nargs='?', action='append',
        help='Files to upload.'
    )
    base_parser.add_argument(
        '--size',
        help='Disk size of image.'
    )

    base_parser_grp.add_argument(
        '--from-file', dest='image_file',
        help='Use base image template from file.'
    )
    base_parser.add_argument(
        '--template',
        help='Which template to use from file'
    )


    build_parser = subparsers.add_parser('build')
    build_parser.add_argument(
        'base_os',
        help='Desired os/platform for build.'
    )
    build_parser.add_argument(
        '--name',
        help='Domain names. Multiple names will create additional domains.'
    )
    build_parser.add_argument(
        '--size',
        help='Desired image size.'
    )
    build_parser.add_argument(
        '--hostname',
        help='Desired hostname.'
    )
    build_parser.add_argument(
        '--ram',
        help='memory.'
    )
    build_parser.add_argument(
        '--cpus',
        help='Num cpus.'
    )
    build_parser.add_argument(
        '--tags', nargs='?', action='append',
        help='Tags.'
    )

    info_parser = subparsers.add_parser('info')
    info_parser.add_argument(
        '--domain',
        help='Which domain to check out.'
    )
    info_parser.add_argument(
        '--format',
        help='output format.'
    )

    destroy_parser = subparsers.add_parser('destroy')
    destroy_parser.add_argument(
        '--domain',
        help='Which domain to delete.'
    )

    args = vars(argparser.parse_args())
    
    verbose = args.pop('verbose')
    debug = args.pop('debug')
    command = args.pop('command')

    # Perform some extra arg validation crapola that is
    # tough to do with argparse.
    if command == 'base' and 'image_file' in kwargs:
        # read data from yaml file instead of cli
        assert os.path.exists(kwargs['image_file'])

        if not kwargs['template']:
            print('--template is required with --from-file')
            return False

        template = args.pop('template')
        image_file = args.pop('image_file')

        with open(image_file, 'r') as yml:
            templates = yaml.load(yml.read())
            if template not in templates:
                print('template not found')
                return False

            for k, v in templates[template].items():
                args[k] = v

    elif command == 'base':
        if kwargs['template']:
            print('--template not supported unless --image-file')
            return False

    if command == 'destroy' and not args.get('domain'):
        print('danger, will robinson:')
        resp = input('y/n')
        if not resp.strip() == 'y':
            return

    hobo = Hobo(verbose=verbose, debug=debug)
    func = getattr(hobo, command)
    return func(**args)


