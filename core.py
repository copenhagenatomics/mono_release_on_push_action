import os
import requests
import uuid
from typing import Dict, List, Union
import tempfile
import json

from gitCLI import *

# Configuration Parsing
def getenv_or_throw(name):
    val = os.getenv(name)
    if not val:
        raise Exception(f"Expected environment variable to be set: {name}")
    return val

def input_strategy_set():
    if os.getenv("INPUT_STRATEGY"):
        print("WARNING: the action property `strategy` has been renamed `bump_version_scheme`. Support for `strategy` will be removed in the future. See the rymndhng/release-on-push-action README for the current configuration")
        return True
    return False

def assert_valid_bump_version_scheme(bump_version_scheme):
    valid_bump_version_schemes = {"major", "minor", "patch", "norelease"}
    if bump_version_scheme not in valid_bump_version_schemes:
        raise Exception(f"Invalid bump-version-scheme. Expected one of major|minor|patch|norelease. Got: {bump_version_scheme}")
    return bump_version_scheme

def context_from_env(args):
    return {
        "token": getenv_or_throw("GITHUB_TOKEN"),
        "repo": getenv_or_throw("GITHUB_REPOSITORY"),
        "sha": getenv_or_throw("GITHUB_SHA"),
        "github" : {
            "api-url": getenv_or_throw("GITHUB_API_URL"),
            "output": os.getenv("GITHUB_OUTPUT"),
            "token": getenv_or_throw("GITHUB_TOKEN")
        },
        "input" : {
            "max-commits": int(getenv_or_throw("INPUT_MAX_COMMITS")),
            "release-body": os.getenv("INPUT_RELEASE_BODY"),
            "tag-prefix": os.getenv("INPUT_TAG_PREFIX") or "v",
            "release-name": os.getenv("INPUT_RELEASE_NAME") or "<RELEASE_TAG>",
            "use-github-release-notes": bool(os.getenv("INPUT_USE_GITHUB_RELEASE_NOTES")),
        },
        "bump-version-scheme": assert_valid_bump_version_scheme(os.getenv("INPUT_BUMP_VERSION_SCHEME") or input_strategy_set() or "patch"),
        "dry-run": bool(int(os.getenv("INPUT_DRY_RUN"))) or "--dry-run" in args
    }

# Version Bumping Logic
def fetch_related_data(context):
    latest_release = fetch_latest_release_custom(context,context['input']['tag-prefix'])
    context["sha"] = latest_release['target_commitish']
    return {
        'related-prs': fetch_related_prs(context).body,
        'commit': fetch_commit(context).body,
        'latest-release': latest_release,
        'latest-release-commit': fetch_commit(context).body
        if latest_release["tag_name"] else None
    }


def get_label_names(related_prs):
    return set(label['name'] for pr in related_prs for label in pr['labels'])

def bump_version_scheme(context, related_data) -> str:
    labels = get_label_names(related_data['related_prs'])
    if 'release:major' in labels:
        return 'major'
    elif 'release:minor' in labels:
        return 'minor'
    elif 'release:patch' in labels:
        return 'patch'
    else:
        return context.get('bump_version_scheme', '')

def get_tagged_version(latest_release) -> str:
    tag = latest_release.get('tag_name', '0.0.0')
    return tag.split('v')[-1]

def safe_inc(n: Union[int, None]) -> int:
    return n + 1 if n is not None else 1

def semver_bump(version: str, bump: str) -> str:
    major, minor, patch = map(int, version.split('.'))
    if bump == 'major':
        return f'{safe_inc(major)}.0.0'
    elif bump == 'minor':
        return f'{major}.{safe_inc(minor)}.0'
    elif bump == 'patch':
        return f'{major}.{minor}.{safe_inc(patch)}'
    else:
        raise ValueError(f'Invalid semver bump: {bump}')

def norelease_reason(context, related_data) -> str:
    if bump_version_scheme(context, related_data) == 'norelease':
        return 'Skipping release, no version bump found.'
    elif related_data['commit'] and '[norelease]' in related_data['commit'].get('title', ''):
        return 'Skipping release. Reason: git commit title contains [norelease]'
    elif 'related_prs' in related_data and related_data['related_prs'] and \
         'labels' in related_data['related_prs'][0] and \
         'norelease' in get_label_names(related_data['related_prs']):
        return 'Skipping release. Reason: related PR has label norelease'
    else:
        return ''

def get_labels(related_prs):
    labels = set()
    for pr in related_prs:
        if 'labels' in pr and pr['labels']:
            labels.update(label['name'] for label in pr['labels'])
    return labels


def bump_version_scheme(context, related_data):
    labels = get_labels(related_data.get('related-prs', {}))
    if 'release:major' in labels:
        return 'major'
    elif 'release:minor' in labels:
        return 'minor'
    elif 'release:patch' in labels:
        return 'patch'
    else:
        return context.get('bump-version-scheme', None)

def get_tagged_version(latest_release):
    tag = latest_release.get('tag_name', '0.0.0')
    prefix = re.findall(r'^\D*', tag)[0]
    return tag[len(prefix):]

def safe_inc(n):
    return n + 1 if n else 1

def semver_bump(version, bump):
    major, minor, patch = map(int, version.split('.'))
    if bump == 'major':
        next_version = (safe_inc(major), 0, 0)
    elif bump == 'minor':
        next_version = (major, safe_inc(minor), 0)
    elif bump == 'patch':
        next_version = (major, minor, safe_inc(patch))
    return '.'.join(str(part) for part in next_version)

def generate_new_release_data(context, related_data):
    bump_version_scheme_inst = bump_version_scheme(context, related_data)
    current_version = get_tagged_version(related_data["latest-release"])
    next_version = semver_bump(current_version, bump_version_scheme_inst)
    base_commit = related_data["latest-release-commit"]["sha"]
    tag_name = context["input"]["tag-prefix"] + next_version

    commits_since_last_release = [
        commit_summary(commit)
        for commit in list_commits_to_base(context, base_commit)[:context["input"]["max-commits"]]
    ]

    body = f"Version {next_version}\n\n"
    if context["input"]["release-body"]:
        body += context["input"]["release-body"] + "\n\n"

    if not context["input"]["use-github-release-notes"]:
        body += "### Commits\n\n"
        body += "\n".join(commits_since_last_release)

    return {
        "tag_name": tag_name,
        "target_commitish": context["sha"],
        "name": context["input"]["release-name"]
            .replace("<RELEASE_VERSION>", next_version)
            .replace("<RELEASE_TAG>", tag_name),
        "body": body,
        "draft": False,
        "prerelease": False,
        "generate_release_notes": context["input"]["use-github-release-notes"],
    }

def create_new_release(context, new_release_data):
    with tempfile.NamedTemporaryFile(suffix=".json") as file:
        file.write(json.dumps(new_release_data).encode())
        file.flush()

        headers = {
            "Authorization": f"Bearer {context['github']['token']}",
            "Accept": "application/vnd.github.v3+json",
        }

        response = requests.post(
            f"{context['github']['api-url']}/repos/{context['repo']}/releases",
            headers=headers,
            json=new_release_data,
        )

        response.raise_for_status()

def prepare_key_value(key, value, delimiter=None):
    delimiter = delimiter or f"delimiter_{uuid.uuid1()}"
    return f"{key}<<{delimiter}\n{value}\n{delimiter}"

def set_output_parameters(context, release_data):
    out = open(context.get("github", {}).get("output")) if context.get("github", {}).get("output") else None

    print(prepare_key_value("tag_name", release_data["tag_name"]), file=out)
    print(prepare_key_value("version", release_data["name"]), file=out)
    print(prepare_key_value("upload_url", release_data.get("upload_url", "")), file=out)
    print(prepare_key_value("body", release_data["body"]), file=out)

def main(*args):
    print("Starting process...")
    context = context_from_env(args)
    print("Received context", context)  # in GitHub actions the secrets are printed as '***'
    print("Fetching related data...")
    related_data = fetch_related_data(context)
    reason = norelease_reason(context, related_data)
    if (reason is not ''):
        print("Skipping release:", reason)
        sys.exit(0)

    print("Generating release...")
    release_data = generate_new_release_data(context, related_data)
    if context["dry-run"]:
        print("Dry Run. Not performing release\n", json.dumps(release_data, indent=2))
        print("Release Body")
        print(release_data["body"])
    else:
        print("Executing Release\n", json.dumps(release_data, indent=2))
        create_new_release(context, release_data)
    set_output_parameters(context, release_data)

if __name__ == "__main__":
    main()