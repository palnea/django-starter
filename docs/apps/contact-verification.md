# contact_verification

[Back to docs index](../README.md)

Issues and checks six digit codes to prove a user controls an email address or a
phone number. Registration depends on it. See [authy.md](authy.md).

---

## Endpoints

| Method | Path | URL name | Purpose |
|---|---|---|---|
| `POST` | `/contact-verification/send-the-code/` | `contact_verification:contact-verification` | Issue and send a code |
| `POST` | `/contact-verification/verify-the-code/` | `contact_verification:verify-contact` | Check a code, then mark the contact verified |
| `POST` | `/contact-verification/verify-email/` | `contact_verification:email-verification` | Mark an email verified from a code |
| `POST` | `/contact-verification/verify-phone/` | `contact_verification:phone-verification` | Mark a phone verified from a code |

---

## The model

`ContactVerification`, table `contact_verification`. Not soft-deleted.

| Field | Notes |
|---|---|
| `id` | UUID primary key. This is the `code_id` returned to the client |
| `medium` | `email` or `phone`, a `CommunicationMedium` |
| `receiver_address` | The address or number the code went to |
| `code` | Six digits, generated on save if not set |
| `valid_interval_in_seconds` | 1500 for email, 300 for phone |
| `attempts` | Wrong guesses so far |
| `status` | `initial`, `sent`, `failed`, `verified` |

```python
UniqueConstraint(
    fields=["code", "status"],
    condition=Q(status="initial") | Q(status="sent"),
    name="unique_code_status_when_not_finished",
)
```

So two codes in flight can never collide, while a finished code frees its value
for reuse.

### Code generation

`generate_code()` picks six random digits and retries up to ten times until it
finds one not used by any row created inside the current validity window. After
ten failures it raises `RuntimeError`. Codes are generated in `save()` when the
field is empty, so you never set `code` yourself.

The codes are numeric and six digits, which is a keyspace of one million. The
attempt limit below is what makes that safe.

### Expiry

Two different intervals, from `settings/base.py`:

```python
EMAIL_VERIFICATION_ACTIVE_INTERVAL = 1500   # 25 minutes, the comment saying "a day" is wrong
PHONE_VERIFICATION_ACTIVE_INTERVAL = 300    # 5 minutes
MAX_VERIFICATION_ATTEMPTS = 3
```

`settings/local_test.py` sets `VERIFICATION_ACTIVE_INTERVAL = 300`, a separate
name that nothing reads. The two above are what actually apply.

`is_valid` is false once the code is `verified`, or once the window has passed.

---

## Sending a code

```
POST /contact-verification/send-the-code/   { receiver_address, medium }
  |
ContactVerificationViewSet.create
  v
ContactVerificationService.create_contact_verification(data, send_code=True)
  |  @transaction.atomic
  |  picks the validity window from the medium
  |  ContactVerification.objects.create(...)   -> save() generates the code
  |
  |  contact_verification.send_code(language_code, user)
  |     email -> renders emails/verification_email.html, EmailService.send_async
  |     phone -> SMSService.send_async, which is actually synchronous
  |     sets status = SENT
  |
  |  status == FAILED -> CustomException 500
  v
{ "id": <uuid> }  plus a localised message
```

The email path renders a template with the code, the user's name, the expiry, and
`settings.LOGO_URL`. It calls `django.utils.translation.activate(language_code)`
first, so the message arrives in the caller's language.

Registration calls this with `send_code=False` and then calls `send_code()`
itself, so it can pass the newly created user in for the greeting. See
[authy.md](authy.md).

---

## Verifying a code

```
POST /contact-verification/verify-the-code/   { uuid, code }
  |
ContactVerificationViewSet.verify
  v
ContactVerificationService.verify_contact(validated_data)
  |
  |  no row for uuid            -> 400, field error on "uuid"
  |  not is_valid               -> 400, field error on "code", expired
  |  attempts >= MAX (3)        -> status = FAILED, 400 on "attempts"
  |  code mismatch              -> attempts += 1, status = FAILED, 400 on "code"
  |
  |  match:
  |     @transaction.atomic
  |     status = VERIFIED
  |     CodeVerificationService.verify_user_contact(email=... | phone=...)
  |         sets User.email_verified or User.phone_verified
  v
success
```

Every failure is a `CustomException.validation_error` with a field error, so
clients can attach the message to the right input. See
[../conventions/errors.md](../conventions/errors.md).

### Attempts and status

A wrong code sets `status = FAILED` **and** increments `attempts`. Because
`is_valid` only excludes `VERIFIED`, a `FAILED` row can still be attempted again
until `attempts` reaches `MAX_VERIFICATION_ATTEMPTS`, which is 3. So a user gets
three guesses in total.

`CodeVerificationService` also exposes `verify_code(code, email=None, phone=None)`
for the `verify-email/` and `verify-phone/` endpoints, which look the code up by
value plus address rather than by id.

---

## Delivery

Both media go through `communications`. See [communications.md](communications.md).

- **Email** is genuinely asynchronous, dispatched to Celery via
  `send_email_task.delay()`.
- **SMS** is not. `SMSService.send_async` calls `_send` directly, so a slow
  NetGSM response blocks the request.

---

## Configuration

| Setting | Purpose |
|---|---|
| `EMAIL_VERIFICATION_ACTIVE_INTERVAL` | Email code lifetime, seconds |
| `PHONE_VERIFICATION_ACTIVE_INTERVAL` | Phone code lifetime, seconds |
| `MAX_VERIFICATION_ATTEMPTS` | Guesses allowed |
| `LOGO_URL` | Image in the verification email. Currently points at a third-party CDN. Replace it |
| `EMAIL_*` | SMTP delivery |
| `NETGSM_*`, `SMS_HEADER` | SMS delivery |

---

## Files

| Path | Contains |
|---|---|
| `contact_verification/models.py` | `ContactVerification`, code generation, `send_code` |
| `contact_verification/services.py` | `ContactVerificationService`, `CodeVerificationService` |
| `contact_verification/views.py` | The two viewsets |
| `contact_verification/templates/emails/verification_email.html` | Email template |
| `contact_verification/test/` | Integration tests |

---

## Testing

Celery runs eagerly under `settings/local_test.py`, so `send_async` completes
inline. Read the code straight off the model rather than trying to intercept the
message:

```python
content, message, verification = ContactVerificationService.create_contact_verification(
    {"receiver_address": "a@example.com", "medium": "email"}, send_code=False
)
verification.refresh_from_db()
code = verification.code
```

---

## Related

- [authy.md](authy.md) for registration, which drives this.
- [user.md](user.md) for `email_verified` and `phone_verified`.
- [communications.md](communications.md) for delivery.
