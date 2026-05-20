# GTM container — source of truth

This directory is the **canonical definition** of the elbruscloud.com Google Tag Manager container. The site loads GTM at runtime (`GTM_CONTAINER_ID` env var), but every tag/trigger/variable inside that container should originate from a file in this directory.

## File

- `elbruscloud-container-v1.json` — full GTM container export. Import this into a fresh or existing workspace.

What it ships:

| Kind | Name | Purpose |
| ---- | ---- | ------- |
| Variable | `GA4 Measurement ID` | Constant. **Edit after import.** Replace `G-XXXXXXXXXX` with your real GA4 stream ID. |
| Variable | `Event - form_id` | Data Layer Variable (`form_id`). |
| Variable | `Event - conversion_type` | Data Layer Variable (`conversion_type`). |
| Variable | `Event - appointment_type` | Data Layer Variable (`appointment_type`). |
| Variable | `Event - duration_minutes` | Data Layer Variable (`duration_minutes`). |
| Trigger | `Initialization - All Pages` | Fires the Google tag at the earliest possible moment. |
| Trigger | `CE — contact_form_submit` | Custom Event trigger, matches the dataLayer push from the contact "thanks" page. |
| Trigger | `CE — newsletter_subscribe_confirmed` | Custom Event trigger, fired from the newsletter confirm page. |
| Trigger | `CE — booking_created` | Custom Event trigger, fired from the React scheduling island on first-time booking. |
| Trigger | `CE — booking_rescheduled` | Custom Event trigger, fired from the React scheduling island on reschedule. |
| Tag | `GA4 Configuration` | Loads gtag and configures GA4 on every page. Inherits Consent Mode v2 state set by `_analytics_head.html`. |
| Tag | `GA4 — generate_lead — contact form` | GA4 Event `generate_lead`. Consent-gated on `analytics_storage`. |
| Tag | `GA4 — sign_up — newsletter` | GA4 Event `sign_up` (method=newsletter). Consent-gated on `analytics_storage`. |
| Tag | `GA4 — book_appointment — calendar` | GA4 Event `book_appointment`. Consent-gated on `analytics_storage`. |
| Tag | `GA4 — reschedule_appointment — calendar` | GA4 Event `reschedule_appointment`. Consent-gated on `analytics_storage`. |

All GA4 Event tags are gated by GTM's built-in consent feature on `analytics_storage`. They will not fire (and GA4 will not receive event hits) unless the visitor accepts cookies via our consent banner.

## How to import (first time)

1. In Google Tag Manager, open the elbruscloud.com container.
2. Go to **Admin → Import Container**.
3. Click **Choose container file** and upload `infra/gtm/elbruscloud-container-v1.json`.
4. Choose workspace: **Default Workspace** (or create one called `import-v1`).
5. Choose import option: **Merge**, and tick **Overwrite conflicting tags, triggers, and variables**.
6. Click **Confirm**.
7. Open the **GA4 Measurement ID** variable in the Variables list and replace `G-XXXXXXXXXX` with your real Measurement ID from GA4 (Admin → Data Streams → Web → copy `G-...`).
8. Click **Preview**, open elbruscloud.com in the connected Tag Assistant tab, and confirm:
   - `GA4 Configuration` fires on `Initialization`.
   - The four `GA4 — *` event tags appear under their custom events (you can fire them manually from the contact form, newsletter confirm, and booking flows).
9. **Submit** the workspace as a new container version. Name it `v1 — initial import (5 tags)`.
10. **Publish**.

## How to update

Whenever you change tags/triggers/variables in GTM, **export the container from GTM** (Admin → Export Container) and overwrite `elbruscloud-container-v1.json` (or bump to `v2.json`) so the repo stays in sync with what's live. Commit + push. This keeps the JSON file as a reviewable artifact in git.

For brand-new tags or paid-channel additions (LinkedIn Insight Tag, Meta Pixel, Microsoft UET, TikTok Pixel, Google Ads Conversion), prefer adding them in GTM first, testing in Preview, then exporting and committing the diff.

## Wiring to the site

The site loads this container automatically when `GTM_CONTAINER_ID=GTM-W78SVVN2` is set in `.env` (it already is on prod). Consent defaults to denied; the consent banner (`backend/templates/partials/_consent_banner.html` + `backend/static/src/consent.js`) calls `gtag('consent', 'update', ...)` when the visitor accepts, which lets the consent-gated GA4 Event tags fire.

The dataLayer events pushed from the Django backend / React island are in `backend/templates/partials/_analytics_head.html` and `frontend/scheduling-island/src/StepDone.tsx`. If you change an event name here, update the corresponding `CE — *` trigger in the JSON above.
