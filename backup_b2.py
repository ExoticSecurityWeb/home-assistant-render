#!/usr/bin/env python3

import os
import sys
import tarfile
import tempfile
import time
from datetime import datetime, timezone

import boto3
from botocore.config import Config


CONFIG_DIR = "/config"
WORK_DIR = "/backup"

B2_ENDPOINT = os.environ.get("B2_ENDPOINT", "")
B2_KEY_ID = os.environ.get("B2_KEY_ID", "")
B2_APPLICATION_KEY = os.environ.get("B2_APPLICATION_KEY", "")
B2_BUCKET = os.environ.get("B2_BUCKET", "")

PREFIX = "home-assistant/"

KEEP_BACKUPS = 7
MIN_BACKUP_INTERVAL = 60
CHECK_INTERVAL = 5


def get_client():
    if not B2_ENDPOINT:
        raise RuntimeError("B2_ENDPOINT missing")

    if not B2_KEY_ID:
        raise RuntimeError("B2_KEY_ID missing")

    if not B2_APPLICATION_KEY:
        raise RuntimeError("B2_APPLICATION_KEY missing")

    if not B2_BUCKET:
        raise RuntimeError("B2_BUCKET missing")

    endpoint = B2_ENDPOINT

    if not endpoint.startswith("http"):
        endpoint = "https://" + endpoint

    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=B2_KEY_ID,
        aws_secret_access_key=B2_APPLICATION_KEY,
        region_name="us-east-005",
        config=Config(signature_version="s3v4"),
    )


def configured():
    return os.path.exists(
        os.path.join(CONFIG_DIR, ".storage", "core.config_entries")
    )


def latest_backup(s3):
    result = s3.list_objects_v2(
        Bucket=B2_BUCKET,
        Prefix=PREFIX,
    )

    objects = [
        item
        for item in result.get("Contents", [])
        if item["Key"].endswith(".tar.gz")
    ]

    if not objects:
        return None

    return max(
        objects,
        key=lambda item: item["LastModified"],
    )


def should_restore(path):
    """
    Détermine si un fichier du backup peut être restauré.
    """

    normalized = path.replace("\\", "/").lstrip("./")

    ignored_files = {
        "home-assistant.log",
        "home-assistant.log.1",
        "home-assistant.log.fault",
        "home-assistant_v2.db",
        "home-assistant_v2.db-shm",
        "home-assistant_v2.db-wal",
        ".HA_VERSION",
    }

    filename = os.path.basename(normalized)

    if filename in ignored_files:
        return False

    ignored_parts = {
        "__pycache__",
        ".cache",
        "tts",
    }

    parts = normalized.split("/")

    if any(part in ignored_parts for part in parts):
        return False

    return True


def safe_extract(archive, destination):
    """
    Extrait uniquement les fichiers autorisés du backup.
    """

    for member in archive.getmembers():

        if not should_restore(member.name):
            print(
                f"B2: fichier runtime ignoré: {member.name}",
                flush=True,
            )
            continue

        target = os.path.abspath(
            os.path.join(destination, member.name)
        )

        base = os.path.abspath(destination)

        if not (
            target == base
            or target.startswith(base + os.sep)
        ):
            raise RuntimeError(
                f"Chemin invalide dans le backup: {member.name}"
            )

        archive.extract(member, destination)


def restore():
    """
    Restaure le dernier backup uniquement si
    Home Assistant n'est pas encore configuré.
    """

    if configured():
        print(
            "B2: configuration existante détectée, restauration ignorée.",
            flush=True,
        )
        return

    print(
        "B2: recherche d'un backup...",
        flush=True,
    )

    s3 = get_client()

    backup = latest_backup(s3)

    if not backup:
        print(
            "B2: aucun backup trouvé. Première installation.",
            flush=True,
        )
        return

    key = backup["Key"]

    print(
        f"B2: restauration de {key}",
        flush=True,
    )

    os.makedirs(WORK_DIR, exist_ok=True)

    with tempfile.NamedTemporaryFile(
        suffix=".tar.gz",
        dir=WORK_DIR,
        delete=False,
    ) as temp:
        local_file = temp.name

    try:

        s3.download_file(
            B2_BUCKET,
            key,
            local_file,
        )

        print(
            "B2: extraction sécurisée du backup...",
            flush=True,
        )

        with tarfile.open(
            local_file,
            "r:gz",
        ) as archive:

            safe_extract(
                archive,
                CONFIG_DIR,
            )

        print(
            "B2: restauration terminée.",
            flush=True,
        )

    finally:

        try:
            os.remove(local_file)
        except FileNotFoundError:
            pass


def config_signature():
    ignored = {
        "home-assistant.log",
        "home-assistant.log.1",
        "home-assistant.log.fault",
        "home-assistant_v2.db",
        "home-assistant_v2.db-shm",
        "home-assistant_v2.db-wal",
        ".HA_VERSION",
    }

    entries = []

    for root, dirs, files in os.walk(CONFIG_DIR):

        dirs[:] = [
            d
            for d in dirs
            if d not in {
                "__pycache__",
                ".cache",
                "tts",
            }
        ]

        for filename in files:

            if filename in ignored:
                continue

            path = os.path.join(
                root,
                filename,
            )

            try:

                stat = os.stat(path)

                relative = os.path.relpath(
                    path,
                    CONFIG_DIR,
                )

                entries.append(
                    (
                        relative,
                        stat.st_size,
                        stat.st_mtime_ns,
                    )
                )

            except FileNotFoundError:
                pass

    return tuple(sorted(entries))


def create_backup(s3):

    timestamp = datetime.now(
        timezone.utc
    ).strftime(
        "%Y%m%d-%H%M%S"
    )

    filename = (
        f"home-assistant-{timestamp}.tar.gz"
    )

    local_file = os.path.join(
        WORK_DIR,
        filename,
    )

    remote_key = PREFIX + filename

    print(
        f"B2: création de {filename}",
        flush=True,
    )

    with tarfile.open(
        local_file,
        "w:gz",
    ) as archive:

        def filter_member(member):

            if not should_restore(member.name):
                return None

            return member

        archive.add(
            CONFIG_DIR,
            arcname=".",
            filter=filter_member,
        )

    print(
        "B2: upload...",
        flush=True,
    )

    s3.upload_file(
        local_file,
        B2_BUCKET,
        remote_key,
    )

    os.remove(local_file)

    print(
        "B2: backup terminé.",
        flush=True,
    )

    cleanup_old_backups(s3)


def cleanup_old_backups(s3):

    result = s3.list_objects_v2(
        Bucket=B2_BUCKET,
        Prefix=PREFIX,
    )

    backups = [
        item
        for item in result.get("Contents", [])
        if item["Key"].endswith(".tar.gz")
    ]

    backups.sort(
        key=lambda item: item["LastModified"],
        reverse=True,
    )

    for old in backups[KEEP_BACKUPS:]:

        print(
            f"B2: suppression de {old['Key']}",
            flush=True,
        )

        s3.delete_object(
            Bucket=B2_BUCKET,
            Key=old["Key"],
        )


def watch():

    print(
        "B2: surveillance des modifications activée.",
        flush=True,
    )

    s3 = get_client()

    last_signature = config_signature()

    last_backup_time = 0

    while True:

        time.sleep(CHECK_INTERVAL)

        try:

            current_signature = config_signature()

            if current_signature == last_signature:
                continue

            last_signature = current_signature

            now = time.time()

            if now - last_backup_time < MIN_BACKUP_INTERVAL:

                print(
                    "B2: modification détectée mais "
                    "anti-spam actif.",
                    flush=True,
                )

                continue

            print(
                "B2: modification importante détectée.",
                flush=True,
            )

            create_backup(s3)

            last_backup_time = time.time()

        except Exception as error:

            print(
                f"B2 ERROR: {error}",
                file=sys.stderr,
                flush=True,
            )


if __name__ == "__main__":

    if len(sys.argv) != 2:

        print(
            "Usage: backup_b2.py restore|watch"
        )

        sys.exit(1)

    command = sys.argv[1]

    if command == "restore":

        restore()

    elif command == "watch":

        watch()

    else:

        print(
            "Commande inconnue."
        )

        sys.exit(1)