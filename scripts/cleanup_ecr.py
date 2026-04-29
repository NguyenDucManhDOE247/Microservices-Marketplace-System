#!/usr/bin/env python3
"""
cleanup_ecr.py — ECR Image Cleanup for osm-* Repositories

For each osm-* repository:
  1. Deletes ALL untagged images immediately
  2. Keeps the K most recent tagged images, deletes older ones

Usage:
  python cleanup_ecr.py
  python cleanup_ecr.py --region ap-southeast-1 --keep 10
  python cleanup_ecr.py --dry-run

Environment variables:
  AWS_REGION    AWS region (default: ap-southeast-1)
  ECR_KEEP      Tagged images to keep per repo (default: 10)
  ECR_DRY_RUN   "true" to preview without deleting

Exit codes:
  0  Cleanup completed
  1  Error
"""

import argparse
import logging
import os
import sys
from datetime import datetime, timezone

try:
    import boto3
except ImportError:
    print("ERROR: boto3 not installed — run: pip install -r requirements.txt")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

DEFAULT_REGION = "ap-southeast-1"
DEFAULT_KEEP   = 10
REPO_PREFIX    = "osm-"


# ── Helpers ───────────────────────────────────────────────────────────────────

def list_osm_repos(ecr_client) -> list:
    """Return sorted list of ECR repository names matching osm-* prefix."""
    repos = []
    paginator = ecr_client.get_paginator("describe_repositories")
    for page in paginator.paginate():
        for repo in page["repositories"]:
            if repo["repositoryName"].startswith(REPO_PREFIX):
                repos.append(repo["repositoryName"])
    return sorted(repos)


def list_images(ecr_client, repo: str) -> tuple:
    """Return (tagged_sorted_newest_first, untagged) image detail lists."""
    paginator  = ecr_client.get_paginator("describe_images")
    all_images = []
    for page in paginator.paginate(repositoryName=repo):
        all_images.extend(page.get("imageDetails", []))

    tagged   = [img for img in all_images if img.get("imageTags")]
    untagged = [img for img in all_images if not img.get("imageTags")]

    # Sort tagged: newest push date first
    tagged.sort(
        key=lambda img: img.get(
            "imagePushedAt",
            datetime.min.replace(tzinfo=timezone.utc),
        ),
        reverse=True,
    )
    return tagged, untagged


def delete_images(ecr_client, repo: str, images: list, dry_run: bool) -> int:
    """
    Batch-delete images from an ECR repository.
    ECR batch limit is 100 image IDs per call.
    Returns count of image IDs queued for deletion.
    """
    if not images:
        return 0

    ids = []
    for img in images:
        if img.get("imageTags"):
            for tag in img["imageTags"]:
                ids.append({"imageTag": tag})
        else:
            ids.append({"imageDigest": img["imageDigest"]})

    deleted = 0
    for i in range(0, len(ids), 100):
        batch = ids[i : i + 100]
        if dry_run:
            for item in batch:
                label = item.get("imageTag") or item.get("imageDigest", "")[:12] + "..."
                log.info("[DRY-RUN] Would delete  %s : %s", repo, label)
            deleted += len(batch)
        else:
            resp = ecr_client.batch_delete_image(
                repositoryName=repo, imageIds=batch
            )
            n = len(resp.get("imageIds", []))
            deleted += n
            for fail in resp.get("failures", []):
                log.warning(
                    "Delete failed in %s: %s — %s",
                    repo,
                    fail.get("imageId"),
                    fail.get("failureReason"),
                )
    return deleted


def fmt_size(bytes_val) -> str:
    if not bytes_val:
        return "?"
    for unit in ("B", "KB", "MB", "GB"):
        if bytes_val < 1024:
            return f"{bytes_val:.1f} {unit}"
        bytes_val /= 1024
    return f"{bytes_val:.1f} TB"


def fmt_date(pushed_at) -> str:
    if hasattr(pushed_at, "strftime"):
        return pushed_at.strftime("%Y-%m-%d %H:%M")
    return str(pushed_at)


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description="OSM ECR Image Cleanup")
    p.add_argument(
        "--region",
        default=os.environ.get("AWS_REGION", DEFAULT_REGION),
        help="AWS region (default: ap-southeast-1)",
    )
    p.add_argument(
        "--keep",
        type=int,
        default=int(os.environ.get("ECR_KEEP", str(DEFAULT_KEEP))),
        help=f"Tagged images to keep per repository (default: {DEFAULT_KEEP})",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        default=os.environ.get("ECR_DRY_RUN", "").lower() == "true",
        help="Preview without deleting any images",
    )
    return p.parse_args()


def main():
    args = parse_args()

    log.info("=" * 62)
    log.info(
        "OSM ECR Cleanup  —  %s",
        datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
    )
    log.info("Region  : %s", args.region)
    log.info("Keep    : %d tagged images per repo", args.keep)
    if args.dry_run:
        log.info("DRY-RUN : enabled (no images will be deleted)")
    log.info("=" * 62)

    try:
        ecr_client = boto3.client("ecr", region_name=args.region)

        repos = list_osm_repos(ecr_client)
        if not repos:
            log.warning(
                "No ECR repositories found with prefix '%s' in %s",
                REPO_PREFIX, args.region,
            )
            return

        log.info("Repositories (%d): %s", len(repos), ", ".join(repos))

        total_deleted  = 0
        total_untagged = 0
        total_old      = 0

        for repo in repos:
            log.info("")
            log.info("── %s ──", repo)
            tagged, untagged = list_images(ecr_client, repo)
            log.info("  Tagged: %d  |  Untagged: %d", len(tagged), len(untagged))

            # 1. Delete all untagged images
            if untagged:
                n = delete_images(ecr_client, repo, untagged, args.dry_run)
                log.info("  Untagged deleted: %d", n)
                total_untagged += n
                total_deleted  += n
            else:
                log.info("  No untagged images")

            # 2. Keep newest K tagged; delete the remainder
            keep_imgs   = tagged[: args.keep]
            delete_imgs = tagged[args.keep :]

            log.info("  Keeping %d tagged image(s):", len(keep_imgs))
            for img in keep_imgs:
                tags = ", ".join(img.get("imageTags", []))
                log.info(
                    "    ✓  %-22s  pushed=%s  size=%s",
                    tags,
                    fmt_date(img.get("imagePushedAt")),
                    fmt_size(img.get("imageSizeInBytes")),
                )

            if delete_imgs:
                log.info("  Deleting %d old tagged image(s):", len(delete_imgs))
                for img in delete_imgs:
                    tags = ", ".join(img.get("imageTags", []))
                    log.info(
                        "    ✗  %-22s  pushed=%s  size=%s",
                        tags,
                        fmt_date(img.get("imagePushedAt")),
                        fmt_size(img.get("imageSizeInBytes")),
                    )
                n = delete_images(ecr_client, repo, delete_imgs, args.dry_run)
                total_old     += n
                total_deleted += n
            else:
                log.info("  No old tagged images to delete")

        log.info("")
        log.info("=" * 62)
        log.info("SUMMARY")
        log.info("  Repositories processed     : %d", len(repos))
        log.info("  Untagged images deleted    : %d", total_untagged)
        log.info("  Old tagged images deleted  : %d", total_old)
        log.info("  Total deleted              : %d", total_deleted)
        if args.dry_run:
            log.info("  (DRY-RUN — no actual deletions performed)")
        log.info("=" * 62)

    except Exception as exc:
        log.error("=" * 62)
        log.error("ECR cleanup FAILED: %s", exc, exc_info=True)
        log.error("=" * 62)
        sys.exit(1)


if __name__ == "__main__":
    main()
