# Admin login throttling

Staging serves three password login forms publicly:

- the Django admin login, `<ADMIN_URL>login/` (`/django-admin/login/` by
  default, `DJANGO_ADMIN_URL` in production settings);
- the Wagtail admin login, `<DJANGO_CHAT_WAGTAIL_ADMIN_PATH>login/`
  (`/cms/login/`);
- Wagtail's front-end login for login-restricted pages, `/_util/login/`
  (from `wagtail.urls`).

Until November 2026 all three were plain Django `LoginView`s with no rate
limit, so they accepted any number of password guesses. `config/urls.py` now
routes them through `django_chat.core.login_throttle.throttle_failed_logins`,
mounted before the admin and Wagtail includes, which limits **failed** login
attempts. The module mirrors python-podcast's reviewed
admin login throttle.

- `admin_login_client`: failed attempts per client address. The default is
  `20/hour`; override it with `DJANGO_ADMIN_LOGIN_CLIENT_RATE`. The client
  address is Django REST framework's `get_ident`, the same one the comment
  post rate limit uses. Gunicorn sees every request from Traefik on
  `127.0.0.1`. Traefik replaces any `X-Forwarded-For` the client sends with
  the real client address, so `REST_FRAMEWORK["NUM_PROXIES"]` stays unset
  (see [Post rate limit](local-development.md#post-rate-limit)).
- `admin_login_username`: failed attempts per submitted username, from any
  address. The default is `10/hour`; override it with
  `DJANGO_ADMIN_LOGIN_USERNAME_RATE`. Usernames are compared
  case-insensitively after the NFKC normalization the login form applies,
  with surrounding whitespace ignored. This limit holds even when a client
  rotates addresses.

All three logins share the same counters. A POST counts as failed unless it logs a
user in, so a wrong password and an invalid form both count. The Django admin
form refuses valid credentials of an account without staff status, so those
count as failed there. Successful logins do not count, and GET requests are
never throttled.

The client limit is checked first; a refused request is not counted against
anything. Once either limit is reached, every POST is refused with
`429 Too Many Requests` and a `Retry-After` header, even with the correct
password, until the oldest counted failure is older than the window.

## Storage and locking

The rates live in `REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]`. The counters use
the `admin_login_throttle` cache when it is configured and the `default` cache
otherwise. Production settings configure it as a file-based cache in
`<DJANGO_CACHE_LOCATION>/admin-login-throttle/`, a directory of its own: a view
restriction change clears the `default` cache (`django_chat/core/receivers.py`),
and that must not reset lockouts.

Every distinct username and client address with a failure leaves a counter
file for one hour; finished attempts leave no empty reservation entry. Django's
`FileBasedCache` deletes a random share of all files, live ones included, once
`MAX_ENTRIES` (`100000` here) is reached, and removes expired files only when
their key is read again. The counters therefore use
`django_chat.core.cache_backends.ExpiringFileBasedCache`, which first deletes
every expired file and culls at random only if the live entries alone still
reach the limit. The remaining limit: one client address leaves at most about
21 live files per hour (its own counter plus one per distinct username it
tried before reaching its `20/hour` budget), so roughly 4,800 addresses in one
hour could fill the cache with live counters, and the random cull could then
reset a real lockout. The client key is the full address, so a single IPv6
`/64` supplies that many addresses if the site is reachable over IPv6. While the cache is that full, every
counter write also lists the whole directory under the shared lock, so logins
slow down.

Failure history reads and updates hold one `filelock.FileLock` on
`ADMIN_LOGIN_THROTTLE_LOCK_PATH`, `<DJANGO_CACHE_LOCATION>/admin-login-throttle.lock`
in production. `FileBasedCache.clear()` deletes only `*.djcache` files, so
clearing a cache never replaces the lock. All Gunicorn workers must share the
same local filesystem, cache directory and lock path; independent hosts or
network filesystems are not supported. Admission checks both budgets and
reserves an in-flight slot in each under that lock, before the password is
verified, so failures plus running attempts cannot exceed either budget.
Successful logins and exceptions release their slots without adding failures;
a failed response turns the reservation into a counted failure. Reservations
expire after five minutes, so a killed worker cannot block capacity forever.
A pre-authentication lock wait longer than five seconds returns `503` with
`Retry-After: 5`; no login is admitted without a counter check. Local and test
settings use the `LocMemCache` with a process-local thread lock.

## API authentication

django-cast's API views (`/api/...`) inherit
`REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]`. Django Chat allows only
`SessionAuthentication`. Django REST framework's default also enabled HTTP
Basic authentication, which checked a username and password on every API
request: an unthrottled password check outside the login forms, without CSRF.
The Wagtail admin session still works for the editor API; no token
authentication is installed.

## Password rules

`AUTH_PASSWORD_VALIDATORS` applies Django's four standard validators: at least
12 characters, not too similar to the username or email, not a common password
and not entirely numeric. They apply when a password is set or changed
(`createsuperuser`, `changepassword`, the Wagtail account and user forms);
existing passwords are not checked.

## Locked out?

Anyone who knows a username can use up its `admin_login_username` budget and
lock all three logins for that user for up to an hour. To get in anyway, clear
the counters on the server:

```sh
cd /home/django-chat/site
DJANGO_SETTINGS_MODULE=config.settings.production .venv/bin/python manage.py shell \
  -c "from django.core.cache import caches; caches['admin_login_throttle'].clear()"
```

Run it as the `django-chat` user so the cache files keep their owner.
