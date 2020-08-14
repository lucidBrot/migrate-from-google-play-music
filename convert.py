#!/usr/bin/python
# -*- coding: utf-8 -*-
# Python version 3

# `python convert.py > out.txt`
#  Computes everything!
#  Note: Not always will the best bitrate file be chosen. when the files match well enough, we don't consider all the files.

# `python -c "import convert; convert.read_gpm_playlist('/path-to/Google Play Music/Playlists/MyPlaylistDir/')`
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
import mutagen
from datetime import datetime
import html
import json
import shutil, filecmp
import hashlib

DEBUG_LINUX=(os.name=='posix')and False
USE_UNRELIABLE_METHODS = False
IGNORE_MUSIC_FOLDERS=['@eaDir']
HANDLE_THUMBS_UP=True
# Note that path settings are relative to the current working directory if you don't specify absolute paths.
OUTPUT_PLAYLIST_DIR=os.path.normpath('output_playlists')
OUTPUT_PLAYLIST_DIR_RELATIVE=os.path.normpath('N:\Files\Musik\playlists_relative')
MAKE_PLAYLISTS_RELATIVE_TO_OUTPUT_PLAYLIST_DIR=True
SAVE_ABSOLUTE_PLAYLISTS=True # No harm done in always keeping this True
DELETE_REDUNDANT_FILES_IN_MUSIC_PATH=False

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
COPY_FALLBACK_GPM_MUSIC=True
COPY_FALLBACKS_TO_PATH=os.path.normpath(os.path.join(MUSIC_PATH, "2020", "gpm-migration"))

# Path to where the export from GPM resides.
# Files are assumed to be lower quality
# Also add any other fallback paths here.
GPM_FALLBACK_TRACK_PATHS = [
        os.path.normpath('N:\Files\Backups\GPM_export\Takeout\Google Play Music\Tracks'),
        os.path.normpath('F:\PlayMusic'),
        ]

# For de-duplication of the music library
# Set this to true only if you are willing to wait a long time for the script to run.
# Also, not well tested.
I_AM_SCARED_OF_HASH_COLLISIONS=False

class MatchSource(Enum):
    EXACT_TAG_MATCH = 1
    FUZZY = 2
    UNMATCHED = 3
    FUZZY_TAG_MATCH = 4
    TAGS_CONTAIN = 5
    PATH_CONTAINS = 6
    SUBSTRING_TAG_MATCH = 7

@dataclass()
class Playlist:
    """
        After collecting, the data must be SOMEWHERE. Here.
    """
    name: str
    content: list = None
    # Either fully qualified paths or a placeholder for later correction. Anything that is not a path MUST start with PLACEHOLDER
    PLACEHOLDER = "PLACEHOLDER:"

    def add(self, line: str):
        if self.content is None:
            self.content = []

        if line is None:
            raise ValueError("Playlist line may never be None.")

        self.content.append(line)

    def get_content(self):
        if self.content is None:
            return []
        else:
            return self.content

    def update_placeholders(self, new_info):
        if self.content is None:
            self.content = []

        print("Updating placeholders for Playlist {}...".format(self.name))
    
        for i in range(len(self.content)):
            if self.content[i].startswith(Playlist.PLACEHOLDER):
                key = self.content[i][len(Playlist.PLACEHOLDER):]
                self.content[i] = new_info.get(key, self.content[i])

    def debug_isabs_check(self):
        for elem in self.content:
            if not os.path.isabs(elem):
                print("-- {} --\n".format(os.path.isabs(os.path.abspath(elem))))
            assert os.path.isabs(elem), "[Playlist {}]: {} failed the check. It should have been {}".format(self.name, elem, os.path.abspath(elem))


@dataclass
class MatchTracker:
    match_counts : dict
    unmatched_songs : set
    playlist_searches : dict
    fuzzy_details : dict
    num_songs_missing : dict
    subbed_songs : set # for tracking substitutions, so that the user can verify their correctness.

    def __init__(self):
        self.match_counts = {}
        self.unmatched_songs = set()
        self.playlist_searches = {}
        self.fuzzy_details = {}
        self.subbed_songs = set()
        self.num_songs_missing = {}


    def match(self, songinfo, path, match_source: MatchSource, playlist: Playlist, fuzzy_info: str = None):
        self.match_counts[match_source] = self.match_counts.get(match_source, 0) + 1
        if match_source == MatchSource.FUZZY and fuzzy_info is not None:
            self.fuzzy_details[fuzzy_info] = self.fuzzy_details.get(fuzzy_info, 0) + 1
        if match_source == MatchSource.SUBSTRING_TAG_MATCH:
            self.subbed_songs.add(songinfo)
        # store result
        if playlist != None:
            playlist.add(path)

    def unmatch_for_playlist(self, playlist):
        """
            Keeps track of which playlists are incomplete.
        """
        self.num_songs_missing[playlist] = self.num_songs_missing.get(playlist, 0) + 1

    def unmatch(self, songinfo, playlist: Playlist):

        self.match(songinfo, "{}{}".format(Playlist.PLACEHOLDER, pformat(songinfo)), MatchSource.UNMATCHED, playlist=playlist)
        self.unmatched_songs.add(songinfo)

    def increment_search_counter(self, playlist_basename):
        self.playlist_searches[playlist_basename] = self.playlist_searches.get(playlist_basename, 0) + 1

def print_todos(f=sys.stderr):
    print("\n--- TODOS ---", file=f)
    print("\t Check for surprising cases with more than two rows in a song csv. (In my 4000 test cases this never occurred)", file=f)
    print("\t Implement caching of file matches across playlists?", file=f)
    print("\t Find duplicate files in music library and suggest deletion of all but the best one.", file=f)

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
            if os.path.split(folder)[1] != "Thumbs up":
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
    title_stripped: str

def strip_title(title):
    if title is None:
        return ""
    t = re.sub('\d\d\d\d\d+', '', title)
    t = re.sub('.mp3', '', t)
    t = re.sub('.flac', '', t)
    return t

def read_gpm_playlist(playlistdir, trackdir='Tracks'):
    """
      Returns a list of song names contained in a GPM Takeout Playlist
    """
    song_infos_unsorted = []
    tracks_path = os.path.join(playlistdir, trackdir)
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
                    # clean up google's htmlencoding mess
                    title = html.unescape(title)
                    album = html.unescape(album)
                    artist = html.unescape(artist)

                    print("Reading GPM  {} by {}.".format(title, artist))
                    song_info = SongInfo(title= title, album= album, artist= artist, liked= (rating == '5'),
                            title_stripped=strip_title(title))
                    song_infos_unsorted.append((song_info, playlist_index))
        except UnicodeEncodeError as e:
            print("INFO: Skipping file {} due to Unicode Reading Error.".format(song_csv))

    # sort playlist by index
    song_infos_sorted = sorted(song_infos_unsorted, key=lambda x: x[1])
    return [song_tuple[0] for song_tuple in song_infos_sorted]

def generate_songlists(mdir=PLAYLISTS_PATH, outdir='./songlists', handle_thumbs_up=HANDLE_THUMBS_UP):
    subfolders = [ f.path for f in os.scandir(mdir) if f.is_dir() ]
    playlists = list(filter_playlists(subfolders))
    os.makedirs(os.path.normpath(outdir), exist_ok=True)
    for playlistpath in playlists:
        song_info_list_sorted = read_gpm_playlist(playlistpath)
        playlistname = os.path.basename(os.path.normpath(playlistpath))
        playlistpath = os.path.join(outdir, playlistname)
        with open("{}.txt".format(playlistpath), 'w+', encoding="utf-8") as sfile:
            for info in song_info_list_sorted:
                sfile.write("{artist} - {title} - {album}\n".format(artist=info.artist, title=info.title, album=info.album))
    # now handle the Thumbs up playlist
    if handle_thumbs_up:
        sils = read_gpm_playlist(mdir, trackdir='Thumbs up')
        playlistname='Thumbs up'
        playlistpath = os.path.join(outdir, playlistname)
        with open("{}.txt".format(playlistpath), 'w+', encoding="utf-8") as sfile:
            for info in sils:
                sfile.write("{artist} - {title} - {album}\n".format(artist=info.artist, title=info.title, album=info.album))



def find_match(trackname, possible_names, cutoff=0.3):
    """
      Return None if no good match found, otherwise return the possible_names[i] that matched well.
    """
    # inspired by rhasselbaum's https://gist.github.com/rhasselbaum/e1cf714e21f00741826f
    # we're asking for exactly one match and set the cutoff quite high - i.e. the match must be good.
    close_matches = difflib.get_close_matches(trackname, possible_names, n=1, cutoff=cutoff)
    if close_matches:
        return close_matches[0]
    else:
        return None
    
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

    def update_tag_from_fs(self):
        newly_loaded_tag = False
        try:
            # the returns from mutagen are lists, that's why the index 0 everywhere.
            tag=EasyID3(self.full_path)
            self.tag = FileTag(artist=(tag['artist'][0] if 'artist' in tag else ''), album=(tag['album'][0] if 'album' in tag else ''), title=(tag['title'][0] if 'title' in tag else ''))
            newly_loaded_tag = True
        except ID3NoHeaderError:
            # This is not a music file or has no tags
            self.tag = None
            try:
                # OOOr maybe it is a FLAC file instead of an mp3 file
                # or anything else... let the library guess...
                tag = mutagen.File(self.full_path)
                if tag is not None:
                    self.tag = FileTag(artist=(tag['artist'][0] if 'artist' in tag else ''), album=(tag['album'][0] if 'album' in tag else ''), title=(tag['title'][0] if 'title' in tag else ''))
                    newly_loaded_tag = True
            except mutagen.mp3.HeaderNotFoundError as err:
                self.tag = None # happens. "can't sync to MPEG frame" is the ~800th check, so it's probably just not a music file.

        if newly_loaded_tag:
            # Need to transform "&quot;", "&amp;" and similar because locally this is stored correctly in the tags.
            self.tag.title = html.unescape(self.tag.title)
            self.tag.album = html.unescape(self.tag.album)
            self.tag.artist = html.unescape(self.tag.artist)

def debug_m(track, music_path=MUSIC_PATH):
    local_music_file_infos = [FileInfo(filename=filpath, full_path=os.path.abspath(os.path.join(dirpath, filpath))) for (dirpath, _dirs, filpaths) in os.walk(music_path) for filpath in filpaths ]
    local_music_files=map(lambda x: x.get_plain_filename(), local_music_file_infos)
    a=find_match(track, local_music_files)
    print(a if a else "No match")

def find_exact_tag_match(local_music_file_infos, song_info, tracker: MatchTracker, playlist):
    """
        Returns True if an exact match was found, False otherwise.
        When the first exact match is found, the search calls match and returns.
    """
    for music_file_info in local_music_file_infos:
        if music_file_info.is_tag_set():
            tag = music_file_info.tag
            if tag.set_parts_equal(artist=song_info.artist, title=song_info.title, album=song_info.album):
                # The tags exactly match!
                print("Exact Tag Match for {title} by {artist} from Album {album} at path {tpath}".format(title=song_info.title, album=song_info.album, artist=song_info.artist, tpath=music_file_info.full_path))
                tracker.match(song_info, music_file_info.full_path, MatchSource.EXACT_TAG_MATCH, playlist=playlist)
                return True
            else:
                ##print("[{}] checking {} step 3".format(song_info.title, music_file_info.filename))
                ##print("Tags did not match. SongInfo vs Tag:")
                ##pprint(song_info)
                ##pprint(tag)
                pass
    return False

def find_substring_tag_match(fallback_music_file_infos, song_info, fallback_tracker, playlist: Playlist):
    for music_file_info in fallback_music_file_infos:
        if music_file_info.is_tag_set():
            tag = music_file_info.tag
            if tag.title in song_info.title:
                if (not tag.album) or (not song_info.album) or tag.album in song_info.album:
                    if (not tag.artist) or (not song_info.artist) or tag.artist in song_info.artist:
                        print("Substring Tag Match for {title} by {artist} from Album {album} at path {tpath}".format(title=song_info.title, album=song_info.album, artist=song_info.artist, tpath=music_file_info.full_path))
                        fallback_tracker.match(song_info, music_file_info.full_path, MatchSource.SUBSTRING_TAG_MATCH, playlist=playlist)
                        return True

    return False


def find_fuzzy_tag_match(local_music_file_infos, song_info, tracker: MatchTracker, playlist: Playlist):
    possibilities = ["{}{}".format(mf_info.tag.title, mf_info.tag.artist) for mf_info in local_music_file_infos if mf_info.is_tag_set()]
    found = find_match("{}{}".format(song_info.title, song_info.artist), possibilities, cutoff=0.4)
    if found is not None:
        found_music_file_infos = list(filter(
                lambda mfi: mfi.is_tag_set() and ("{}{}".format(mfi.tag.title, mfi.tag.artist) == found),
                local_music_file_infos))
        found_path = found_music_file_infos[0]
        # but just because this matches does not yet mean it's valid. E.g. "Vitas - My Swan" matched "Starset - My Demons"...
        print("Fuzzy Tag Match for {title} by {artist} from Album {album} to path {tpath}".format(
                title=song_info.title, album=song_info.album, artist=song_info.artist, tpath=found_path
            ))
        tracker.match(song_info, found_path, MatchSource.FUZZY_TAG_MATCH, playlist=playlist)
        return True
    return False

def find_fuzzy_match(local_music_file_infos, song_info, searchterm: str, tracker: MatchTracker, playlist: Playlist):
    """
        Return True if found, false otherwise. If found, calls match.
    """
    song_name = find_match(searchterm.format(title=song_info.title, artist=song_info.artist, album=song_info.album, cutoff=0.3),
        [f.filename for f in local_music_file_infos]
    )
    if song_name is None:
        return False
    else:
        # We found the song path that belongs to this song_info!
        song_path = [f.full_path for f in local_music_file_infos if f.filename == song_name][0]
        print("Fuzzy Match for {title} by {artist} from Album {album} to path {tpath}".format(
            title=song_info.title, album=song_info.album, artist=song_info.artist,
            tpath=song_path
            ))
        tracker.match(song_info, song_path, MatchSource.FUZZY, fuzzy_info = searchterm, playlist = playlist)
        return True

def x_fuzzily_contains_y(x:str, y:str):
    """
        checks if all parts of x are somewhat in y
    """
    if y is None:
        return False
    if x is None: 
        return False
    xx = x.lower().replace('&amp;', '&').replace('&#39;',"'").replace('&quot;','"')
    # split on non-word characters of any amount, or underscore, or dash (included in non-word characters)
    splitmagic='[\W_]+'
    yys = [ item for item in re.split(splitmagic,y.lower().replace('&amp;', '&').replace('&#39;', "'").replace('&quot;', '"')) if item != '' ]
    if all([yy in xx for yy in yys]):
        return True
    else:
        return False

def best_bitrate_file(mfi_filelist):
    if len(mfi_filelist) < 1:
        return None
    fl = [(mutagen.File(item.full_path).info.bitrate, item) for item in mfi_filelist]
    sl = sorted(fl, reverse=True, key=lambda x:x[0])
    return sl[0][1]

def kinda_equal(a, b):
    return x_fuzzily_contains_y(a,b) and x_fuzzily_contains_y(b,a)

def tags_contain_info(local_music_file_infos, song_info, tracker, playlist: Playlist):
    """
        Return True if a match found
    """
    found_mfi_options = []
    for mfi in local_music_file_infos:
        if mfi.is_tag_set():
            # only check the options that are set. If no tags are set, we ignore the file. The title is required. But artist and album not.
            good=False
            if x_fuzzily_contains_y(x=mfi.tag.title, y=song_info.title):
                if (not mfi.tag.artist) or (not song_info.artist) or x_fuzzily_contains_y(x=mfi.tag.artist, y=song_info.artist):
                    if (not mfi.tag.album) or (not song_info.artist) or x_fuzzily_contains_y(x=mfi.tag.album, y=song_info.album):
                        good=True
            if good:
                found_mfi_options.append(mfi)
    num_found =  len(found_mfi_options)
    if num_found == 1:
        print("TCInfo found match for {title} by {artist} from Album {album} to path {tpath}".format(
            title=song_info.title, artist=song_info.artist, album=song_info.album, tpath=found_mfi_options[0].full_path
            ))
        tracker.match(song_info, found_mfi_options[0].full_path, MatchSource.TAGS_CONTAIN, playlist=playlist)
        return True
    else:
        if num_found > 1:
            print("TCI found {n} options for {title} by {artist} from Album {album}:\n\t{options}".format(
                n=num_found, title=song_info.title, artist=song_info.artist, album=song_info.album,
                options = pformat(list(map(lambda x: x.full_path, found_mfi_options)))
                ))
            if len(found_mfi_options) < 20: # just so we dont take too long
                if all([kinda_equal(a.filename,b.filename) for a in found_mfi_options for b in found_mfi_options]):
                    best_bitrate_f = best_bitrate_file(found_mfi_options)
                    print("... choosing the best bitrate file: {}".format(best_bitrate_f.full_path))
                    tracker.match(song_info, best_bitrate_f.full_path, MatchSource.TAGS_CONTAIN, playlist=playlist)
                    return True
        return False

def filepath_contains_info(local_music_file_infos, song_info, tracker, playlist: Playlist):
    found_mfi_options = []
    for mfi in local_music_file_infos:
        if x_fuzzily_contains_y(x=mfi.full_path, y=song_info.title):
            if x_fuzzily_contains_y(x=mfi.full_path, y=song_info.artist) \
            or x_fuzzily_contains_y(x=mfi.full_path, y=song_info.album):
                found_mfi_options.append(mfi)

    num_found= len(found_mfi_options)
    if num_found == 1:
        print("PathInfo found match for {title} by {artist} from Album {album} to path {tpath}".format(
            title=song_info.title, artist=song_info.artist, album=song_info.album, tpath=found_mfi_options[0].full_path
            ))
        tracker.match(song_info, found_mfi_options[0].full_path, MatchSource.PATH_CONTAINS, playlist=playlist)
        return True
    else:
        if num_found > 1:
            print("PathI found {n} options for {title} by {artist} from Album {album}:\n\t{options}".format(
                n=num_found, title=song_info.title, artist=song_info.artist, album=song_info.album,
                options = pformat(list(map(lambda x: x.full_path, found_mfi_options)))
                ))
            if len(found_mfi_options) < 20: # just so we dont take too long
                if all([kinda_equal(a.filename,b.filename) for a in found_mfi_options for b in found_mfi_options]):
                    best_bitrate_f = best_bitrate_file(found_mfi_options)
                    print("... choosing the best bitrate file: {}".format(best_bitrate_f.full_path))
                    tracker.match(song_info, best_bitrate_f.full_path, MatchSource.PATH_CONTAINS, playlist=playlist)
                    return True
            
        return False

def folders_of_path(folderpath):
    return os.path.normpath(folderpath).split(os.sep)

def is_ignored(folder):
    path = os.path.normpath(folder)
    folders= folders_of_path(path)
    return any([item in folders for item in IGNORE_MUSIC_FOLDERS])

def save_playlist_files(playlists: list, outdir=OUTPUT_PLAYLIST_DIR):
    """
        Takes a List<Playlist> and writes it out to files.
    """
    os.makedirs(os.path.normpath(outdir), exist_ok=True)
    for playlist in playlists:
        pfile = os.path.join(outdir, "{}.m3u".format(playlist.name))
        with open(pfile, "w+", encoding="utf-8") as outfile:
            for line in playlist.get_content():
                outfile.write(line+"\n")

def complete_playlists_interactively(playlists: list):
    """
        Asks user for inputs for the missing paths and returns an updated list.
        Modifies the Playlists!
    """
    user_specifiable_mappings = {}
    infostring="SPECIFY_PATH_HERE"
    jsonfile="_missing_matches.json"
    for playlist in playlists:
        plcontent = playlist.get_content()
        for entry in plcontent:
            if entry.startswith(Playlist.PLACEHOLDER):
                user_specifiable_mappings[entry[len(Playlist.PLACEHOLDER):]] = infostring
    
    if len(user_specifiable_mappings) > 0:
        need_more_input=True
    else:
        need_more_input=False
        print("Don't require any user input. Found everything!")

    while need_more_input:
        print("looping because need more input...")
        try:
            with open(os.path.join(OUTPUT_PLAYLIST_DIR, jsonfile), "r", encoding="utf-8") as jsf:
                # read previous content
                try:
                    data = json.load(jsf)
                except json.decoder.JSONDecodeError as e:
                    data = {}
                    pass
                #print("JSON data read: \n{}\n".format(pformat(data)))
        except FileNotFoundError:
            #print("JSON file did not yet exist")
            data = {}


        # include that content as specified by the user
        print("Loading preexisting data...")
        for key, value in data.items():
            user_specifiable_mappings[key] = os.path.normpath(value)

        # do we still need user input after this?
        need_more_input=False
        for key, value in user_specifiable_mappings.items():
            if value is None or value == "" or value == infostring:
                print("Need info for {}".format(key))
                need_more_input = True

        if need_more_input:
            with open(os.path.join(OUTPUT_PLAYLIST_DIR, jsonfile), "w", encoding="utf-8") as jsf:
                # write out.
                data_to_write=json.dumps(user_specifiable_mappings, indent=4)
                #print("JSON DATA TO WRITE: \n{}\n".format(data_to_write))
                jsf.write(data_to_write)
                print("Need more inputs in file _missing_matches.json!", file=sys.stderr)
            input("Press ENTER when ready")

    print("No more inputs needed by user!")
    for playlist in playlists:
        playlist.update_placeholders(user_specifiable_mappings)

    return playlists

def path_a_in_b(a, b):
    """
        Not considering symbolic links... be careful with them.
    """
    aa = os.path.normpath(a)
    bb = os.path.normpath(b)
    return aa.startswith(os.path.abspath(bb) + os.sep) or aa == bb

def copy_files_over(playlists: list, targetdir=COPY_FALLBACKS_TO_PATH, musicdir=MUSIC_PATH):
    """
        Copy files to path unless they are located in the musicpath already.
        Modifies the Playlists!
    """
    os.makedirs(os.path.normpath(targetdir), exist_ok=True)
    for playlist in playlists:
        for i in range(len(playlist.content)):
            entry = playlist.content[i]
            if not path_a_in_b(entry, musicdir):
                # copy file
                filename = os.path.basename(entry)
                target_path = os.path.normpath(os.path.join(targetdir, filename))
                if not os.path.exists(target_path) or not filecmp.cmp(target_path, entry):
                    shutil.copyfile(os.path.normpath(entry), target_path)
                # update playlist
                playlist.content[i] = target_path

    return playlists

def relativate_playlists(abs_playlists: list, relative_to=OUTPUT_PLAYLIST_DIR_RELATIVE):
    """
       COPY Playlists to use relative paths 
    """
    rel_playlists = []
    for abs_playlist in abs_playlists:
        rel_playlist = Playlist(name=abs_playlist.name)
        rel_playlists.append(rel_playlist)
        rel_playlist.content = []
        for abspath in abs_playlist.content:
            try:
                # create relative path. This could fail.
                relpath = os.path.relpath(abspath, start=relative_to)
                # transform to forward slashes
                pl_line = relpath.replace('\\', '/')
                rel_playlist.content.append(pl_line)
            except ValueError as ve:
                # target is probably on a different drive.
                print("Target path {abspath} cannot be translated to a relative path. Is it on a different drive than {mus} is? Consider activating the Copying from Fallback Dirs".format(abspath=abspath, mus=relative_to), file=sys.stderr)
                raise ve

    return rel_playlists

def debug_create_lmfi_sans_tags():
    return [FileInfo(filename=filpath, full_path=os.path.abspath(os.path.join(dirpath, filpath))) for (dirpath, _dirs, filpaths) in os.walk(MUSIC_PATH) for filpath in filpaths if not is_ignored(dirpath) ]

def compute_redundant_files(local_music_file_infos, folder=MUSIC_PATH, BUF_SIZE=2*65536):
    """
        The files aren't that big, so we wouldn't need to compute a hash for comparison... but since we need one for tracking... we compute one. Then if the hashes match up, we can do a quick comparison.

        BUF_SIZE is arbitrarily chosen to read files in 128kb chunks.
    """
    startTime=datetime.now()
    redundancies = {} # maps hexdigest of hash to list of file paths
    progressctr=0
    progresstotal=len(local_music_file_infos)
    # See https://stackoverflow.com/questions/22058048/hashing-a-file-in-python
    for lmfi in local_music_file_infos:
        progressctr+=1
        print("[HASHING]: Progress {} / {}".format(progressctr, progresstotal))
        # compute md5 without reading the whole file at once. Maybe not necessary, but whatever.
        md5=hashlib.md5()
        with open(lmfi.full_path, 'rb') as f:
            while True:
                data = f.read(BUF_SIZE)
                if not data:
                    break
                md5.update(data)
        mdhash = md5.hexdigest()
        # add to dict
        redundancies[mdhash] = redundancies.get(mdhash, list()) + [lmfi.full_path]
    
    if I_AM_SCARED_OF_HASH_COLLISIONS:
        # make sure they really are equal, byte for byte. If we're unsure, we better treat them as distinct
        out_redundancies = {}
        progressctr=0
        progresstotal = len(redundancies.keys())
        for mdhash, pathlist in redundancies.items():
            # compare the first item to each other
            hashctr = 0
            progressctr+=1
            print("[HASH COLLISION DETECTION]: Progress {} / {}".format(progressctr, progresstotal))
            while True:
                if len(pathlist) == 1:
                    # only one item? it's the same xD
                    hashctr+=1
                    out_redundancies[mdhash + str(hashctr)]
                    break
                if len(pathlist) == 0:
                    # I don't even
                    break
                # the nontrivial case
                eq_to_first = [filecmp.cmp(pathlist[0], pathlist[i]) for i in range(1, len(pathlist))]
                try:
                    num_the_same = sum(eq_to_first)
                except IndexError as e:
                    # debugging issue
                    print("{}".eq_to_first())
                    raise e
                if num_the_same == len(pathlist):
                    # everything is the same, nothing needs to be rearranged
                    hashctr+=1
                    out_redundancies[mdhash+str(hashctr)] = pathlist
                    break
                else:
                    same=[pathlist[0]]
                    not_same=[]
                    for i in range(len(eq_to_first)):
                        if eq_to_first[i]:
                            # the ith entry in eq_to_first is the i+1st entry in pathlist
                            same.append(pathlist[i+1])
                        else:
                            not_same.append(pathlist[i+1])
                    # store again, but with modified (longer) hash
                    # "same" is at least 1 entry long
                    hashctr+=1
                    samehash=mdhash+str(hashctr)
                    out_redundancies[samehash] = same
                    # "not_same" is re-considered if not empty. The case where len(not_same)==1 is handled at the start of the next loop iteration
                    if len(not_same) > 0:
                        # the not_same need to be checked again among themselves.
                        pathlist=not_same
                        # eventually, when all not_same are equal, they will be added
                    continue
    else:
        # not scared of hash collisions
        out_redundancies = redundancies

    # Now get rid of memory usage for those that are alone.
    print("building smaller dictionary")
    redundancies={}
    for key, val in out_redundancies.items():
        if len(val) > 1:
            redundancies[key]=val


    print("Time: {}".format(datetime.now() - startTime))
    with open(os.path.join(OUTPUT_PLAYLIST_DIR, "redundancies.json"), "w", encoding="utf-8") as jsf:
        json.dump(redundancies, jsf)

    return redundancies

def update_playlists(playlists, redundancies):
    return playlists # stub

def delete_redundant_files(redundancies):
    #stub
    pass

def main():
    startTime=datetime.now()
    tracker = MatchTracker()
    fallback_tracker = MatchTracker()
    print("Considering any playlists in {}".format(PLAYLISTS_PATH))
    
    print("Collecting playlist directories...\n")
    subfolders = [ f.path for f in os.scandir(PLAYLISTS_PATH) if f.is_dir() and not is_ignored(f.path) ]
    playlists = list(filter_playlists(subfolders))
    for playlistpath in playlists:
        playlistname = os.path.basename(playlistpath)
        print("\tPlaylist: {}".format(playlistname))

    print("Indexing local music files...")
    local_music_file_infos = [FileInfo(filename=filpath, full_path=os.path.abspath(os.path.join(dirpath, filpath))) for (dirpath, _dirs, filpaths) in os.walk(MUSIC_PATH) for filpath in filpaths if not is_ignored(dirpath) ]

    print("Indexing local music file tags...")
    for file_info in local_music_file_infos:
        file_info.update_tag_from_fs()

    print("Indexing fallback...") 
    fallback_music_file_infos = []
    fallback_music_files=[]
    for fallback in GPM_FALLBACK_TRACK_PATHS:
        fbpath = os.path.normpath(fallback)

        print("Indexing local fallback music files for {} ...".format(fbpath))
        fallback_music_file_infos = [FileInfo(filename=filpath, full_path=os.path.join(dirpath, filpath)) for (dirpath, _dirs, filpaths) in os.walk(fbpath) for filpath in filpaths if not is_ignored(dirpath) ]
        fallback_music_files=map(lambda x: x.get_plain_filename(), fallback_music_file_infos)

        print("Indexing local fallback music tags for {} ...".format(fbpath))
        for file_info in fallback_music_file_infos:
            file_info.update_tag_from_fs()

    output_playlists = [] # List of Playlist objects

    print("Accumulating Contents...")
    # hackaround for Thumbs up Playlist: add it and handle it separately
    THUMBSUPHACK="thumbsuphack1234542323232321231233333$2"
    playlists.append(THUMBSUPHACK)
    for playlistpath in playlists:
        if playlistpath != THUMBSUPHACK:
            playlistname = os.path.basename(playlistpath)
            print("Accumulating Contents for Playlist {}".format(playlistname))
            song_info_list_sorted = read_gpm_playlist(playlistpath)
        else:
            playlistname = "Thumbs up"
            print("Accumulating Contents for Playlist {}".format(playlistname))
            song_info_list_sorted = read_gpm_playlist(PLAYLISTS_PATH, trackdir="Thumbs up")
        song_path_list = []
        # instantiate playlist object for later use
        playlist=Playlist(name=playlistname)
        output_playlists.append(playlist)
        for song_info in song_info_list_sorted:
            # count number of playlist searches for debugging
            tracker.increment_search_counter(playlistname)

            # try once normally, and if nothing works try again with the stripped title
            match_found=False
            for hack_one in range(2):
                # hack_one: temporarily use stripped title as normal title
                hack_one_tmp = None
                if (hack_one == 1):
                    hack_one_tmp = song_info
                    song_info = SongInfo(
                            title=song_info.title_stripped,
                            artist=song_info.artist,
                            album=song_info.album,
                            title_stripped=song_info.title,
                            liked=song_info.liked,
                            )
                    # restore at the end of loop iteration

                # try exact tag matching - for MP3 files only
                found_exact_match = find_exact_tag_match(local_music_file_infos, song_info, tracker, playlist=playlist)
                if found_exact_match:
                    match_found=True
                    break

                # try a simple heuristic of whether the tags contain the relevant title and artist
                if tags_contain_info(local_music_file_infos, song_info, tracker, playlist=playlist):
                    match_found=True
                    break

                # try a heuristic on the file path (full path, not just name)
                if filepath_contains_info(local_music_file_infos, song_info, tracker, playlist=playlist):
                    match_found=True
                    break

                # Not found... let's use the fallback GPM export (if set)
                # Since the Tags should be correct there, we only check for exact matches. But technically we could also run the other checks.
                found_exact_gpm_match = find_exact_tag_match(fallback_music_file_infos, song_info, fallback_tracker, playlist=playlist)
                if found_exact_gpm_match:
                    match_found=True
                    break
                # But since gpm seems to cut off some parts of long titles, let's also check for substrings
                if find_substring_tag_match(fallback_music_file_infos, song_info, fallback_tracker, playlist=playlist):
                    match_found=True
                    break

                # try things that are likely to guess wrongly
                if USE_UNRELIABLE_METHODS:
                    # try fuzzy filename matching in various orders
                    fuzzy_match_techniques = [
                            "{artist}{title}{album}",
                            "{artist}{title}",
                            "{artist}{album}{title}",
                            "{title}",
                            "{title} - {artist}",
                            ]
                    for tec in fuzzy_match_techniques:
                        # if found, break and continue with next song
                        found_fuzzy_match = find_fuzzy_match(local_music_file_infos, song_info, tec, tracker, playlist=playlist)
                        if found_fuzzy_match:
                            break
                    if found_fuzzy_match:
                        #continue with next song
                        match_found=True
                        break
                    
                    # try fuzzy tag matching
                    found_fuzzy_tag_match = find_fuzzy_tag_match(local_music_file_infos, song_info, tracke, playlist=playlistr)
                    if found_fuzzy_tag_match:
                        match_found=True
                        break

                if (hack_one == 1):
                    # Not sure if this restoration is ever relevant, but why not do it.
                    song_info = hack_one_tmp

            if not match_found:
                # if we're still here, no match has been found for this song.
                tracker.unmatch(song_info, playlist)
                tracker.unmatch_for_playlist(playlistname)
            else:
                continue # not explicitly needed

    print("\nSubmatched Songs: \n{}\n#End List of Submatched Songs".format(pformat(fallback_tracker.subbed_songs)))
    print("\nUnmatched Songs: \n{}\n#End List of Unmatched Songs".format(pformat(tracker.unmatched_songs)))
    print("\nFuzzy Stats: \n{}".format(pformat(tracker.fuzzy_details)))
    print("\nFound Matches Statistics:\n{}".format(pformat(tracker.match_counts)))
    print("\nMatches from Fallback (unmatched total is handled by other tracker):\n{}".format(pformat(fallback_tracker.match_counts)))
    print("\nSearched Playlists Statistics:\n{}".format(pformat(tracker.playlist_searches)))
    print("\nIncompleteness of Playlists (Number of missing Songs):\n{}".format(pformat(tracker.num_songs_missing)))
    print("Time: {}".format(datetime.now() - startTime))

    output_playlists=complete_playlists_interactively(output_playlists)
    if COPY_FALLBACK_GPM_MUSIC:
        output_playlists=copy_files_over(output_playlists)
    if DELETE_REDUNDANT_FILES_IN_MUSIC_PATH:
        redundancies = compute_redundant_files(local_music_file_infos, folder=MUSIC_PATH) # a dict of file hashes and a list of paths
        output_playlists=update_playlists(output_playlists, redundancies) # only use the first file of each list
        delete_redundant_files(redundancies) # delete all that are not the first in their list and that are within the music path
    if SAVE_ABSOLUTE_PLAYLISTS:
        save_playlist_files(output_playlists, outdir=OUTPUT_PLAYLIST_DIR)
    if MAKE_PLAYLISTS_RELATIVE_TO_OUTPUT_PLAYLIST_DIR:
        output_playlists_rel=relativate_playlists(output_playlists, relative_to=OUTPUT_PLAYLIST_DIR_RELATIVE)
        save_playlist_files(output_playlists_rel, outdir=OUTPUT_PLAYLIST_DIR_RELATIVE)

if __name__ == '__main__':
    if len(sys.argv) > 1:
        if sys.argv[1] == 'help':
            print("hello. Specify some things in the source file with the CAPS LOCKED variables!")
            print("If you're running this in Windows CMD, you might need to `set PYTHONIOENCODING=utf-8` first.")
            print("It is probably advisable to pipe the stdout into a file so that the important messages from STDERR surface clearly.")
            exit(0)
        if sys.argv[1] == 'here':
            print("using current directory {} as MUSIC_PATH".format(os.getcwd()))
            MUSIC_PATH = os.getcwd()

    # always:
    main()
    print_todos()
    print("Done", file=sys.stderr)

