#!/usr/bin/env python3
"""
backup_mongodb.py — MongoDB On-Demand Backup to S3

Triggered from Jenkins EC2 (same VPC as MongoDB private subnet).
Connects via SSH (paramiko), runs the backup script installed by Ansible
at /usr/local/bin/mongodb-backup.sh, downloads the archive via SFTP,
uploads to S3, and applies retention policy.

Usage:
  python backup_mongodb.py --key-file ../osm-key.pem
  python backup_mongodb.py --key-file ../osm-key.pem --retain 30
  python backup_mongodb.py --key-file ../osm-key.pem --dry-run

Environment variables (alternative to CLI args):
  AWS_REGION      AWS region (default: ap-southeast-1)
  OSM_KEY_FILE    Path to SSH private key (default: ../osm-key.pem)
  OSM_S3_BUCKET   S3 bucket name (auto-named if omitted)
  OSM_RETAIN      Backups to keep in S3 (default: 30)
  OSM_DRY_RUN     Set "true" to preview without executing

Prerequisites:
  - Run from Jenkins EC2 (has VPC access to MongoDB private IP)
  - osm-key.pem accessible at path given by --key-file or OSM_KEY_FILE
  - Jenkins IAM role must have:
      s3:PutObject, s3:GetObject, s3:ListBucket, s3:DeleteObject,
      s3:CreateBucket, ec2:DescribeInstances, sts:GetCallerIdentity

Exit codes:
  0  Backup completed successfully
  1  Backup failed
"""

import argparse
import logging
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

try:
    import boto3
    import paramiko
except ImportError as exc:
    print(f"ERROR: Missing dependency — {exc}")
    print("Run: pip install -r requirements.txt")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
DEFAULT_REGION  = "ap-southeast-1"
DEFAULT_RETAIN  = 30
SSH_USER        = "ubuntu"
BACKUP_SCRIPT   = "/usr/local/bin/mongodb-backup.sh"
BACKUP_DIR      = "/backup/mongodb"
SSH_PORT        = 22
SSH_TIMEOUT     = 30    # connection timeout (seconds)
CMD_TIMEOUT     = 600   # backup script timeout (seconds)
S3_PREFIX       = "mongodb/"


# ── AWS helpers ───────────────────────────────────────────────────────────────

def get_mongodb_private_ip(ec2_client) -> str:
    """Find MongoDB EC2 private IP by tag Name=osm-mongodb."""
    resp = ec2_client.describe_instances(
        Filters=[
            {"Name": "tag:Name",            "Values": ["osm-mongodb"]},
            {"Name": "instance-state-name", "Values": ["running"]},
        ]
    )
    instances = [i for r in resp["Reservations"] for i in r["Instances"]]
    if not instances:
        raise RuntimeError(
            "No running EC2 instance with tag Name=osm-mongodb found. "
            "Ensure Terraform has been applied and the instance is running."
        )
    ip = instances[0]["PrivateIpAddress"]
    log.info("MongoDB EC2 private IP: %s", ip)
    return ip


def get_account_id(sts_client) -> str:
    return sts_client.get_caller_identity()["Account"]


def ensure_s3_bucket(s3_client, bucket: str, region: str):
    """Create S3 bucket if it does not exist, with public access blocked."""
    try:
        s3_client.head_bucket(Bucket=bucket)
        log.info("S3 bucket exists: %s", bucket)
    except Exception as exc:
        code = getattr(getattr(exc, "response", None), "get", lambda *a: {})
        error_code = ""
        if hasattr(exc, "response") and exc.response:
            error_code = exc.response.get("Error", {}).get("Code", "")
        if error_code in ("404", "NoSuchBucket", "403"):
            log.info("Creating S3 bucket: %s in %s", bucket, region)
            if region == "us-east-1":
                s3_client.create_bucket(Bucket=bucket)
            else:
                s3_client.create_bucket(
                    Bucket=bucket,
                    CreateBucketConfiguration={"LocationConstraint": region},
                )
            s3_client.put_public_access_block(
                Bucket=bucket,
                PublicAccessBlockConfiguration={
                    "BlockPublicAcls":       True,
                    "IgnorePublicAcls":      True,
                    "BlockPublicPolicy":     True,
                    "RestrictPublicBuckets": True,
                },
            )
            log.info("S3 bucket created with public access blocked")
        else:
            raise


def apply_s3_retention(s3_client, bucket: str, retain: int, dry_run: bool):
    """Delete oldest backups in S3, keeping the most recent `retain` files."""
    paginator = s3_client.get_paginator("list_objects_v2")
    objects = []
    for page in paginator.paginate(Bucket=bucket, Prefix=S3_PREFIX):
        objects.extend(page.get("Contents", []))

    # Sort oldest first
    objects.sort(key=lambda o: o["LastModified"])
    to_delete = objects[:-retain] if len(objects) > retain else []

    if not to_delete:
        log.info(
            "Retention: %d backup(s) in S3, within limit of %d — nothing to delete",
            len(objects), retain,
        )
        return

    log.info("Retention: keeping %d, deleting %d old backup(s)", retain, len(to_delete))
    for obj in to_delete:
        if dry_run:
            log.info("[DRY-RUN] Would delete s3://%s/%s", bucket, obj["Key"])
        else:
            s3_client.delete_object(Bucket=bucket, Key=obj["Key"])
            log.info("Deleted s3://%s/%s", bucket, obj["Key"])


# ── SSH / SFTP helpers ────────────────────────────────────────────────────────

def run_ssh_command(ssh: paramiko.SSHClient, cmd: str, timeout: int = CMD_TIMEOUT) -> str:
    """Run a shell command over SSH; raises RuntimeError on non-zero exit."""
    log.debug("SSH CMD: %s", cmd)
    _, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    exit_code = stdout.channel.recv_exit_status()
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if exit_code != 0:
        raise RuntimeError(f"Command failed (exit {exit_code}): {err or out}")
    return out


def sftp_download(ssh: paramiko.SSHClient, remote_path: str, local_path: str):
    """Download a single file from the SSH host via SFTP."""
    sftp = ssh.open_sftp()
    try:
        log.info("SFTP download: %s → %s", remote_path, local_path)
        sftp.get(remote_path, local_path)
    finally:
        sftp.close()


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description="OSM MongoDB Backup to S3")
    p.add_argument(
        "--region",
        default=os.environ.get("AWS_REGION", DEFAULT_REGION),
        help="AWS region (default: ap-southeast-1)",
    )
    p.add_argument(
        "--key-file",
        default=os.environ.get("OSM_KEY_FILE", "../osm-key.pem"),
        help="Path to SSH private key (default: ../osm-key.pem)",
    )
    p.add_argument(
        "--s3-bucket",
        default=os.environ.get("OSM_S3_BUCKET", ""),
        help="S3 bucket name (auto-named as osm-mongodb-backups-<account_id> if omitted)",
    )
    p.add_argument(
        "--retain",
        type=int,
        default=int(os.environ.get("OSM_RETAIN", str(DEFAULT_RETAIN))),
        help=f"Number of backups to keep in S3 (default: {DEFAULT_RETAIN})",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        default=os.environ.get("OSM_DRY_RUN", "").lower() == "true",
        help="Preview actions without executing",
    )
    return p.parse_args()


def main():
    args  = parse_args()
    start = datetime.now(timezone.utc)

    log.info("=" * 62)
    log.info("OSM MongoDB Backup  —  %s", start.strftime("%Y-%m-%d %H:%M:%S UTC"))
    log.info("Region   : %s", args.region)
    log.info("Retain   : %d backups in S3", args.retain)
    if args.dry_run:
        log.info("DRY-RUN  : enabled (no changes will be made)")
    log.info("=" * 62)

    key_path = Path(args.key_file).expanduser().resolve()
    if not key_path.exists():
        log.error("SSH key not found: %s", key_path)
        log.error("Provide --key-file <path> or set OSM_KEY_FILE env variable")
        sys.exit(1)

    s3_key = None

    try:
        session    = boto3.Session(region_name=args.region)
        ec2_client = session.client("ec2")
        s3_client  = session.client("s3")
        sts_client = session.client("sts")

        account_id = get_account_id(sts_client)
        bucket     = args.s3_bucket or f"osm-mongodb-backups-{account_id}"
        log.info("S3 bucket: %s", bucket)

        # ── Locate MongoDB EC2 ─────────────────────────────────────────────────
        mongodb_ip = get_mongodb_private_ip(ec2_client)

        if args.dry_run:
            log.info("[DRY-RUN] Would SSH to %s and run %s", mongodb_ip, BACKUP_SCRIPT)
            log.info("[DRY-RUN] Would upload archive to s3://%s/%s", bucket, S3_PREFIX)
            log.info("[DRY-RUN] Would apply retention: keep %d backups", args.retain)
            return

        # ── Connect via SSH ────────────────────────────────────────────────────
        log.info("Connecting via SSH to %s ...", mongodb_ip)
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(
            hostname  = mongodb_ip,
            port      = SSH_PORT,
            username  = SSH_USER,
            key_filename = str(key_path),
            timeout   = SSH_TIMEOUT,
        )
        log.info("SSH connection established")

        try:
            # ── Trigger the Ansible-managed backup script ──────────────────────
            log.info("Running backup script on MongoDB EC2 ...")
            out = run_ssh_command(ssh, f"sudo bash {BACKUP_SCRIPT}", timeout=CMD_TIMEOUT)
            if out:
                for line in out.splitlines():
                    log.info("  [remote] %s", line)

            # ── Locate the newest backup archive ───────────────────────────────
            latest = run_ssh_command(
                ssh,
                f"ls -t {BACKUP_DIR}/backup_*.tar.gz 2>/dev/null | head -1",
            )
            if not latest:
                raise RuntimeError(
                    f"No backup archive found in {BACKUP_DIR} after running script"
                )
            log.info("Latest backup archive: %s", latest)

            backup_filename = os.path.basename(latest)
            s3_key          = f"{S3_PREFIX}{backup_filename}"

            # ── Ensure S3 bucket exists ────────────────────────────────────────
            ensure_s3_bucket(s3_client, bucket, args.region)

            # ── SFTP → local temp file → S3 ───────────────────────────────────
            with tempfile.NamedTemporaryFile(
                suffix=".tar.gz", prefix="osm-backup-", delete=False
            ) as tmp:
                local_tmp = tmp.name

            try:
                sftp_download(ssh, latest, local_tmp)

                log.info("Uploading to s3://%s/%s ...", bucket, s3_key)
                s3_client.upload_file(
                    local_tmp, bucket, s3_key,
                    ExtraArgs={"ServerSideEncryption": "AES256"},
                )
                log.info("Upload complete")

            finally:
                if os.path.exists(local_tmp):
                    os.remove(local_tmp)

        finally:
            ssh.close()
            log.info("SSH connection closed")

        # ── Apply S3 retention ─────────────────────────────────────────────────
        apply_s3_retention(s3_client, bucket, args.retain, dry_run=False)

        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        log.info("=" * 62)
        log.info("Backup COMPLETED in %.1fs", elapsed)
        log.info("Location : s3://%s/%s", bucket, s3_key)
        log.info("=" * 62)

    except Exception as exc:
        log.error("=" * 62)
        log.error("Backup FAILED: %s", exc, exc_info=True)
        log.error("=" * 62)
        sys.exit(1)


if __name__ == "__main__":
    main()
