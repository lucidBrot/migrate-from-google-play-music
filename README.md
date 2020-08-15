Google Play Music is being discontinued starting October 2020. The successor, Youtube Music, requires payment or the music will stop when you turn your screen off. And other disadvantages. So you want to migrate to `m3u` playlist files again.

1. [Export from Google Takeout](https://takeout.google.com/) by selecting only Google Play Music.
   The format of the playlists is a weird csv directory structure.

2. Set configuration options of this script.

3. ```bash
   python convert.py > out.txt
   ```

4. Congrats! You now have 

   * Playlists with absolute paths to your **existing high-quality music files**
   * Playlists **using relative paths** for the same
   * **No more duplicate files** in your library

### Install

```bash
git clone https://github.com/lucidBrot/migrate-from-google-play-music.git
```

The environment.yml was generated with conda. You should only need to install`mutagen` (with pip or conda).

```bash
conda install -c conda-forge mutagen
```

Then read the [Options](#Options) and [Run](#Run) it.

### Options

The following options can and/or should be set near the top of the file by modifying the script before you run it. I advise to have a look at all of them, but *you must modify at least these:*

* [OUTPUT_PLAYLIST_DIR_RELATIVE](#OUTPUT_PLAYLIST_DIR_RELATIVE) and [MAKE_PLAYLISTS_RELATIVE_TO_OUTPUT_PLAYLIST_DIR](#MAKE_PLAYLISTS_RELATIVE_TO_OUTPUT_PLAYLIST_DIR)
* [REDUCE_PLAYLIST_REDUNDANCIES](#REDUCE_PLAYLIST_REDUNDANCIES) and [DELETE_REDUNDANT_FILES_IN_MUSIC_PATH](#DELETE_REDUNDANT_FILES_IN_MUSIC_PATH)
* [PLAYLISTS_PATH](#PLAYLISTS_PATH)
* [MUSIC_PATH](#MUSIC_PATH)
* [GPM_FALLBACK_TRACK_PATHS](#GPM_FALLBACK_TRACK_PATHS)

#### USE_UNRELIABLE_METHODS

Default `False`. If `True`, the script will perform some fuzzy matching that is likely to yield wrong results, but at least they are results and don't require manual intervention. In my case I did not require this.

#### HANDLE_THUMBS_UP

Default `True`. The "Thumbs up" playlist has a different format and hence must be handled differently. If `False`, that playlist will be ignored.

#### OUTPUT_PLAYLIST_DIR

Default `output_playlists` relative to the current working dir. You can specify also an absolute path instead.
The playlist versions with absolute paths will be generated here.

#### OUTPUT_PLAYLIST_DIR_RELATIVE

Where the playlist files are to be stored. Their referenced music files will be relative to this directory.

#### IGNORE_MUSIC_FOLDERS

Default `['@eaDir', os.path.basename(OUTPUT_PLAYLIST_DIR_RELATIVE)]` ignores synology indexing files and the relative playlist directory when collecting a list of all locally stored music files.

#### MAKE_PLAYLISTS_RELATIVE_TO_OUTPUT_PLAYLIST_DIR

Default `True`. If `False`, no relative playlist files will be generated.

#### SAVE_ABSOLUTE_PLAYLISTS

Default `True`. If `False` no absolute playlist files will be generated.

#### REDUCE_PLAYLIST_REDUNDANCIES

Default `True`. Increases runtime by about 3 Minutes to compute hashes of all files in `MUSIC_PATH` and only reference one of those with equal hashes. This means deduplication becomes possible.

If `False`, the script will finish faster, but other options become unusable.

#### DUMP_REDUNDANCIES_AS_JSON_TO_OUTPUT_PLAYLIST_DIR

Default `True`. Writes the found redundancies as a JSON object to a file in the [OUTPUT_PLAYLIST_DIR](#OUTPUT_PLAYLIST_DIR). This file is not further used by the script, it's just for you.

#### DELETE_REDUNDANT_FILES_IN_MUSIC_PATH

Default `True`. If `True`, any files with the same hash will be deleted except for one each - the one which is used in the generated playlists thanks to [REDUCE_PLAYLIST_REDUNDANCIES](#REDUCE_PLAYLIST_REDUNDANCIES).

Should have no effect if said option is not set to `True`.

If `False`, nothing will be deleted

#### MOVE_FILES_INSTEAD_OF_DELETION

Recommend to set to a path. As a safety measure, files that would be deleted by virtue of [DELETE_REDUNDANT_FILES_IN_MUSIC_PATH](#DELETE_REDUNDANT_FILES_IN_MUSIC_PATH) are instead moved to that path so you can manually review them before deletion.

My usage: `MOVE_FILES_INSTEAD_OF_DELETION=os.path.normpath('N:\Temp\GPM_Deletion')`

#### PLAYLISTS_PATH

Where your Google Play Music Takeout export resides, so that their weird csv folder structure is there.

My usage:`PLAYLISTS_PATH = os.path.normpath('N:\Files\Backups\GPM_export\Takeout\Google Play Music\Playlists')`

#### MUSIC_PATH

You have local music files that you prefer over the ones exported from Google Play Music? Likely some FLACs and some MP3s that are not well-sorted and not all are tagged correctly? That's one of the main reasons why this script exists.

My usage: `MUSIC_PATH = os.path.normpath('N:\Files\Musik')`

If you do not have any such directory and just want to use the GPM exported mp3 files, set this to the GPM Tracks directory and deactivate [COPY_FALLBACK_GPM_MUSIC](#COPY_FALLBACK_GPM_MUSIC).

#### COPY_FALLBACK_GPM_MUSIC

Default `True`. Copy files over to the music directory at [MUSIC_PATH](#MUSIC_PATH) if and only if they are used in a playlist. If `False`, no files will be copied over.

If `True`, you also need to set `COPY_FALLBACKS_TO_PATH`.

My usage:

```python
COPY_FALLBACK_GPM_MUSIC=True
COPY_FALLBACKS_TO_PATH=os.path.normpath(os.path.join(MUSIC_PATH, "2020", "gpm-migration"))
```

#### GPM_FALLBACK_TRACK_PATHS

Specify 0 or more fallback paths. Those will be searched if no match in the [MUSIC_PATH](#MUSIC_PATH) was found for a song. This setting can be used even without [COPY_FALLBACK_GPM_MUSIC](#COPY_FALLBACK_GPM_MUSIC) enabled.

My usage:

```python
# Path to where the export from GPM resides.
# Files are assumed to be lower quality
# Also add any other fallback paths here.
GPM_FALLBACK_TRACK_PATHS = [
        os.path.normpath('N:\Files\Backups\GPM_export\Takeout\Google Play Music\Tracks'),
        os.path.normpath('F:\PlayMusic'),
        ]
```

#### I_AM_SCARED_OF_HASH_COLLISIONS

Default `False`. If `True`, any redundancy checks for [REDUCE_PLAYLIST_REDUNDANCIES](#REDUCE_PLAYLIST_REDUNDANCIES) are only trusted if the files actually differ, not just their hashes. This will take longer, and is not tested. Feel free to create a PR if you had to fix something.

### Run

#### Normal Usage: Run Everything

Set the options as outlined in the [Options Section](#Options), then run it with

```bash
python convert.py > out.txt
```

The important or interactive messages will appear in stderr and hence the terminal, the rest is just logging. You can delete `out.txt` after the run if you wish - it is never read.

This run took about 4 minutes on my machine in order to match 20 playlists to a local library of 4000 music files and deleting 200 redundant files. I had to manually find 30 files.

If the script prompts you in the terminal to provide information, you'll have to open the file `_missing_matches.json` in the current working directory and insert the paths that should be used for those files. They may lie outside of `MUSIC_PATH` and if `COPY_FALLBACK_GPM_MUSIC` is set to `True` (default) they will be copied over to the `MUSIC_PATH`. Note that a json path needs to have backslashes escaped, so the lines may look something like this:

```
"SongInfo(title='Grey', artist='Meinhard', liked=True, album='', title_stripped='Grey')": "N:\\Files\\Musik\\2020\\april\\Meinhard Grey_LalU7ej8Kwk.mp3",
```

If a path is invalid or inexistent, the program will tell you. Just save the file, then press <kbd>ENTER</kbd> in the Terminal. When done, it will say `Thanks!`.

For entering those paths manually, I've found "Everything Search" on Windows to be useful. I found the local files with it, copied the paths, and in the end I used Notepad++ to do a quick find-and-replace so that I have the correct number of backslashes in my paths.

#### Compute Songlists

If you just want a list of the Information from each GPM-exported "Playlist", in a single file for *one* playlist, then run

```bash
python -c "import convert; convert.read_gpm_playlist('/path-to/Google Play Music/Playlists/MyPlaylistDir/');"
```

If you want to have that information for each playlist, and saved to files, then run

```python
python -c "import convert; convert.generate_songlists();"
```

Of course, relevant [Options](#Options) need to be set.

#### Compute Duplicates in `MUSIC_PATH`

```python
python convert.py -c "import * from convert; lmfi=debug_create_lmfi_sans_tags(); compute_redundant_files(lmfi);"
```

If `DUMP_REDUNDANCIES_AS_JSON_TO_OUTPUT_PLAYLIST_DIR` is `True`, this dumps to a file in the folder where the absolute path playlists would also be stored.



