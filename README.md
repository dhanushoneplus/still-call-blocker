# Get-On Labs apps website

Static GitHub Pages site for the Get-On Labs app portfolio. The repository name is historical; this site serves multiple apps.

## Public URLs

- `/` — Get-On Labs homepage and app directory
- `/still/` — Still Call Blocker landing page, guide and support
- `/still/privacy-policy.html` — Still privacy policy
- `/buzzpa/` — Buzzpa Alarms & Reminders landing page, guide and support
- `/buzzpa/privacy-policy.html` — Buzzpa privacy policy (existing URL preserved)
- `/privacy-policy.html` — legacy Still policy URL used by installed apps; full policy remains here with a canonical link to the dedicated page

Domain: https://folvi.dpdns.org/ (CNAME unchanged). Deploy from main through GitHub Pages. No build service, account, analytics or tracking scripts are needed. Ordinary hosting request data is handled by GitHub under its policies.

## Adding another app

1. Add an app folder containing index.html and privacy-policy.html, with a real description, support details and that app's own policy.
2. Add its local icon/screenshots in assets/ and use the shared portfolio.css and site.js.
3. Add a homepage card, navigation/footer links and a sitemap.xml entry.
4. Give each page a descriptive title, unique description, absolute canonical URL and accurate structured data. Never invent ratings, download counts or availability.
5. Check mobile layout, keyboard navigation, internal links and existing policy URLs before publishing.

Keep privacy policies separate. Never replace the legacy root policy with a company-wide policy or another app's policy: older Still versions open it directly.
Use local assets and system fonts. The email-copy button only copies the public support address; email links open the user's own email service and never send automatically.

Application/source changes to Still and Buzzpa are maintained separately; website-only updates do not require rebuilding Android app bundles.
