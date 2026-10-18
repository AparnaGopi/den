# Den test deployment

## Free Render setup

The included `render.yaml` declares a free Python web service and a free
PostgreSQL database. It generates a secret and connects the database automatically.
The assigned Render hostname is added to the allowed hosts and CSRF origins.
Automatic deployments are off, so later commits do not publish unexpectedly.

After pushing these files to your GitHub repository, sign in at
https://dashboard.render.com/ and choose New > Blueprint. Connect
`AparnaGopi/den`, select the branch containing this file, and review that both
resources use the Free plan before deploying. Do not deploy the Next.js scaffold
as a static site. Test the assigned provider URL before changing domain DNS.

Render's free web service sleeps after 15 minutes without inbound traffic. Local
uploads are lost on restart/redeploy/sleep; PostgreSQL records live separately.
The free database expires after 30 days. See https://render.com/docs/free for
current limits. Image uploads require separate object storage configured through
the environment settings below before they can be tested end to end.

The free service has no hosted shell. Create the first admin from a trusted local
terminal using the same deployment settings and the database's external connection
URL, then remove those credentials from the local shell environment. The hosted
service itself uses its internal database URL. SMTP ports are blocked on the free
service; outgoing email needs an HTTPS email provider integration or another host.
Authentication itself does not depend on SMTP in the current codebase.

## Application configuration

Deploy the Django application at the repository root. The root Next.js package
is a separate scaffold and is not the current Den web portal. The Expo mobile
client consumes the deployed Django API; it is not deployed by these scripts.

Use Python 3.12 or later supported by the pinned dependencies. Run
`sh deploy/build.sh` as the build command and `sh deploy/start.sh` as the start
command. Supply the variables in `deploy/environment.example` through the host.
Set the health-check path to `/health/` and ensure checks use HTTPS or the
proxy-provided `X-Forwarded-Proto: https` header.

The start command applies committed migrations before serving traffic, including
core migration 0012, which adds `vendor_type`. It never creates migration files
or administrator accounts. Use a dedicated staging database and a newly generated
secret. Existing local users, files and vendor records are not uploaded.

Configure an SMTP sender before relying on outgoing email. Login and registration
tests do not verify email delivery. HTTPS enforcement applies only to the staging
hostname; HSTS subdomain inclusion and browser preloading are intentionally off
because they could affect other services under your business domain. Django's
deployment check reports those two policy warnings; do not enable them blindly.

Use a managed PostgreSQL database. Serve uploaded images from S3-compatible
object storage using `DEN_STORAGE_BACKEND` and `DEN_STORAGE_OPTIONS`. The bucket
or CDN must permit delivery of the intended public vendor images; disabling signed
URLs does not make a private bucket public. WhiteNoise serves application static
files, not uploaded media. The repository's default local media directory is not
durable on hosts with ephemeral filesystems. Alternatively, configure a persistent
media volume and a web server that serves `/media/` from that volume.

The existing demo import deliberately accepts only the local development database.
Do not bypass its safeguards on a hosted database. Create a few fictional vendors
through the normal registration and admin approval flow to test staging, or add
a separately reviewed staging-only seed command later.

Create the first administrator through the hosting shell with
`python manage.py createsuperuser --settings=config.settings_deploy`. Do not
commit administrator passwords or supply passwords in public build logs.

First verify the provider URL: home page, customer registration/login, vendor
registration and submission, admin approval, vendor discovery, event matches,
filters, and image uploads. A pending vendor must stay out of discovery. Restart
the service and verify that accounts and uploaded images persist. Then add
`test.torontodecorden.com` in the hosting dashboard and copy its DNS instructions
to the actual DNS provider. Preserve the main domain and existing mail records.
Google Workspace domain verification is separate from website hosting and DNS
management. Confirm HTTPS and login again on the custom domain.
