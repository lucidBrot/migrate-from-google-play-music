#!/usr/bin/python
# -*- coding: utf-8 -*-
# Python version 3
import os, sys, csv
from dataclasses import dataclass
import re, difflib, sys, glob
from pprint import pprint, pformat

DEBUG_LINUX=True

# Path to "Takeout / Google Play Music / Playlists" as obtained from takeout.google.com
PLAYLISTS_PATH = os.path.normpath('N:\Files\Backups\GPM_export\Takeout\Google Play Music\Playlists')
if DEBUG_LINUX:
    print("WARNING: Debug flag is set to true!", file=sys.stderr)
    PLAYLISTS_PATH = os.path.normpath('./Google Play Music/Playlists')

# Path to where the local music resides. This will be recursively indexed using os.walk
# No idea if that follows symlinks.
MUSIC_PATH = os.path.normpath('N:\Files\Musik')
if DEBUG_LINUX:
    print("WARNING: Debug flag is set to true!", file=sys.stderr)
    MUSIC_PATH = os.path.normpath('Musik')

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
    return [song_tuple[0] for song_tuple in song_infos_sorted]

def find_match(trackname, possible_names):
    """
      Return None if no good match found, otherwise return the possible_names[i] that matched well.
    """
    # inspired by rhasselbaum's https://gist.github.com/rhasselbaum/e1cf714e21f00741826f
    # we're asking for exactly one match and set the cutoff quite low - i.e. the match must be good.
    close_matches = difflib.get_close_matches(trackname, possible_names, n=1, cutoff=0.1)
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
    print('\t verify how same songs from different albums/versions are handled')

def main():
    print("Considering any playlists in {}".format(PLAYLISTS_PATH))
    
    print("Collecting playlist directories...\n")
    subfolders = [ f.path for f in os.scandir(PLAYLISTS_PATH) if f.is_dir() ]
    playlists = list(filter_playlists(subfolders))
    for playlistpath in playlists:
        playlistname = os.path.basename(playlistpath)
        print("\tPlaylist: {}".format(playlistname))

    print("Indexing local music files...")
    local_music_files = [filpath for (_root, _dirs, filpath) in os.walk(MUSIC_PATH)]

    # it would make sense to operate on the filenames instead of the full paths on one hand. 
    # On the other hand, it would make things a bit harder to code, and we'd lose the info of directory names containing maybe band information. (That is not a good argument. My directories contain no useful info.)
    # So let's first try working on the full paths and see how it goes. I think/hope that in case of it going badly, we'd get no matches. I'm not certain if the behaviour of get_close_matches(n=1) is to choose a random one or to fail if there are multiple.

    print("Accumulating Contents...")
    unfound_songs = []
    for playlistpath in playlists:
        song_info_list_sorted = read_gpm_playlist(playlistpath)
        song_path_list = []
        for song_info in song_info_list_sorted:
            song_path = find_match("{artist}-{title}-{album}".format(title=song_info.title, artist=song_info.artist, album=song_info.album),
                local_music_files        
            )
            if song_path is None:
                print("No match found for {}".format(pformat(song_info)))
                unfound_songs.append(song_info)
            else:
                # We found the song path that belongs to this song_info!
                print("Matched {title} by {artist} from Album {album} to path {tpath}".format(
                    title=song_info.title, album=song_info.album, artist=song_info.artist,
                    tpath=song_path
                    ))
                

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'help':
        print("hello. Specify some things in the source file with the CAPS LOCKED variables!")
    else:
        main()
        print_todos()

