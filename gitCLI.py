import requests
import json

# -- Generic HTTP Helpers  ----------------------------------------------------

def link_header_to_map(link_header):
    """Converts link header into a dictionary of rel -> link. This implementation is not standards compliant.
    See https://tools.ietf.org/html/rfc5988"""
    return dict(re.findall(r'<([^>]+)>; rel="([^"]+)"', link_header))

def with_links(response):
    if 'link' in response.headers:
        response.__dict__['links'] = link_header_to_map(response.headers['link'])
    return response

def parse_response(resp):
    resp = with_links(resp)
    resp.body = json.loads(resp.content)
    return resp

def headers(context):
    return {"Authorization": f"token {context['token']}"}

# -- Pagination helpers using token  ------------------------------------------

def follow_link(context, link):
    return parse_response(requests.get(link, headers=headers(context)))

def paginate(context, response):
    if 'next' in response.links:
        return [response] + paginate(context, follow_link(context, response.links['next']['url']))
    else:
        return [response]

# -- Github PRs API  ----------------------------------------------------------

def fetch_related_prs(context):
    url = f"{context['github']['api-url']}/repos/{context['repo']}/commits/{context['sha']}/pulls"
    return parse_response(requests.get(url, headers=headers(context)))

# -- Github Releases API  -----------------------------------------------------

def fetch_latest_release(context):
    url = f"{context['github']['api-url']}/repos/{context['repo']}/releases/latest"
    try:
        return parse_response(requests.get(url, headers=headers(context)))
    except requests.exceptions.RequestException as ex:
        if ex.response.status_code == 404:
            print("No release found for project.")
        else:
            raise ex
        
import requests
import re

def fetch_latest_release_custom(context, *tag_prefix):
    """
    Gets the latest commit. Returns None when there is no release.
    See https://developer.github.com/v3/repos/releases/#get-the-latest-release
    """
    try:
        response = requests.get(
            f"{context['github']['api-url']}/repos/{context['repo']}/releases",
            headers=headers(context)
        )
        response.raise_for_status()  # Raise an error for non-2xx status codes
        releases = response.json()
        return find_release_by_tag(releases, tag_prefix[0] if tag_prefix else "v")
    except requests.exceptions.RequestException as e:
        if isinstance(e, requests.exceptions.HTTPError) and e.response.status_code == 404:
            print("No release found for project.")
            return None
        else:
            raise e
        
        
def find_release_by_tag(releases, tag_str):
    """
    Finds the latest release with the given tag prefix in the list of releases.
    """
    sorted_releases = sorted(releases, key=lambda release: release['tag_name'], reverse=True)
    for release in sorted_releases:
        if re.search(tag_str, release['tag_name']):
            return release
    return None

# -- Github Commit API  -------------------------------------------------------

def fetch_commit(context):
    url = f"{context['github']['api-url']}/repos/{context['repo']}/commits/{context['sha']}"
    return parse_response(requests.get(url, headers=headers(context)))

def list_commits(context):
    url = f"{context['github']['api-url']}/repos/{context['repo']}/commits"
    params = {"sha": context['sha']}
    return parse_response(requests.get(url, headers=headers(context), params=params))

def list_commits_to_base(context, base=None):
    response_pages = paginate(context, list_commits(context))
    commits = [commit for page in response_pages for commit in page.body]
    if base:
        index = next((i for i, commit in enumerate(commits) if commit['sha'] == base), None)
        if index is None:
            return []
        else:
            return commits[:index]
    else:
        return commits

# -- Formatting  --------------------------------------------------------------

def commit_title(commit):
    return commit['commit']['message'].split('\n')[0]

def commit_summary(commit):
    return f"- [{commit['sha'][:8]}] {commit_title(commit)}"

# Testing
if __name__ == '__main__':
    context = {"repo": "copenhagenatomics/CA_Embedded",
               "github":{"api-url" : "https://api.github.com"}, 
               "sha": "1f188ecad5dc2279e6b6235b9d2cc85406ef03e0",
               "token" : "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",
               "headers" : {
                "Authorization": "Bearer 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",
                "Accept": "application/vnd.github.v3+json",
                }
            }
    

    print(fetch_latest_release_custom(context,"LightController")["tag_name"])
