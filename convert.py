#!/usr/bin/python
# -*- coding: utf-8 -*-
# Python version 3
import os, sys

# Full Path to "Takeout / Google Play Music / Playlists" as obtained from takeout.google.com
PLAYLISTS_PATH = os.path.normpath('N:\Files\Backups\GPM_export\Takeout\Google Play Music\Playlists')

def filter_playlists(subfolders):
    """
      Returns folder paths which look like a valid playlist export
    """
    for folder in subfolders:
        valid=True
        # check for existence of Metadata.csv
        if not os.path.isfile(os.path.join(folder, 'Metadata.csv')):
            valid=False
        if not os.path.isdir(os.path.join(folder, 'Tracks')):
            valid=False
        if not valid:
            print("\tInvalid: {}".format(folder))
        if valid:
            yield(folder)

def main():
    print("Considering any playlists in {}".format(PLAYLISTS_PATH))
    
    print("Collecting playlist directories...")
    subfolders = [ f.path for f in os.scandir(PLAYLISTS_PATH) if f.is_dir() ]
    playlists_generator = filter_playlists(subfolders)
    for playlistpath in playlists_generator:
        print("\Playlist: {}".format(playlistpath))

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'help':
        print("hello. Specify some things in the source file!")
    else:
        main()

