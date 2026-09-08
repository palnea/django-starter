# Payments and subscriptions

[Back to docs index](../README.md)

Three Django apps that only make sense together:

| App | Owns |
|---|---|
| `payment` | What can be bought, what was bought, and receipt verification |
| `vendor` | The store side: clients, webhook parsing, notification handling |
| `subscription` | The resulting subscription state and its history |

If your product does not sell in-app purchases, delete all three. See
[../starting-a-new-project.md](../starting-a-new-project.md).

---

## The two ways state changes

Everything here is one of two flows.

1. **The client tells us about a purchase.** The app sends a store receipt to
   `POST /payment/verify_receipt/`. We verify it with Apple or Google, record it,
   and create or renew a subscription.
2. **The store tells us about a change.** Apple or Google posts a server
   notification to a webhook. We verify it, work out what changed, and update the
   subscription.

The first is how a subscription starts. The second is how it renews, lapses,
upgrades, gets refunded, or expires. Renewals do **not** come through the client.

---

## Models

```
Buyable  (what is for sale)
   |  title/description -> common.Translation
   |  special_offer_root -> Buyable (self)
   |
   +--< PurchasedBuyable >--+
                            |
User ---< Purchase ---------+
            |  original_transaction_id
            |
            +---< PaymentTransaction   (one per charge)
            |
            +---< UserSubscription     (current state)
                        |
                        +---< UserSubscriptionChangeRecord   (audit trail)
```

| Model | App | Notes |
|---|---|---|
| `Buyable` | `payment` | A product. Type is `personal_subscription`, `corporate_subscription`, or `one_time_purchase`. Period is `monthly`, `semi_annual`, or `annual`. Carries `trial_days` and an optional `special_offer_root` pointing at another `Buyable`. Name is unique among non-deleted rows. |
| `Purchase` | `payment` | One user's purchase of one or more buyables, through `PurchasedBuyable`. Holds `vendor` and `original_transaction_id`. |
| `PurchasedBuyable` | `payment` | The join, with a quantity. |
| `PaymentTransaction` | `payment` | One charge. Unique on `(payment_vendor, transaction_id)` among non-deleted rows, which is the idempotency guard against duplicate webhooks and repeated client calls. |
| `UserSubscription` | `subscription` | Current state: `buyable`, `purchase`, `start_date`, `expiration_date`, `status`, `used_trial_days`. |
| `UserSubscriptionChangeRecord` | `subscription` | Append-only history, written automatically. |

All of these are soft-deleted except `UserSubscriptionChangeRecord`.

### Two constraints worth knowing

**One active subscription per user.** A partial unique constraint on
`UserSubscription`:

```python
UniqueConstraint(
    fields=["user"],
    condition=Q(status=SubscriptionStatus.ACTIVE) | Q(status=SubscriptionStatus.TRIAL),
    name="unique_user_active_subscription",
)
```

A second active or trial subscription for the same user raises `IntegrityError`
at the database level, whatever the application logic does.

**A subscription cannot be bought alongside anything else.**
`PurchaseManager.create` rejects a basket that mixes a subscription with other
items.

### Subscription status

`SubscriptionStatus`: `initial`, `trial`, `active`, `suspended`, `canceled`,
`expired`.

Counterintuitively, **`canceled` still counts as active**:

```python
ACTIVE_STATUSES = [SubscriptionStatus.TRIAL, SubscriptionStatus.ACTIVE, SubscriptionStatus.CANCELED]
```

That is correct for store subscriptions. Cancelling turns off auto-renewal but
the user keeps access until the period they paid for runs out. Do not "fix" this.

`UserSubscription.current_status` is a `cached_property` that lazily reconciles
status against the clock and **saves as a side effect**. Reading it can write to
the database.

### The history is automatic

`UserSubscription.save()` is overridden. Before saving, it compares the incoming
instance against the stored row and writes a `UserSubscriptionChangeRecord` when
anything differs, other than an `expiration_date` change that exactly matches a
normal period extension. You never create change records by hand.

---

## Flow 1: the client verifies a receipt

```
Client
  |  POST /payment/verify_receipt/   { store, receipt }
  v
PaymentViewSet.make_purchase                       payment/views.py
  |  ReceiptVerificationSerializer validates
  v
PaymentService.make_purchase                       payment/services.py
  |  @transaction.atomic
  |  SUBSCRIPTION_STRATEGY_MAPPER[store]           payment/constants.py
  v
GooglePurchaseStrategy | ApplePurchaseStrategy     payment/subscription/strategies.py
  |
  |  1. verify()                                   calls the store
  |       Apple  -> payment/verifiers/appstore.py    (AppStoreValidator)
  |       Google -> payment/verifiers/googleplay.py
  |     invalid -> CustomException.business_logic_error(ERR_INVALID_RECEIPT)
  |
  |  2. prepare_transaction_creation_for_receipt()
  |       builds unsaved Purchase and PaymentTransaction
  |
  |  3. create_transaction()                       @transaction.atomic
  |       Purchase.objects.create(...)
  |       PaymentTransaction.objects.create(...)
  |         IntegrityError on the unique constraint -> return quietly
  |       if buyable is not one_time_purchase:
  |           purchase_for_subscription_created.send_robust(...)
  v
handle_user_subscription_create                    subscription/handlers.py
  |  @receiver(purchase_for_subscription_created)
  |
  |  already has an active subscription?
  |     same purchase -> renew(from_now=False)
  |     different     -> return, do nothing
  |  otherwise create UserSubscription:
  |     trial_days == 0 -> status=ACTIVE, expires now + period
  |     trial_days > 0  -> status=TRIAL,  expires now + trial_days
  v
UserSubscription  (+ UserSubscriptionChangeRecord written by save())
```

Points worth internalising:

- **The strategy is a stateful object, not a service.** It holds the receipt
  across `verify` then `prepare` then `create`. Calling `create_transaction()`
  before `prepare` raises a 500 deliberately, guarded by
  `prepared_for_transaction`.
- **The unique constraint is the retry guard.** A repeated client call hits
  `IntegrityError` on `(payment_vendor, transaction_id)` and returns quietly
  rather than double-charging state.
- **The subscription is created through a Django signal**, not a direct call.
  `payment` does not import `subscription`. `subscription/handlers.py` listens.
  `send_robust` means a failure there does not blow up the purchase, so a
  purchase can succeed while subscription creation silently fails. Check the logs
  when a payment exists with no subscription.
- **`PaymentService.check_active_subscription`** raises 409
  `ERR_ACTIVE_SUBSCRIPTION_EXISTS` when the user already has a non-one-time
  subscription.

---

## Flow 2: the store sends a notification

```
Apple / Google
  |  POST /payment/appstore/webhook/
  |  POST /payment/googleplay/webhook/
  v
AppStoreWebhookViewSet | GooglePlayWebhookViewSet   payment/views.py
  |  permission_classes = [AllowAny]
  |  @extend_schema(exclude=True)
  |  log.info("... webhook is received")
  |  try:
  v
AppleNotificationHandler | GoogleNotificationHandler
        vendor/notification_handlers/subscription_notification_handlers.py
  |
  |  __init__ parses and verifies
  |     Apple  -> AppStoreNotificationVerifier.parse()
  |                 decodes the JWS, checks the certificate chain to AppleRootCA-G3
  |     Google -> GooglePlayNotificationVerifier.parse()
  |                 base64-decodes the Pub/Sub message envelope
  |
  |  handle()
  |     looks up METHOD_MAPPER[notification_type][subtype]
  |     unknown combination -> self.none(), a no-op
  v
one handler method
  |  renew_subscription / renew_subscription_from_now
  |  update_expiration_time / extend_expiration
  |  ensure_active / ensure_active_if_not_expired / ensure_expiration
  |  cancel_subscription / suspend_subscription
  |  upgrade / downgrade / refund / revoke ...
  v
UserSubscription updated (+ change record)
  |
  |  except Exception:
  |      log.error("Unhandled ... notification")
  v
always returns 200 success
```

### The webhook viewsets always return success

That is deliberate. If we returned an error, the store would retry the same
notification on a schedule, indefinitely. Returning 200 and logging the failure
keeps the retry queue clean and puts the problem where an operator can see it.

**So a failing webhook is invisible from the outside.** When subscription state
looks wrong, search the logs for `Unhandled Google notification` or
`Unhandled App Store notification` before anything else.

### Notification mapping

Google notifications arrive as one type with many subtypes:

| Subtype | Action |
|---|---|
| `SUBSCRIPTION_PURCHASED` | `ensure_subscription` |
| `SUBSCRIPTION_RENEWED` | `create_transaction_and_extend_subscription` |
| `SUBSCRIPTION_RECOVERED` | `create_transaction_and_extend_subscription_from_now` |
| `SUBSCRIPTION_IN_GRACE_PERIOD` | `ensure_active` |
| `SUBSCRIPTION_ON_HOLD`, `SUBSCRIPTION_PAUSED` | `suspend_subscription` |
| `SUBSCRIPTION_CANCELED` | `cancel_subscription` |
| `SUBSCRIPTION_RESTARTED`, `SUBSCRIPTION_PAUSE_SCHEDULE_CHANGED` | `renew_subscription` |
| `SUBSCRIPTION_DEFERRED` | `extend_expiration` |
| `SUBSCRIPTION_PRICE_CHANGE_CONFIRMED` | `change_purchase_amount` |
| `SUBSCRIPTION_EXPIRED`, `SUBSCRIPTION_REVOKED` | `ensure_expiration` |

Apple uses types, sometimes with subtypes:

| Type | Action |
|---|---|
| `SUBSCRIBED` + `INITIAL_BUY` / `RESUBSCRIBE` | `just_subscribed` / `resubscribe` |
| `DID_RENEW` | `did_renew` |
| `DID_FAIL_TO_RENEW` | `did_fail_to_renew` |
| `EXPIRED`, `GRACE_PERIOD_EXPIRED` | `expired`, `grace_period_expired` |
| `DID_CHANGE_RENEWAL_PREF` + `UPGRADE` / `DOWNGRADE` / none | `upgrade` / `downgrade` / `cancel_downgrade` |
| `OFFER_REDEEMED` + subtype | `offer_*` |
| `PRICE_INCREASE` + `ACCEPTED` | `price_increase_accepted` |
| `REFUND`, `REFUND_DECLINED`, `REFUND_REVERSED`, `REVOKE` | `refund`, `refund_declined`, `reversed`, `revoke` |
| `RENEWAL_EXTENDED`, `RENEWAL_EXTENSION` + subtype | `renewal_extended`, `renewal_summary` / `renewal_failure` |
| `TEST` | `test` |

Anything not in the mapper resolves to `none()` and is ignored. Adding support
for a new notification means adding an entry, not adding a branch.

### Google renewals create a synthetic transaction id

Google reuses the original purchase token rather than issuing a new transaction
id per renewal, so `GoogleNotificationHandler.get_payment_transaction()` returns
`None` and `create_new_payment_transaction(..., from_original=True)` prefixes a
Unix timestamp: `f"{int(time.time())}-{purchase_token}"`. Without that, the
unique constraint would reject every renewal as a duplicate.

---

## Endpoints

| Method | Path | Permission | Purpose |
|---|---|---|---|
| `POST` | `/payment/verify_receipt/` | `IsAuthenticated` | Verify a store receipt and record the purchase |
| `GET` | `/payment/buyable/` | `IsReadonly \| ActionAwareModelPermissions` | List products |
| `POST` | `/payment/buyable/` | `ActionAwareModelPermissions` | Create a product |
| `GET`, `PUT`, `PATCH`, `DELETE` | `/payment/buyable/<id>/` | as above | Manage a product |
| `POST` | `/payment/appstore/webhook/` | `AllowAny` | Apple server notifications |
| `POST` | `/payment/googleplay/webhook/` | `AllowAny` | Google Pub/Sub notifications |

`BuyableViewSet.retrieve` resolves `title_id` and `description_id` through
`Translation` for the request's language, including for `special_offer_root`. See
[common.md](common.md).

---

## Directory guide

Two directories are both called "verifiers" and do different jobs.

| Path | Job |
|---|---|
| `payment/verifiers/appstore.py`, `googleplay.py` | Validate a **receipt** the client sent us |
| `payment/verifiers/errors.py` | `InAppPyValidationError` |
| `payment/subscription/strategies.py` | Per-store purchase flow, stateful |
| `payment/constants.py` | `SUBSCRIPTION_STRATEGY_MAPPER` |
| `payment/signals.py` | `purchase_for_subscription_created` |
| `vendor/verifiers/*` | Parse and authenticate a **webhook** the store sent us |
| `vendor/clients/appstore.py`, `googleplay.py` | Outbound calls to store APIs |
| `vendor/notification_handlers/*` | React to a parsed notification |
| `vendor/strategies/*` | **Empty placeholder classes.** Not implemented. The mapping lives in the handlers instead. |
| `subscription/handlers.py` | The signal receiver that creates subscriptions |

---

## Configuration

All optional unless you keep these apps. See
[../operations/settings-and-env.md](../operations/settings-and-env.md).

**Apple**: `APPLE_BUNDLE_ID`, `APPLE_APP_ID`, `APPLE_IN_APP_SIGNING_KEY`,
`APPLE_DEVELOPER_KEY_ID`, `APPLE_DEVELOPER_ISSUER_ID`,
`APPLE_CONNECT_API_KEY_ID`, `APPLE_CONNECT_API_SIGNING_KEY`. The verifier also
reads `APPLE_ROOT_CA` from the environment, falling back to a local
`AppleRootCA-G3.cer`.

**Google**: the `GOOGLE_PLAY_*` block, which is a service-account JSON split
across variables, plus `GOOGLE_PLAY_PACKAGE_NAME` and `GOOGLE_PLAY_RSA_KEY`.

`settings/development.py` provides non-working placeholder defaults for the
Google values, so the app boots locally without credentials. It will not
successfully verify anything.

---

## Failure modes

| Symptom | Look at |
|---|---|
| Purchase succeeds, no subscription appears | The signal receiver failed. `send_robust` swallows it. Search logs for `handle_user_subscription_create`. |
| Renewals never arrive | Webhook not configured at the store, or failing. Search for `webhook is received`. |
| Subscription state is stale | A notification hit `none()` because its type or subtype is not in `METHOD_MAPPER`. |
| `IntegrityError` on `unique_user_active_subscription` | Something tried to create a second active subscription. Usually a webhook racing the client flow. |
| Repeated client calls do nothing | Working as intended. The unique constraint on `(payment_vendor, transaction_id)` absorbs them. |
| Receipt rejected | `ERR_INVALID_RECEIPT`. Check the sandbox versus production environment. `AUTO_RETRY_WRONG_ENVIRONMENT_REQUEST` is on, so Apple receipts retry against the other environment automatically. |
| A user has access after cancelling | Correct. `canceled` is an active status until expiry. |

---

## Testing locally

You cannot get a real receipt without a store build. What you can do:

- Use the recipes in `custom_test/baker_recipes.py`:
  `google_payment_transaction`, `apple_payment_transaction`, `monthly_buyable`.
- Send a captured notification body straight to the webhook endpoint. It is
  `AllowAny`, so no authentication is needed. Apple bodies must carry a valid
  JWS, so use a real captured one.
- Send the signal directly to test subscription creation without any store:

```python
from payment.signals import purchase_for_subscription_created

purchase_for_subscription_created.send_robust(
    instance=payment_transaction, product=buyable, sender=None
)
```

Tests live in `payment/test/` and `vendor/test/`.

---

## Related

- [user.md](user.md) for `active_subscription` and `has_active_subscription`.
- [common.md](common.md) for the `Translation` rows behind product titles.
- [../conventions/errors.md](../conventions/errors.md) for the error codes used here.
- [../conventions/views.md](../conventions/views.md) for why the webhooks look different.
