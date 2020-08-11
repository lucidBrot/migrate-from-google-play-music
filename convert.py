#!/usr/bin/python
# -*- coding: utf-8 -*-
# Python version 3
import os, sys, csv
from dataclasses import dataclass
import re, difflib, sys, glob

# Path to "Takeout / Google Play Music / Playlists" as obtained from takeout.google.com
PLAYLISTS_PATH = os.path.normpath('N:\Files\Backups\GPM_export\Takeout\Google Play Music\Playlists')

# Path to where the local music resides. This will be recursively indexed using os.walk
# No idea if that follows symlinks.
MUSIC_PATH = os.path.normpath('N:\Files\Musik')

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
            print("\tInvalid: {}".format(folder), file=sys.stderr)
        if valid:
            yield(folder)

@dataclass
class SongInfo:
    """
      Basically a Named Tuple for storing info of a song
    """
    title: str
    artist: str
    liked: bool
    album: str

def read_gpm_playlist(playlistdir):
    """
      Returns a list of song names contained in a GPM Takeout Playlist
    """
    song_infos_unsorted = []
    tracks_path = os.path.join(playlistdir, 'Tracks')
    # Expected contents of that directory is one file per song, 
    # each file csv-formatted and containing something like this:
    # 
    # Title,Album,Artist,Duration (ms),Rating,Play Count,Removed,Playlist Index
    # "The Show","Lenka","Lenka","235728","5","24","","4"
    # <newline>
    
    song_csvs = [ f.path for f in os.scandir(tracks_path) if f.is_file() ]
    for song_csv in song_csvs:
        with open(song_csv, encoding="utf-8") as csvfile:
            rows = csv.reader(csvfile)
            for title, album, artist, duration_ms, rating, play_count, removed, playlist_index in rows:
                if (title.strip() == 'Title') and (artist.strip() == 'Artist') and (album.strip() == 'Album'):
                    # skip headline
                    continue
                print("reading {} by {}.".format(title, artist))
                song_info = SongInfo(title= title, album= album, artist= artist, liked= (rating == '5'))
                song_infos_unsorted.append((song_info, playlist_index))

    # sort playlist by index
    song_infos_sorted = sorted(song_infos_unsorted, key=lambda x: x[1])
    return song_infos_sorted

def find_match(inputname, possible_names):
    """
      Return None if no good match found, otherwise return the possible_names[i] that matched well.
    """
    # inspired by rhasselbaum's https://gist.github.com/rhasselbaum/e1cf714e21f00741826f
    # we're asking for exactly one match and set the cutoff quite low - i.e. the match must be good.
    close_matches = difflib.get_close_matches(track, files, n=1, cutoff=0.1)
    if close_matches:
        return close_matches[0]
    else:
        return None

def print_todos():
    print("\n--- TODOS ---")
    print("\t handle the Thumbs Up playlist.")
    print("\t check for surprising cases with more than two rows in a song csv")
    print("\t consider the info in the tags on the music files for matching better")
    print("\t implement caching of file matches")

def main():
    print("Considering any playlists in {}".format(PLAYLISTS_PATH))
    
    print("Collecting playlist directories...\n")
    subfolders = [ f.path for f in os.scandir(PLAYLISTS_PATH) if f.is_dir() ]
    playlists = list(filter_playlists(subfolders))
    for playlistpath in playlists:
        playlistname = os.path.basename(playlistpath)
        print("\tPlaylist: {}".format(playlistname))

    print("Indexing local music files...")
    local_music_files = os.walk(MUSIC_PATH)

    # it would make sense to operate on the filenames instead of the full paths on one hand. 
    # On the other hand, it would make things harder to code, and we'd lose the info of directory names containing maybe band information.
    # So let's first try working on the full paths.

    print("Accumulating Contents...")
    for playlistpath in playlists:
        song_info_list_sorted = read_gpm_playlist(playlistpath)
        song_path_list = []
        for song_info in song_info_list_sorted:
            song_path = find_match("{title}-{artist}".format(title=song_info.title, artist=song_info.artist),
                local_music_files        
            )

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'help':
        print("hello. Specify some things in the source file!")
    else:
        main()
        print_todos()

