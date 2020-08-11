#!/usr/bin/env python3

# Converts a list of audio tracks to corresponding files in a file system using fuzzy matching.
# Track names are read from standard input. For each, we try to find the best match to a
# file path under the current directory recursively. The best match is written to standard output.
# Optionally, a path prefix can be given as an argument to the script. If given, it will be
# prepended to each output file path (e.g. "/media/music/".

import re
import difflib
import sys
import glob
import os.path

# Get optional path prefix, which could be passed in as an argument.
path_prefix = sys.argv[1] if len(sys.argv) > 1 else ''

# Get list of paths to files under the current directory.
files = [file for file in glob.glob('**', recursive=True) if os.path.isfile(file)]

# Each line from standard input is expected to be a track name. Could have artist and album info, too.
for track in sys.stdin.readlines():
    # Here's the magic. Find the best match! Python is so awesome.
    close_matches = difflib.get_close_matches(track, files, n=1, cutoff=0.1)
    if close_matches:
        print("{0}{1}".format(path_prefix, close_matches[0]))
    else:
        print('!! NO MATCH: {0}'.format(track), file=sys.stderr)