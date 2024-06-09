# PhotoPrism to Immich migrator

This tool migrates albums and favorites from a PhotoPrism instance to a Immich instance. Photos and videos must be already migrated to Immich.

## How it works

The script retrieves the list of assets from Immich and matches them with PhotoPrism files, using the sha1 checksum of the file computed by both softwares.

## Installation

```sh
cd photoprism-to-immich
pip install -r requirements.txt
```

## Usage

```
Usage: migrate.py [OPTIONS] COMMAND [ARGS]...

Options:
  --dry-run
  --im-url TEXT         [required]
  --im-apikey TEXT      [required]
  --pp-mysql-host TEXT  [required]
  --pp-mysql-user TEXT  [required]
  --pp-mysql-pswd TEXT  [required]
  --pp-mysql-db TEXT    [required]
  --help                Show this message and exit.

Commands:
  migrate-albums
  migrate-favorites
```

## Example command to migrate albums

```sh
python migrate.py \
    --dry-run \
    --im-url https://immich.example.com \
    --im-apikey API_KEY \
    --pp-mysql-host 127.0.0.1 \
    --pp-mysql-user photoprism \
    --pp-mysql-pswd '' \
    --pp-mysql-db photoprism \
    migrate-albums
```
