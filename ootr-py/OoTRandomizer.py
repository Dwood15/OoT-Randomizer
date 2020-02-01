#!/usr/bin/env python3
import argparse
import datetime
import logging
import os
import textwrap
import time
from ctypes import *

from Main import main, from_patch_file, cosmetic_patch
from Settings import get_settings_from_command_line_args
from Utils import local_path

zig_lib = "../zig-cache/lib/libOoT-Randomizer.so"


class ArgumentDefaultsHelpFormatter(argparse.RawTextHelpFormatter):

    def _get_help_string(self, action):
        return textwrap.dedent(action.help)


def start():
    zig_funcs = CDLL(zig_lib)
    print(type(zig_funcs))

    res = zig_funcs.add(1, 2)
    print("add res: ")
    print(res)
    print("num_args: ")
    print(zig_funcs.num_args())

    settings, gui, args_loglevel, no_log_file = get_settings_from_command_line_args(zig_funcs)

    # set up logger
    loglevel = {'error': logging.ERROR, 'info': logging.INFO, 'warning': logging.WARNING, 'debug': logging.DEBUG}[args_loglevel]
    logging.basicConfig(format='%(message)s', level=loglevel)

    logger = logging.getLogger('')

    if not no_log_file:
        ts = time.time()
        st = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H-%M-%S')
        log_dir = local_path('Logs')
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        log_path = os.path.join(log_dir, '%s.log' % st)
        log_file = logging.FileHandler(log_path)
        log_file.setFormatter(logging.Formatter('[%(asctime)s] %(message)s', datefmt='%H:%M:%S'))
        logger.addHandler(log_file)

    try:
        if settings.cosmetics_only:
            cosmetic_patch(settings)
        elif settings.patch_file != '':
            from_patch_file(settings)
        elif settings.count != None and settings.count > 1:
            orig_seed = settings.seed
            for i in range(settings.count):
                settings.update_seed(orig_seed + '-' + str(i))
                main(settings, zig_funcs)
        else:
            main(settings, zig_funcs)
    except Exception as ex:
        logger.exception(ex)


if __name__ == '__main__':
    start()
