# Inbox — the drop-box for screening reports

Drop a Capital IQ Transaction Screening Report (`.xls`, `.xlsx`, or `.csv`)
into this folder **using GitHub's web uploader** (Add file → Upload files)
and commit. A robot will immediately:

1. import every deal (new ones added, existing ones updated and enriched),
2. refresh the audit report and the public-safe data file,
3. **delete your uploaded file** — licensed exports must not live in the repo,
4. commit the updated data.

Watch it work under the **Actions** tab (workflow: "Import screening report").
Then check **audit.html** to see what came in.
