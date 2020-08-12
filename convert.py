#!/usr/bin/python
# -*- coding: utf-8 -*-
# Python version 3

# `python convert.py
#  Computes everything!

# `python -c "import convert; convert.read_gpm_playlist('/path-to/Google Play Music/Playlists/MyPlaylistDir/')
#  Computes Songlist
#  Or to compute them all and save them as files, call `generate_songlists` with
# `N:\Files\Backups\GPM_export\Takeout>python -c "import convert; convert.generate_songlists();"`
import os, sys, csv
from dataclasses import dataclass
import re, difflib, sys, glob
from pprint import pprint, pformat
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3NoHeaderError
from enum import Enum

DEBUG_LINUX=(os.name=='posix')and True

# Path to "Takeout / Google Play Music / Playlists" as obtained from takeout.google.com
PLAYLISTS_PATH = os.path.normpath('N:\Files\Backups\GPM_export\Takeout\Google Play Music\Playlists')
if DEBUG_LINUX:
    print("WARNING: Debug flag is set to true!", file=sys.stderr)
    PLAYLISTS_PATH = os.path.normpath('./Google Play Music/Playlists')

# Path to where the local music resides. This will be recursively indexed using os.walk
# No idea if that follows symlinks.
MUSIC_PATH = os.path.normpath('N:\Files\Musik')
if DEBUG_LINUX:
    MUSIC_PATH = os.path.normpath('Musik')

class MatchSource(Enum):
    EXACT_TAG_MATCH = 1
    FUZZY = 2
    UNMATCHED = 3

@dataclass
class MatchTracker:
    match_counts = {}
    unmatched_songs = set()
    playlist_searches = {}
    fuzzy_details = {}

    def match(self, songinfo, path, match_source: MatchSource, fuzzy_info: str = None):
        self.match_counts[match_source] = self.match_counts.get(match_source, 0) + 1
        if match_source == MatchSource.FUZZY and fuzzy_info is not None:
            self.fuzzy_details[fuzzy_info] = self.fuzzy_details.get(fuzzy_info, 0) + 1


    def unmatch(self, songinfo):
        self.match(songinfo, None, MatchSource.UNMATCHED)
        self.unmatched_songs.add(songinfo)

    def increment_search_counter(self, playlist_basename):
        self.playlist_searches[playlist_basename] = self.playlist_searches.get(playlist_basename, 0) + 1

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

@dataclass(frozen=True)
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
        try:
            with open(song_csv, encoding="utf-8") as csvfile:
                rows = csv.reader(csvfile)
                for title, album, artist, duration_ms, rating, play_count, removed, playlist_index in rows:
                    if (title.strip() == 'Title') and (artist.strip() == 'Artist') and (album.strip() == 'Album'):
                        # skip headline
                        continue
                    print("Reading GPM  {} by {}.".format(title, artist))
                    song_info = SongInfo(title= title, album= album, artist= artist, liked= (rating == '5'))
                    song_infos_unsorted.append((song_info, playlist_index))
        except UnicodeEncodeError as e:
            print("INFO: Skipping file {} due to Unicode Reading Error.".format(song_csv))

    # sort playlist by index
    song_infos_sorted = sorted(song_infos_unsorted, key=lambda x: x[1])
    return [song_tuple[0] for song_tuple in song_infos_sorted]

def generate_songlists(mdir=PLAYLISTS_PATH, outdir='./songlists'):
    subfolders = [ f.path for f in os.scandir(PLAYLISTS_PATH) if f.is_dir() ]
    playlists = list(filter_playlists(subfolders))
    os.makedirs(os.path.normpath(outdir), exist_ok=True)
    for playlistpath in playlists:
        song_info_list_sorted = read_gpm_playlist(playlistpath)
        playlistname = os.path.basename(os.path.normpath(playlistpath))
        playlistpath = os.path.join(outdir, playlistname)
        with open("{}.txt".format(playlistpath), 'w+', encoding="utf-8") as sfile:
            for info in song_info_list_sorted:
                sfile.write("{artist} - {title} - {album}\n".format(artist=info.artist, title=info.title, album=info.album))


def find_match(trackname, possible_names):
    """
      Return None if no good match found, otherwise return the possible_names[i] that matched well.
    """
    # inspired by rhasselbaum's https://gist.github.com/rhasselbaum/e1cf714e21f00741826f
    # we're asking for exactly one match and set the cutoff quite high - i.e. the match must be good.
    close_matches = difflib.get_close_matches(trackname, possible_names, n=1, cutoff=0.2)
    if close_matches:
        return close_matches[0]
    else:
        return None

def print_todos(f=sys.stderr):
    print("\n--- TODOS ---", file=f)
    print("\t handle the Thumbs Up playlist.", file=f)
    print("\t check for surprising cases with more than two rows in a song csv", file=f)
    print("\t consider the info in the tags on the music files for matching better", file=f)
    print("\t implement caching of file matches", file=f)
    print('\t verify how same songs from different albums/versions are handled', file=f)
    print("\t Maybe try matching with different formats or names?", file=f)
    print("\t Compare audios directly?", file=f)
    print("\t replace dashes and such with whitespace for fuzzy matching?", file=f)
    print("\t query Shazam?", file=f)
    
@dataclass
class FileTag:
    artist: str
    album: str
    title: str

    def is_everything_unset(self):
        if self.artist or self.album or self.title:
            # at least one thing is set
            if (self.artist == "") and (self.album == "") and (self.title== ""):
                return True # everything empty string counts as unset
            else:
                return False
        else:
            return True # no part is set

    def set_parts_equal(self, artist, title, album):
        result = True
        if self.artist:
            result = result and (self.artist == artist)
        if self.title:
            result = result and (self.title == title)
        if self.album:
            result = result and (self.album == album)
        return result

@dataclass
class FileInfo:
    full_path: str
    filename: str
    tag: FileTag = None

    def get_plain_filename(self):
        return os.path.splitext(self.filename)[0]

    def is_tag_set(self):
        return not (True if self.tag is None else self.tag.is_everything_unset())

def debug_m(track, music_path=MUSIC_PATH):
    local_music_file_infos = [FileInfo(filename=filpath, full_path=os.path.join(dirpath, filpath)) for (dirpath, _dirs, filpaths) in os.walk(music_path) for filpath in filpaths ]
    local_music_files=map(lambda x: x.get_plain_filename(), local_music_file_infos)
    a=find_match(track, local_music_files)
    print(a if a else "No match")

def find_exact_tag_match(local_music_file_infos, song_info, tracker: MatchTracker):
    """
        Returns True if an exact match was found, False otherwise.
        When the first exact match is found, the search calls match and returns.
    """
    for music_file_info in local_music_file_infos:
        ##print("[{}] checking {} step 1".format(song_info.title, music_file_info.filename))
        if music_file_info.is_tag_set():
            ##print("[{}] checking {} step 2".format(song_info.title, music_file_info.filename))
            tag = music_file_info.tag
            if tag.set_parts_equal(artist=song_info.artist, title=song_info.title, album=song_info.album):
                # The tags exactly match!
                print("Exact Match for {title} by {artist} from Album {album} at path {tpath}".format(title=song_info.title, album=song_info.album, artist=song_info.artist, tpath=music_file_info.full_path))
                tracker.match(song_info, music_file_info.full_path, MatchSource.EXACT_TAG_MATCH)
                return True
            else:
                ##print("[{}] checking {} step 3".format(song_info.title, music_file_info.filename))
                ##print("Tags did not match. SongInfo vs Tag:")
                ##pprint(song_info)
                ##pprint(tag)
                pass
    return False

def find_fuzzy_match(local_music_files, song_info, searchterm: str, tracker: MatchTracker):
    """
        Return True if found, false otherwise. If found, calls match.
    """
    song_path = find_match(searchterm.format(title=song_info.title, artist=song_info.artist, album=song_info.album),
        local_music_files        
    )
    if song_path is None:
        return False
    else:
        # We found the song path that belongs to this song_info!
        print("Matched {title} by {artist} from Album {album} to path {tpath}".format(
            title=song_info.title, album=song_info.album, artist=song_info.artist,
            tpath=song_path
            ))
        tracker.match(song_info, song_path, MatchSource.FUZZY, fuzzy_info = searchterm)
        return True

def main():
    tracker = MatchTracker()
    print("Considering any playlists in {}".format(PLAYLISTS_PATH))
    
    print("Collecting playlist directories...\n")
    subfolders = [ f.path for f in os.scandir(PLAYLISTS_PATH) if f.is_dir() ]
    playlists = list(filter_playlists(subfolders))
    for playlistpath in playlists:
        playlistname = os.path.basename(playlistpath)
        print("\tPlaylist: {}".format(playlistname))

    print("Indexing local music files...")
    local_music_file_infos = [FileInfo(filename=filpath, full_path=os.path.join(dirpath, filpath)) for (dirpath, _dirs, filpaths) in os.walk(MUSIC_PATH) for filpath in filpaths ]
    local_music_files=map(lambda x: x.get_plain_filename(), local_music_file_infos)

    print("Indexing local music file tags...")
    for file_info in local_music_file_infos:
        try:
            # the returns from mutagen are lists, that's why the index 0 everywhere.
            tag=EasyID3(file_info.full_path)
            file_info.tag = FileTag(artist=(tag['artist'][0] if 'artist' in tag else ''), album=(tag['album'][0] if 'album' in tag else ''), title=(tag['title'][0] if 'title' in tag else ''))
        except ID3NoHeaderError:
            # This is not a music file or has no tags
            file_info.tag = None
    

    # it would make sense to operate on the filenames instead of the full paths on one hand. 
    # but how to keep track of the actual paths?

    print("Accumulating Contents...")
    for playlistpath in playlists:
        print("Accumulating Contents for Playlist {}".format(os.path.basename(playlistpath)))
        song_info_list_sorted = read_gpm_playlist(playlistpath)
        song_path_list = []
        for song_info in song_info_list_sorted:
            # count number of playlist searches for debugging
            tracker.increment_search_counter(os.path.basename(playlistpath))
            # try exact tag matching
            found_exact_match = find_exact_tag_match(local_music_file_infos, song_info, tracker)
            if found_exact_match:
                continue

            # try fuzzy filename matching in various orders
            # artist, title, album
            found_fuzzy_match_by_artist_title_album = find_fuzzy_match(local_music_files, song_info, "{artist}{title}{album}", tracker)
            if found_fuzzy_match_by_artist_title_album:
                continue

            # artist, title
            found_fuzzy_match_by_artist_title = find_fuzzy_match(local_music_files, song_info, "{artist}{title}", tracker)
            if found_fuzzy_match_by_artist_title:
                continue

            # artist, album, title
            found_fuzzy_match_by_artist_album_title = find_fuzzy_match(local_music_files, song_info, "{artist}{album}{title}", tracker)
            if found_fuzzy_match_by_artist_album_title:
                continue

            # title
            found_fuzzy_match_by_title = find_fuzzy_match(local_music_files, song_info, "{title}", tracker)
            if found_fuzzy_match_by_title:
                continue

            # if we're still here, no match has been found for this song.
            tracker.unmatch(song_info)

    print("\nFuzzy Stats: \n{}".format(pformat(tracker.fuzzy_details)))
    print("\nFound Matches Statistics:\n{}".format(pformat(tracker.match_counts)))
    print("\nSearched Playlists Statistics:\n{}".format(pformat(tracker.playlist_searches)))
                

if __name__ == '__main__':
    if len(sys.argv) > 1:
        if sys.argv[1] == 'help':
            print("hello. Specify some things in the source file with the CAPS LOCKED variables!")
            print("If you're running this in Windows CMD, you might need to `set PYTHONIOENCODING=utf-8` first.")
            print("It is probably advisable to pipe the stdout into a file so that the important messages from STDERR surface clearly.")
        if sys.argv[1] == 'here':
            print("using current directory {} as MUSIC_PATH".format(os.getcwd()))
            MUSIC_PATH = os.getcwd()

    # always:
    main()
    print_todos()

