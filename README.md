# Awesome Starred Projects

This repository auto-builds an awesome list from your GitHub starred repositories.

## Quick setup

1. Create a GitHub Personal Access Token (PAT).
2. In this repository, go to `Settings -> Secrets and variables -> Actions`.
3. Add secret:
   - Name: `GH_STAR_PAT`
   - Value: your PAT token
4. Run workflow `Update Awesome List` (tab `Actions`) once manually.

After that, the workflow runs daily and updates:

- `README.md` (table with all starred repos)
- `data/starred-repos.json` (raw export)

## Required token access

- Fine-grained PAT: read access to profile metadata and repositories you want to include.
- Classic PAT: for public stars, basic token usually works; for private repos add `repo`.

The generator script uses GitHub GraphQL API with pagination and includes:

- project link and description
- language
- stars count
- last push date
- last commit date on default branch
- date when the repository was starred
