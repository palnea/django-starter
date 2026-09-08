# authy

[Back to docs index](../README.md)

Authentication: registration, login, token refresh, password flows, and the three
social providers. The `User` model itself lives in [user.md](user.md).

---

## Endpoints

All under `/auth/`, namespaced `authy:` for `reverse()`.

| Method | Path | URL name | Permission | Throttle |
|---|---|---|---|---|
| `POST` | `/auth/login` | `authy:login` | `AllowAny` | `AuthRateThrottle` |
| `POST` | `/auth/register` | `authy:register` | `AllowAny` | `AuthRateThrottle` |
| `POST` | `/auth/token/refresh/` | `authy:token_refresh` | default | none |
| `POST` | `/auth/reset_password` | `authy:reset_password` | `AllowAny` | `AuthRateThrottle` |
| `POST` | `/auth/update_password/` | `authy:update_password` | `IsAuthenticated` | none |
| `POST` | `/auth/google/` | `authy:google_social_auth` | `AllowAny` | `AuthRateThrottle` |
| `POST` | `/auth/facebook/` | `authy:facebook_social_auth` | `AllowAny` | `AuthRateThrottle` |
| `POST` | `/auth/apple/` | `authy:apple_social_auth` | `AllowAny` | `AuthRateThrottle` |

`AuthRateThrottle` is keyed by IP through `AnonRateThrottle`, at the `auth` rate
of **5 per minute**, so brute force is limited regardless of whether credentials
are valid. Note `token/refresh/` and `update_password/` are **not** throttled.

Tests disable throttling entirely through `settings/local_test.py`.

---

## Tokens

`djangorestframework-simplejwt`, configured in `settings/base.py`:

| Setting | Value |
|---|---|
| `ACCESS_TOKEN_LIFETIME` | 15 minutes |
| `REFRESH_TOKEN_LIFETIME` | 30 days |
| `ROTATE_REFRESH_TOKENS` | `True` |
| `BLACKLIST_AFTER_ROTATION` | `True` |
| `ALGORITHM` | HS256, signed with `SECRET_KEY` |
| `USER_ID_CLAIM` | `account_id` |
| `AUTH_HEADER_TYPES` | `Bearer` |

Refreshing rotates the refresh token and blacklists the old one, through
`rest_framework_simplejwt.token_blacklist`. A stolen refresh token is therefore
usable once, and reuse of a rotated token fails.

### What is in a token

`CustomTokenObtainPairSerializer.get_token()` adds to both tokens:

| Claim | Value |
|---|---|
| `email` | The user's email |
| `phone` | International format, spaces stripped |
| `user_id` | The user's UUID as a string |
| `groups` | Group names |
| `permissions` | Permission codenames |

`authenticate_response()` then adds two more to the **access token only**:

| Claim | Value |
|---|---|
| `subscription` | `UserSubscription.safe_json()`, or `null` |
| `locale_code` | The user's locale code |

Two consequences:

- **The client learns its subscription state from the token.** No extra call. It
  also means subscription changes are not visible until the access token is
  refreshed, at most 15 minutes.
- **`user_id` and `account_id` are different claims.** simplejwt uses
  `account_id` for its own user lookup, and `GlobalContext.user_id` reads
  `user_id`. Both are the same UUID. Do not remove either.

`GlobalContext` reads `user_id`, `groups`, `permissions`, and `locale_code`
straight off the token payload. See
[../conventions/logging-and-context.md](../conventions/logging-and-context.md).

### `CustomJWTAuthentication`

Registered as the first `DEFAULT_AUTHENTICATION_CLASSES` entry. It subclasses
`JWTAuthentication` and adds exactly one thing: on success it calls
`newrelic.agent.set_user_id()`, so New Relic traces are attributable. Failure to
tag is swallowed and logged, never blocking authentication.

Session and Basic authentication are also enabled, which is what makes the Django
admin work.

---

## Registration

```
POST /auth/register
  |
UserRegisterView (AllowAny, throttled)
  |  UserRegisterSerializer.validate()
  |     requires email XOR phone, and password == verify_password
  v
RegistrationService.register(data, language_code)      @transaction.atomic
  |
  |  User.create_with_password(...)
  |
  |  email given -> ContactVerificationService.create_contact_verification(
  |                     medium="email", send_code=False)
  |  phone given -> same with medium="phone"
  |
  |  contact_verification.send_code(language_code=..., user=user)
  |     any failure -> CustomException 500 "Could not send the verification code"
  v
{ "phone": ..., "email": ..., "code_id": ... }
```

Registration does **not** return tokens. It returns a `code_id`, and the client
is expected to verify the contact before logging in. See
[contact-verification.md](contact-verification.md).

The whole thing is one transaction, so a verification-send failure rolls back the
user creation.

The language for the verification message comes from
`GlobalContext.language_code`, so the code arrives in the caller's language.

---

## Login

```
POST /auth/login   { email | phone, password }
  |
UserLoginView (AllowAny, throttled)
  |  UserLoginSerializer.validate()
  |     normalises email to lowercase and trims
  |     requires email XOR phone, rejecting both or neither
  |     authenticate_user(user, password)
  |        wrong password -> CustomException.authentication_error
  |     authenticate_response(user)
  v
response_body = { "access": ..., "refresh": ..., "user": {...} }
```

`user` is `user.to_dict(exclude=["phone", "products", "password"])`.

Both email and phone login are supported, and exactly one must be supplied.

---

## Password flows

Two different things, easily confused.

### Reset, for a user who is locked out

`POST /auth/reset_password`, `AllowAny`. Supply email or phone, not both.

`PasswordService.reset_password` generates a **six digit numeric password**, sets
it on the user, and sends it by email or SMS. Email goes through
`EmailService().send_async()`, SMS through `SMSService(get_sms_client()).send()`,
synchronously.

Worth knowing before you ship this:

- The new password is six numeric digits, which is weak. It is delivered in
  plain text over email or SMS.
- The endpoint reveals whether an account exists, by returning
  `ERR_NOT_FOUND_ERROR` for an unknown address.
- There is no reset token and no expiry. The password is changed immediately, so
  anyone who can trigger the endpoint can lock the real user out of their current
  password.

For a production product, replace this with a tokenised, expiring reset link.
The throttle at 5 per minute per IP is the only thing limiting abuse today.

### Update, for a user who is signed in

`POST /auth/update_password/`, `IsAuthenticated`. `UpdatePasswordSerializer`
validates and performs the change. All the work happens in the serializer, and
the view returns a bare `ViewSuccessResponse()`.

---

## Social authentication

Three endpoints, one shape. The client obtains a token from the provider and
posts it. All validation happens inside the serializer's
`validate_auth_token`.

```
POST /auth/{google,facebook,apple}/   { auth_token }
  |
{Google,Facebook,Apple}SocialAuthSerializer.validate_auth_token()
  |  Google   -> authy/social_auth/google.py    verifies the Google ID token
  |  Facebook -> authy/social_auth/facebook.py  verifies the access token
  |  Apple    -> authy/social_auth/apple.py     verifies the identity token
  v
login_social_user(provider, user_id, email, name)     authy/helpers/social_auth.py
  |  user with this email exists -> use it
  |  otherwise User.create_with_password({email, password: SOCIAL_SECRET, fullname})
  |     email_verified = True
  |     creation_type = UserCreationType.PERSONAL
  v
social_auth_authenticate_user(user)  ->  access and refresh tokens
```

Note the Apple view reads `validated_data["code"]` while Google and Facebook read
`validated_data["auth_token"]`.

### `SOCIAL_SECRET` matters

Every socially-created user gets `settings.SOCIAL_SECRET` as their password. So
that value is effectively a **master password for every social account**. If it
leaks, anyone can log in as any social user through the ordinary email and
password endpoint.

`settings/base.py` defaults it to `"default-social-secret-key"` and
`settings/development.py` to `"dev-social-secret-123"`. Set a real, secret value
in every deployed environment.

### Accounts are matched by email

`login_social_user` finds an existing user by email address and reuses it. So
signing in with Google using the same address as an existing password account
takes over that account. That is usually what you want, and it is worth knowing
that it is what happens.

### Known gap: `GOOGLE_CLIENT_ID` is not defined

`authy/serializers.py` checks the Google token audience:

```python
if user_data["aud"] != settings.GOOGLE_CLIENT_ID:
```

`GOOGLE_CLIENT_ID` is **not defined anywhere in `settings/`**. The tests pass
only because they wrap the call in `@override_settings(GOOGLE_CLIENT_ID="google")`.
At runtime this raises `AttributeError`, which the exception handler renders as a
500, so **Google sign-in cannot currently succeed in a deployed environment**.

Fix it by adding the setting before relying on that endpoint:

```python
# settings/base.py
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
```

and setting `GOOGLE_CLIENT_ID` in the environment. The audience check is a real
security control, so do not remove the comparison instead.

---

## Files

| Path | Contains |
|---|---|
| `authy/views.py` | The eight views, all using `LoggingMixin` |
| `authy/serializers.py` | Login, register, refresh, password, and the three social serializers |
| `authy/services.py` | `RegistrationService`, `PasswordService` |
| `authy/custom/token_serializer.py` | `CustomTokenObtainPairSerializer`, which adds the claims |
| `authy/helpers/token_helper.py` | `authenticate_user`, `authenticate_response`, `set_token_parameters` |
| `authy/helpers/social_auth.py` | `login_social_user` |
| `authy/social_auth/` | `google.py`, `facebook.py`, `apple.py`, the provider verifiers |
| `authy/utils/custom_jwt_authentication.py` | `CustomJWTAuthentication` |
| `authy/test/` | Integration tests |

---

## Configuration

| Variable | Needed for |
|---|---|
| `SECRET_KEY` | JWT signing. Required in test and production |
| `SOCIAL_SECRET` | All social login. Treat as a credential |
| `SOCIAL_AUTH_APPLE_KEY_ID`, `SOCIAL_AUTH_APPLE_TEAM_ID`, `SOCIAL_AUTH_APPLE_PRIVATE_KEY` | Sign in with Apple |
| `GOOGLE_CLIENT_ID` | Google sign-in. **Not currently wired into settings**, see above |
| `EMAIL_*`, `NETGSM_*`, `SMS_HEADER` | Delivering reset passwords and verification codes |

---

## Related

- [user.md](user.md) for the `User` model and `create_with_password`.
- [contact-verification.md](contact-verification.md) for what happens after registration.
- [../conventions/logging-and-context.md](../conventions/logging-and-context.md) for the claims the global context reads.
- [../conventions/permissions.md](../conventions/permissions.md) for how the token's permissions are used.
