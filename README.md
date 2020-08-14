Google Play Music is being discontinued starting October 2020. The successor, Youtube Music, requires payment or the music will stop when you turn your screen off. And other disadvantages. So you want to migrate to `m3u` playlist files again.

1. [Export from Google Takeout](https://takeout.google.com/) by selecting only Google Play Music.
   The format of the playlists is a weird csv directory structure.

2. Set configuration options of this script.

3. ```bash
   python convert.py > out.txt
   ```

4. Congrats! You now have 

   * Playlists with absolute paths to your **existing high-quality music files**
   * Playlists using relative paths
   * No more duplicate files in your existing library

### Setup

```bash
git clone https://github.com/lucidBrot/migrate-from-google-play-music.git
```

The environment.yml was generated with conda. You should only need to install`mutagen` (with pip or conda).

```bash
conda install -c conda-forge mutagen
```

