# GitHub profile mission control

The profile is a set of GitHub-compatible SVG images, ordinary Markdown links and a public JSON snapshot. No JavaScript, image proxy service, external font, or embedded HTML app is required. Desktop cards are 840 px wide; `<picture>` selects 420 px cards for narrow screens. The mobile calendar wraps into two bands rather than shrinking a full year into unreadable cells.

## Configure your profile

1. Put these files in the public repository **`YOUR_USERNAME/YOUR_USERNAME`**, on its default `main` branch. For this profile, the configured username is **`PunithRajuJanardhana`**.
2. Edit **[`dashboard.config.json`](../dashboard.config.json)**:
   - `username`: the GitHub account whose owned public repositories to scan.
   - `headline` and `focus`: the opening message visitors see.
   - `include_forks` and `include_archived`: booleans controlling language and technology aggregation. Both default to `false`.
   - `featured`: zero to four owned public repository names, in display order. Give each a `description` and optionally a `demo` URL. Without an override, GitHub's description and homepage are used. Private, missing or externally owned featured repositories fail the refresh rather than expose data or silently disappear.
   - `links`: portfolio, contact or other destinations.
3. Open **Settings → Actions → General** and make sure Actions may run and the workflow may write repository contents. Organization policies or branch protection may require an allowed bot or a pull-request-based update flow. The workflow explicitly requests `contents: write`.
4. Commit and push the configuration, script and workflow. Open **Actions → Refresh profile dashboard → Run workflow → main** to trigger the first refresh. The workflow also runs when its configuration/code changes and requests an hourly run at minute 17 UTC.
5. Check that the run succeeds and commits `README.md` plus `assets/`. Those files must remain committed so GitHub can display the last successful version at any time.

GitHub schedules are best effort: runs can be delayed, and scheduled workflows in inactive public repositories can be disabled after 60 days. The visible **Last successful sync** is the actual fetch timestamp, never an assumed schedule time. You can always run the workflow manually. GitHub's image cache and contribution attribution can delay what a visitor sees.

## Credentials

The workflow uses the automatically supplied **`${{ secrets.GITHUB_TOKEN }}`** for authenticated API rate limits and pushing commits. No personal access token or additional secret is required for a standard public profile repository. Never put credentials in JSON, README content or committed files. The generator reads `GH_TOKEN` or `GITHUB_TOKEN` from its environment and never stores them in outputs.

The contribution calendar is fetched **without authentication** from GitHub's public profile calendar. This ensures that owner-only information cannot appear when a broad credential is available. If you enable anonymous private contributions on your profile, the same anonymous daily counts visible to visitors may appear here. Private repository identities, counts, languages and files are never queried.

## Run locally

Python 3.10+ is the only dependency:

```sh
python3 -m unittest discover -s tests -v
python3 scripts/dashboard.py
```

Public API calls work without a token but can hit GitHub's unauthenticated rate limit, especially for larger profiles. Set an environment token through your usual secret manager if necessary. Do not commit a `.env` file. With no token, all requests remain public.

To iterate on SVG styling using the existing real-data snapshot:

```sh
python3 scripts/dashboard.py --render-only
```

This preserves the snapshot's original timestamp. It does not simulate new data or claim a fresh sync.

## What the numbers mean

| Metric | Definition |
| --- | --- |
| Public repositories | All owned public repositories, including forks and archived repositories; fully paginated |
| Total / private repositories | Always `?`. An exact total could reveal the private count by subtracting the public count |
| Days on GitHub | Difference between the current UTC date and the account creation date; join date shown separately |
| Total stars | Sum of stars across all owned public repositories |
| Contribution year | Exactly 365 UTC dates ending today, taken from the public GitHub contribution calendar |
| Current streak | Consecutive nonzero dates ending today; if today is zero, count backward from yesterday |
| Longest streak | Longest run of nonzero dates inside the displayed 365-day window, not a lifetime streak |
| 30-day chart | Daily contribution counts for the final 30 dates of the same calendar |
| Languages | Sum of GitHub-reported language bytes across included owned public repositories; not skill levels |
| Technology counts | Distinct included repositories with matching dependency, public topic or configuration evidence |
| Recent activity | Latest five available release/PR events and owned-repo push timestamps, sorted newest first |

The account's own profile repository is excluded from recent activity so automatic dashboard commits do not masquerade as project progress. GitHub's public events API has a limited history; repository push timestamps fill gaps. A repository update date is the API's `pushed_at`, not an invented release or PR. Recent work outside owned repositories can appear if the public event is visible. No missing event is fabricated.

## Scope and evidence

The README lists every included repository. [`assets/dashboard.json`](../assets/dashboard.json) contains daily dates and counts, language bytes, featured metadata, and repository/file evidence for every technology. Frameworks, databases and infrastructure have separate categories. Each repository contributes at most one count per technology.

The detector reads public dependency manifests (including nested `package.json`, Python requirements and project manifests, Maven/Gradle files), repository topics, Docker/Compose paths, Actions workflows, Terraform files and Kubernetes manifests in `k8s/` or `kubernetes/` folders. Development dependencies count as usage. SDKs and database drivers indicate integration evidence, not a claim that a service is deployed. Code hidden in skipped dependency/build folders, unusual filenames, runtime-only imports or remote configuration may not be detected. Add identifiers to `DEPENDENCIES` and matching rules in `scripts/dashboard.py` when needed.

The fork/archive switches affect language and technology aggregation only. Featured projects are manually selected and can be inspected even if excluded by those switches. Public overview counts and stars always include every owned public repository.

## Failure behavior

All remote fetches and SVG validation finish in a temporary staging directory before output files are replaced. An HTTP error, rate limit, incomplete calendar, truncated repository tree or invalid featured project stops the job. There is no fallback to zero or fake stats. The workflow commits only after a successful render, so the published last good dashboard and sync time remain intact on failure. A concurrent manual push can cause the bot push to fail safely; rerun the workflow against the latest branch.

The generated README is overwritten on refresh. Edit the config for content and the renderer for layout. Keep this setup guide separate so it survives refreshes.

## GitHub references

- [Public repository listing](https://docs.github.com/en/rest/repos/repos#list-repositories-for-a-user)
- [Repository language bytes](https://docs.github.com/en/rest/repos/repos#list-repository-languages)
- [Contribution visibility](https://docs.github.com/en/account-and-profile/how-tos/contribution-settings/manage-visibility-settings-for-private-contributions-and-achievements)
- [Scheduled workflow behavior](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)
- [GITHUB_TOKEN authentication](https://docs.github.com/en/actions/tutorials/authenticate-with-github_token)
