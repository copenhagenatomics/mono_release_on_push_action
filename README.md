# mono_release_on_push

This repository contains a GitHub Action that generates a release based on information given and works with monolithic repository architectures. It pumps up the minor releases based on a tracked major release and returns a full tag name that can be used for publishing the release.

## Usage

Use it in a Github workflow as given in the example below.

### Example workflow

```yaml
name: Testing mono_release_on_push

on: [push]

jobs:
  build:

    runs-on: ubuntu-latest

    steps:
		- uses: copenhagenatomics/mono_release_on_push_action@master
		      id: release-on-push
		      with:
		        bump_version_scheme: minor
		        use_github_release_notes: true
		        tag_prefix: "${{ matrix.package }}-"
		      env:
		        GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

### Inputs

| Input | Description |
| --- | --- |
| bump_version_scheme | The bumping scheme to use by default. One of minor|major|patch|norelease |
| release_body (optional) | Additional text to insert into the release's body. |
| tag_prefix (optional) | Prefix to append to git tags. To unset this, set version_prefix to an empty string. |
| release_name | Name of the release. Supports these template variables: <RELEASE_VERSION> the version number, e.g. "1.2.3"
<RELEASE_TAG> the git tag name, e.g. "v1.2.3” |
| max_commits (optional) | Maximum number of commits to add to release body |
| use_github_release_notes (optional) | When set to 'true', uses Github's Generated Release Notes instead of this plugin's release notes |
| dry_run (optional) | When set to 'true', will compute the next tag, but will not create a release. |

### Outputs

| Output | Description |
| --- | --- |
| tag_name | Tag of released version |
| version | Version of release |
| body | Github Release Body in Text |
| upload_url | Github Release Upload URL |