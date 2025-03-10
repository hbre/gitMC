"""
This was the original implementation of mass-checking of Git status
using asyncio and subprocesses. It is much more efficient to use
libgit2 via pygit2, which is the current implementation.

replaced by git status --porcelain:
  git ls-files -o -d --exclude-standard: # check for uncommitted files
  git --no-pager diff HEAD , # check for uncommitted work

DOES NOT WORK git log --branches --not --remotes     # check for uncommitted branches
"""

import subprocess
import logging
from pathlib import Path
import asyncio

from .git import gitdirs, git_exe, subprocess_asyncio, MAGENTA, BLACK, TIMEOUT

C0 = ["rev-parse", "--abbrev-ref", "HEAD"]  # get branch name
C1 = ["status", "--porcelain"]  # uncommitted or changed files

__all__ = ["git_porcelain"]


def git_porcelain(path: Path, timeout: float = TIMEOUT["local"]) -> bool:
    """
    detects if single Git repo is porcelain i.e. clean.
    May not have been pushed or fetched.

    Parameters
    ----------

    path: pathlib.Path
        path to Git repo

    Returns
    -------

    is_porcelain: bool
        true if local Git is clean
    """

    if not path.is_dir():
        raise NotADirectoryError(path)

    ret = subprocess.run(
        [git_exe(), "-C", str(path)] + C1,
        stdout=subprocess.PIPE,
        text=True,
        timeout=timeout,
    )
    if ret.returncode != 0:
        logging.error(f"{path.name} return code {ret.returncode}  {C1}")
        return False
    return not ret.stdout


async def _git_status(path: Path, timeout: float) -> tuple[str, str] | None:
    """
    Notes which Git repos have local changes that haven't been pushed to remote

    Parameters
    ----------
    path : pathlib.Path
        Git repo directory

    Returns
    -------
    changes : tuple of pathlib.Path, str
        Git repo local changes
    """

    code, out, err = await subprocess_asyncio([git_exe(), "-C", str(path)] + C1, timeout=timeout)
    if code != 0:
        logging.error(f"{path.name} return code {code}  {C1}  {err}")
        return None

    logging.info(path.name)

    # %% uncommitted changes
    if out:
        return path.name, out

    # %% detect committed, but not pushed
    code, branch, err = await subprocess_asyncio([git_exe(), "-C", str(path)] + C0, timeout=timeout)
    if code != 0:
        logging.error(f"{path.name} return code {code}  {C0}  {err}")
        return None

    C2 = [git_exe(), "-C", str(path), "diff", "--stat", f"origin/{branch}.."]
    code, out, err = await subprocess_asyncio(C2, timeout=timeout)
    if code != 0:
        logging.error(f"{path.name} return code {code}  {branch} {out}  {err}")
        return None

    if out:
        return path.name, out

    return None


def git_status_serial(path: Path, timeout: float = TIMEOUT["local"]) -> tuple[str, str] | None:
    """

    Notes which Git repos have local changes that haven't been pushed to remote

    Parameters
    ----------
    path : pathlib.Path
        Git repo directory

    Returns
    -------
    changes : tuple of pathlib.Path, str
        Git repo local changes
    """

    out = subprocess.check_output(
        [git_exe(), "-C", str(path)] + C1, text=True, timeout=timeout
    ).strip()

    logging.info(path.name)

    # %% uncommitted changes
    if out:
        return path.name, out

    # %% detect committed, but not pushed
    branch = subprocess.check_output(
        [git_exe(), "-C", str(path)] + C0, text=True, timeout=timeout
    ).strip()

    C2 = [git_exe(), "-C", str(path), "diff", "--stat", f"origin/{branch}.."]
    out = subprocess.check_output(C2, text=True, timeout=timeout).strip()

    if out:
        return path.name, out

    return None


async def git_status_async(path: Path, verbose: bool, timeout: float) -> list[str]:
    c = MAGENTA if verbose else ""

    changed = []
    futures = [_git_status(d, timeout) for d in gitdirs(path)]
    for r in asyncio.as_completed(futures, timeout=timeout):
        if changes := await r:
            changed.append(changes[0])
            print(c + changes[0])
            if verbose:
                print(BLACK + changes[1])

    return changed
