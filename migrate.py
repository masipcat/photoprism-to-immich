import base64
from collections import defaultdict

import click
import httpx
import MySQLdb


class ImmichClient:

    def __init__(self, server, apikey, dry_run):
        self.dry_run = dry_run
        self.apikey = apikey
        self.client = httpx.Client(
            base_url=server,
            auth=httpx._auth.FunctionAuth(self._api_key_auth),
        )

    def _api_key_auth(self, request):
        request.headers["x-api-key"] = self.apikey
        return request

    def get_all_assets(self):
        """
        https://immich.app/docs/api/get-all-assets
        """
        resp = self.client.get("/api/asset")
        resp.raise_for_status()

        assets = {}
        for asset in resp.json():
            checksum = base64.b64decode(asset["checksum"]).hex()
            assets[checksum] = asset
        return assets

    def get_all_albums(self):
        """
        https://immich.app/docs/api/get-all-albums
        """
        resp = self.client.get("/api/album")
        resp.raise_for_status()

        albums = {}
        for a in resp.json():
            albums[a["albumName"]] = a
        return albums

    def create_album(self, album_name):
        """
        https://immich.app/docs/api/create-album
        """
        if self.dry_run:
            return

        data = {"albumName": album_name}
        resp = self.client.post("/api/album", json=data)
        resp.raise_for_status()
        return resp.json()

    def set_favorites(self, ids):
        """
        https://immich.app/docs/api/update-assets/
        """
        if self.dry_run:
            return

        data = {"ids": ids, "isFavorite": True}
        resp = self.client.put("/api/asset", json=data)
        resp.raise_for_status()

    def set_assets_to_album(self, album_id, ids):
        """
        https://immich.app/docs/api/add-assets-to-album
        """
        if self.dry_run:
            return

        data = {"ids": ids}
        resp = self.client.put(f"/api/album/{album_id}/assets", json=data)
        resp.raise_for_status()


class PhotoPrismClient:

    def __init__(self, host, user, password, db):
        self.conn = MySQLdb.connect(
            host=host, user=user, password=password, database=db
        )

    def get_favorites(self):
        query = """
            select f.id, file_hash, file_name
            from files f
            left join photos p on f.photo_id = p.id
            where p.photo_favorite = 1;
        """
        c = self.conn.cursor()
        c.execute(query)
        return {
            checksum.decode("utf-8"): fn.decode("utf-8")
            for f_id, checksum, fn in c.fetchall()
        }

    def get_photos_in_albums(self):
        query = """
            select file_hash, file_name, album_uid, album_title
            from files f
            inner join photos_albums pa using(photo_uid)
            inner join albums using(album_uid);
        """
        c = self.conn.cursor()
        c.execute(query)
        return {
            checksum.decode("utf-8"): {
                "file_name": fn.decode("utf-8"),
                "album_id": album_id.decode("utf-8"),
                "album_title": album_title,
            }
            for checksum, fn, album_id, album_title in c.fetchall()
        }


@click.group()
@click.option("--dry-run", is_flag=True)
@click.option("--im-url", required=True)
@click.option("--im-apikey", required=True)
@click.option("--pp-mysql-host", required=True)
@click.option("--pp-mysql-user", required=True)
@click.option("--pp-mysql-pswd", required=True)
@click.option("--pp-mysql-db", required=True)
@click.pass_context
def cli(
    ctx,
    dry_run,
    im_url,
    im_apikey,
    pp_mysql_host,
    pp_mysql_user,
    pp_mysql_pswd,
    pp_mysql_db,
):
    ctx.obj = {
        "immich": ImmichClient(im_url, im_apikey, dry_run),
        "photoprism": PhotoPrismClient(
            pp_mysql_host, pp_mysql_user, pp_mysql_pswd, pp_mysql_db
        ),
    }


@cli.command()
@click.pass_context
def migrate_favorites(ctx):
    immich = ctx.obj["immich"]
    photoprism = ctx.obj["photoprism"]

    favorites_pp = photoprism.get_favorites()
    immich_assets = immich.get_all_assets()

    favorites_immich_ids = {
        asset["id"]: asset["originalFileName"]
        for checksum, asset in immich_assets.items()
        if checksum in favorites_pp and asset["isFavorite"] is False
    }

    if favorites_immich_ids:
        click.echo(f"Set favorite: {favorites_immich_ids}")
        immich.set_favorites(list(favorites_immich_ids.keys()))


@cli.command()
@click.pass_context
def migrate_albums(ctx):
    immich = ctx.obj["immich"]
    photoprism = ctx.obj["photoprism"]

    pp_photos_in_albums = photoprism.get_photos_in_albums()

    photos_by_album_name = defaultdict(list)
    for checksum, data in pp_photos_in_albums.items():
        album_name = data["album_title"]
        photos_by_album_name[album_name] += [checksum]

    immich_albums = immich.get_all_albums()
    # Create missing albums
    for album in photos_by_album_name:
        if album not in immich_albums:
            resp = immich.create_album(album)
            album_id = resp["id"]
            click.echo(f"Created album {album}: {album_id}")
            immich_albums[album] = resp

    immich_assets = immich.get_all_assets()
    # Assign assets to album
    for album in photos_by_album_name:
        album_id = immich_albums[album]["id"]
        assets_ids = []
        for checksum in photos_by_album_name[album]:
            if checksum in immich_assets:
                assets_ids += [immich_assets[checksum]["id"]]
            else:
                original_file = pp_photos_in_albums[checksum]["file_name"]
                click.echo(
                    f"Photo with checksum {checksum} ({original_file}) not found in Immich"
                )

        click.echo(f"Set {len(assets_ids)} assets to album {album} ({album_id})")
        immich.set_assets_to_album(album_id, assets_ids)


if __name__ == "__main__":
    cli()
