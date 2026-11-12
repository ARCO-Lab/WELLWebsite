# Terms of use and privacy

These cover the WELL Environmental Data Platform ([welldash.mcmaster.ca](https://welldash.mcmaster.ca)) and the
WordPress site ([well.mcmaster.ca](https://well.mcmaster.ca)). Questions about privacy, corrections to the data or the
service go to the WELL team, through well.mcmaster.ca.

## Terms of use

The platform and the WordPress site provide environmental monitoring information, research support and public-facing
project communication.

- **Informational use only:** Data, charts, summaries, and downloadable files are provided for informational,
  educational, and research-support purposes and should not be treated as legal, regulatory, engineering,
  safety-critical, or emergency-response advice.
- **No guarantee of uninterrupted service:** While the platform is designed for near real-time availability, uptime,
  data freshness, and feature availability are not guaranteed at all times because of scheduled maintenance, upstream
  API outages, network issues, or infrastructure failures.
- **Data accuracy and completeness:** Sensor readings, derived metrics, and exports may contain delays, gaps,
  approximations, processing errors, or third-party source inconsistencies. Users should independently validate
  important findings before relying on them.
- **Acceptable use:** Users must not misuse the dashboard, APIs, iframe integration, or WordPress site, including by
  attempting unauthorized access, bypassing rate limits, scraping protected content, interfering with service
  availability, or introducing malicious content.
- **Third-party services:** The platform depends on external providers including HoboLink, WQData Live, Borealis,
  SharePoint, WordPress, and hosting/network services. Their availability and terms may affect platform behavior.
- **Intellectual property:** Project branding, code, visual assets, and original content remain subject to the rights
  and licenses defined by the WELL project, McMaster University, and any third-party licensors.
- **Changes to the service:** Features, APIs, visualizations, exports, and access controls may be updated, restricted,
  or removed without notice as the platform evolves.

## Privacy

- **Operational data collected:** The system may log request metadata such as IP address, timestamp, requested path,
  response status, browser/user-agent details, and application errors for security, troubleshooting, and performance
  monitoring.
- **Analytics and observability:** Monitoring tools, logs, metrics, and alerts are used to understand uptime,
  failures, and performance across Flask, Next.js, WordPress, and PostgreSQL. Error reports sent to Sentry leave out
  request bodies, cookies, headers, query strings, IP addresses and user identity; the request counts the backend
  keeps record no IP addresses, query strings or browser details.
- **Sampling files:** Creek sampling files are uploaded by project members to a Borealis dataset, not through these
  sites; the dashboard imports the published files.
- **Third-party processing:** Data sent to third-party services, such as the external APIs used for ingestion and
  export workflows, is subject to those providers' terms and privacy practices.
- **Visitor counts:** Both sites count page views with GoatCounter, which sets no cookies, stores nothing in the
  browser and keeps only aggregated counts (pages, referrers, browsers, screen sizes, countries), not personal data or
  IP addresses. Query strings are left out of the counted page.
- **Cookies and WordPress behavior:** The WordPress site may set essential cookies related to login state, session
  handling, security, or embedded content; the visitor counts add none.
- **Retention:** Download files are deleted by an hourly cleanup once they are an hour old
  (`EXPORT_FILE_TTL_MINUTES`), the request
  counts and uptime checks are kept for 90 days, and database backups for up to 8 weeks.
