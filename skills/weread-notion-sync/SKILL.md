---
name: weread-notion-sync
description: Help a user install, configure, troubleshoot, or maintain the WeRead to Notion automatic sync project on GitHub Actions.
---

# WeRead to Notion Sync

Help the user set up the WeRead to Notion sync project in the current checkout or the project package they provided, so GitHub Actions copies their WeRead books, highlights, thoughts, and reading metadata into their own Notion database.

## Setup workflow

1. Read the project's `INSTALL.md` and inspect its current workflow and schema before giving version-specific steps.
2. Help the user create or fork a GitHub repository. Keep each user's integration private unless they explicitly choose otherwise.
3. In Notion, create or select a database and share it with a Notion integration. The database must have a title property named `title`, plus `WeRead ID`, `作者`, `封面`, `阅读进度`, `开始阅读时间`, `最后阅读时间`, `总共阅读时长`, and `最后同步时间` with the types documented in `INSTALL.md`.
4. Guide the user to save `WEREAD_API_KEY` and `NOTION_TOKEN` as GitHub Actions repository secrets, and `NOTION_DATABASE_ID` as a repository variable. Do not ask them to paste credentials into chat or commit them into files.
5. Start a manual workflow run and help inspect its result. Do not claim setup is complete until a successful run is observed or the user confirms it.

## Data behavior

- One Notion database row represents one WeRead book, keyed by `WeRead ID`.
- WeRead highlights and personal thoughts/reviews use separate endpoints and both belong in the page body.
- Progress, dates, duration, cover, and last sync time are database properties. Do not add a duplicate progress block to the page body.
- Removing a book from the WeRead shelf does not delete or archive its Notion page.
- WeRead does not expose the historical first-reading date. If no value exists, the app records when it first observed that the book had been started, and preserves that value on later runs. Describe it as an observed date, not the true start date.
- Each user's API key, Notion integration, database, GitHub secrets, and repository variable must belong to that user. Never reuse the project maintainer's credentials or database ID.

## Troubleshooting

Use the latest GitHub Actions run log and the current WeRead Skill documentation before suggesting API changes. Keep tokens out of logs and chat. If sync succeeds but thoughts are missing, verify that `/review/list/mine` is queried in addition to `/book/bookmarklist`. If records duplicate, check that the Notion `WeRead ID` property is populated and used as the idempotency key.
