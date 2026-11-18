# How to Contribute

We're so thankful you're considering contributing to an [open source project of
the U.S. government](https://code.gov/)! If you're unsure about anything, just
ask -- or submit the issue or pull request anyway. The worst that can happen is
you'll be politely asked to change something. We appreciate all friendly
contributions.

We encourage you to read this project's CONTRIBUTING policy (you are here), its
[LICENSE](LICENSE), and its [README](README.md).

## Getting Started

Useful contributions include:

- Adding or correcting an agency source in
  [`sources/agency-index-sources.json`](sources/agency-index-sources.json).
- Fixing a bug in the downloader, normalization, or validation scripts.
- Adding a normalization rule for a messy value found in real agency data.
- Improving tests or documentation.

Look for open [issues](https://github.com/GSA-SHARE-IT/govcode-index/issues) or
open a new one to discuss a change before starting larger work.

### Team Specific Guidelines

Project roles and the people responsible for reviewing and merging changes are
listed in [COMMUNITY.md](COMMUNITY.md). How decisions are made is described in
[GOVERNANCE.md](GOVERNANCE.md).

### Building dependencies

The project is plain Python with one third-party dependency (`jsonschema`).

1. Install Python 3.12. The GitHub Actions workflows use 3.12, so keep code
   compatible with it even if you develop on a newer version.
2. Create a virtual environment and install the requirements:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

`jsonschema` is needed for the test suite as well as the consolidation script,
because the tests import `scripts.utils`, which imports the schema module.

### Building the Project

There is no build step. The scripts run directly from the repository root:

| Command | What it does | Network | Writes |
| :-- | :-- | :-- | :-- |
| `python3 -m unittest discover -s tests -v` | Runs the offline test suite | No | Temporary directories only |
| `python3 scripts/pull_index_assets.py` | Downloads every agency index and extracts project files | Yes | `agency-indexes/` |
| `python3 scripts/consolidate_to_gov_code.py` | Normalizes, validates, and combines project files | Yes (schema) | `gov-code.json` |

Paths are resolved relative to the repository, so the scripts can be run from
any working directory.

### Workflow and Branching

We follow the [GitHub Flow Workflow](https://guides.github.com/introduction/flow/):

1. Fork the project (external contributors) or create a branch (team members).
2. Check out the `main` branch.
3. Create a feature branch.
4. Write code and tests for your change.
5. From your branch, make a pull request against `GSA-SHARE-IT/govcode-index/main`.
6. Work with repo maintainers to get your change reviewed.
7. Wait for your change to be merged into `GSA-SHARE-IT/govcode-index/main`.
8. Delete your feature branch.

#### Code changes and data changes

The files under `agency-indexes/` are generated outputs. The weekly
[`pull-index-assets.yml`](.github/workflows/pull-index-assets.yml) workflow
refreshes and commits them.

- For code-only changes, **do not commit refreshed inventory files**. Test
  against temporary fixtures instead. This keeps code review separate from
  agency data churn.
- Run a live download only when the change calls for a data refresh, such as
  adding an agency. Mention in the pull request that it includes refreshed data.
- Do not hand-edit project files to fix agency data. They are overwritten on the
  next refresh. Fix the problem with a normalization rule, or report it to the
  agency.
- `gov-code.json` is generated locally and should not be committed.

### Testing Conventions

Tests live in [`tests/`](tests/) and use the standard library `unittest` module:

| File | Covers |
| :-- | :-- |
| `test_pull_index_assets.py` | Downloading, data preservation, encoding fallback, filename sanitization and collisions, warnings, failure handling |
| `test_normalization_values.py` | Value normalization rules (URLs, dates, licenses, enums) |
| `test_normalization_comprehensive.py` | End-to-end normalization of real-world records, idempotency |
| `test_validation.py` | Helpers, `validate_record`, `fill_record`, and standardization |

Run them from the repository root:

```bash
python3 -m unittest discover -s tests -v
```

Guidelines:

- Add or update tests for every behavior change, and run the full suite before
  opening a pull request.
- Tests must not use the network. Mock `urlopen` (see
  `test_pull_index_assets.py`) and use `tempfile.TemporaryDirectory()` for
  output.
- Tests must not read or modify the real files in `agency-indexes/`.
- When a change affects them, cover data preservation (unknown fields and
  original names survive), encoding, filename collisions and their warnings,
  and continuing after an agency failure.
- When you add a normalization or validation rule, also update
  [docs/NORMALIZATION_RULES.md](docs/NORMALIZATION_RULES.md) or
  [docs/VALIDATION_RULES.md](docs/VALIDATION_RULES.md).

The [`run-tests.yml`](.github/workflows/run-tests.yml) workflow runs the suite
on Python 3.12 for pull requests that change `scripts/`, `tests/`, or the
workflow itself.

### Coding Style and Linters

The project does not enforce a linter. Please:

1. Follow [PEP 8](https://peps.python.org/pep-0008/) and match the style of the
   surrounding code.
2. Prefer the Python standard library. Add a dependency to `requirements.txt`
   only when it is clearly worth it.
3. Resolve data paths relative to the repository (see `ROOT` in
   `pull_index_assets.py`), not the caller's working directory.
4. Keep agency URLs in `sources/agency-index-sources.json` rather than in code.
5. Preserve complete project objects in `agency-indexes/`. Filename cleanup must
   never change values inside the JSON.
6. Keep visible warnings for anything that changes how a project is saved
   (sanitized, truncated, suffixed, or unnamed), including the original name,
   final filename, and reason.
7. One agency's failure must not stop the others. Report the error and return a
   nonzero exit status.

### Writing Issues

Please file issues on
[GitHub](https://github.com/GSA-SHARE-IT/govcode-index/issues) using this
format:

    module-name: One line summary of the issue (less than 72 characters)

    ### Expected behavior

    As concisely as possible, describe the expected behavior.

    ### Actual behavior

    As concisely as possible, describe the observed behavior.

    ### Steps to reproduce the behavior

    List all relevant steps to reproduce the observed behavior.

For data problems, include the agency, the project name or filename, and the
relevant `WARNING` or `Failed` line from the workflow log if there is one.

### Writing Pull Requests

Open pull requests against `main` and fill out the
[pull request template](.github/PULL_REQUEST_TEMPLATE.md).

Comments should be formatted to a width no greater than 80 columns.

Files should be exempt of trailing spaces.

We adhere to a specific format for commit messages. Please write your commit
messages along these guidelines. Please keep the line width no greater than 80
columns (You can use `fmt -n -p -w 80` to accomplish this).

    module-name: One line description of your change (less than 72 characters)

    Problem

    Explain the context and why you're making that change.  What is the problem
    you're trying to solve? In some cases there is not a problem and this can be
    thought of being the motivation for your change.

    Solution

    Describe the modifications you've done.

    Result

    What will change as a result of your pull request? Note that sometimes this
    section is unnecessary because it is self-explanatory based on the solution.

Some important notes regarding the summary line:

* Describe what was done; not the result
* Use the active voice
* Use the present tense
* Capitalize properly
* Do not end in a period — this is a title/subject
* Prefix the subject with its scope

In the pull request, describe how you tested the change. Say which results came
from the offline test suite and which came from a live download or a GitHub
Actions run.

## Reviewing Pull Requests

Pull requests are reviewed by the maintainers and approvers listed in
[COMMUNITY.md](COMMUNITY.md). Each pull request should get at least one
approving review before it is merged. Reviewers check that:

- The tests pass and new behavior has tests.
- Generated data is not refreshed or rewritten by a code-only change.
- Project data is preserved and filename warnings are kept.
- Documentation is updated when commands, output layout, or processing behavior
  change.

External contributors cannot merge their own pull requests. A maintainer merges
them once they are approved.

## Shipping Releases

govcode-index does not publish versioned releases. Changes to the scripts take
effect when merged to `main`, and the data is refreshed every Monday by the
[`pull-index-assets.yml`](.github/workflows/pull-index-assets.yml) workflow.
Maintainers can start a refresh manually from the Actions tab with **Run
workflow**.

## Documentation

We welcome improvements to the project documentation. Please file an
[issue](https://github.com/GSA-SHARE-IT/govcode-index/issues) or open a pull
request.

When you change how the project behaves, update the matching documentation in
the same pull request:

| Change | Update |
| :-- | :-- |
| Commands, output layout, or downloader behavior | [README.md](README.md), [AGENTS.md](AGENTS.md) |
| Normalization rules | [docs/NORMALIZATION_RULES.md](docs/NORMALIZATION_RULES.md) |
| Validation or fill rules | [docs/VALIDATION_RULES.md](docs/VALIDATION_RULES.md) |
| Development process | This file |

## Policies

### Open Source Policy

We adhere to the [CMS Open Source
Policy](https://github.com/CMSGov/cms-open-source-policy). If you have any
questions, just [shoot us an email](mailto:opensource@cms.hhs.gov).

### Security and Responsible Disclosure Policy

_Submit a vulnerability:_ Vulnerability reports can be submitted through [Bugcrowd](https://bugcrowd.com/cms-vdp). Reports may be submitted anonymously. If you share contact information, we will acknowledge receipt of your report within 3 business days.

For more information about our Security, Vulnerability, and Responsible Disclosure Policies, see [SECURITY.md](SECURITY.md).

## Public domain

This project is in the public domain within the United States, and copyright and related rights in the work worldwide are waived through the [CC0 1.0 Universal public domain dedication](https://creativecommons.org/publicdomain/zero/1.0/).

All contributions to this project will be released under the CC0 dedication. By submitting a pull request or issue, you are agreeing to comply with this waiver of copyright interest.
