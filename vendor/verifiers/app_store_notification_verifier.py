import datetime
import os

import jwt
from cryptography.x509 import load_der_x509_certificate, load_pem_x509_certificate
from OpenSSL.crypto import (
    X509Store,
    X509StoreContext,
    X509StoreContextError,
    load_certificate,
    FILETYPE_ASN1,
    FILETYPE_PEM,
)
from structlog import get_logger

from vendor.types import (
    StoreNotificationVerificationResult,
    AppStoreNotificationSubtype,
    AppStoreNotificationType,
)

log = get_logger(__name__)


class InvalidTokenError(Exception):
    pass


class AppStoreNotificationVerifier:
    @staticmethod
    def add_labels(key: str) -> bytes:
        return (
            "-----BEGIN CERTIFICATE-----\n" + key + "\n-----END CERTIFICATE-----"
        ).encode()

    @staticmethod
    def _get_root_cert(root_cert_path):
        fn = os.environ.get("APPLE_ROOT_CA")
        if fn is None:
            fn = root_cert_path or "AppleRootCA-G3.cer"

        fn = os.path.expanduser(fn)
        with open(fn, "rb") as f:
            data = f.read()
            root_cert = load_certificate(FILETYPE_ASN1, data)

        return root_cert

    @staticmethod
    def _verify_and_decode_jws(token, root_cert_path, algorithms):
        """
        Verify the JWS signature using the certificate chain in the x5c header
        and decode the payload. The leaf certificate is validated against the
        Apple root CA via a full chain-of-trust check.

        Raises InvalidTokenError if verification fails.
        """
        try:
            # Extract the header to get the x5c certificate chain
            unverified_header = jwt.get_unverified_header(token)
            x5c = unverified_header.get("x5c", [])

            if not x5c:
                raise InvalidTokenError(
                    "JWS token missing x5c certificate chain in header"
                )

            # Build the certificate chain from x5c
            # x5c[0] is the leaf cert (signing cert), x5c[-1] should chain to root
            import base64

            certs = []
            for cert_b64 in x5c:
                cert_der = base64.b64decode(cert_b64)
                certs.append(load_certificate(FILETYPE_ASN1, cert_der))

            # Verify the certificate chain against the Apple root CA
            root_cert = AppStoreNotificationVerifier._get_root_cert(root_cert_path)

            store = X509Store()
            store.add_cert(root_cert)
            # Add intermediate certs (all except the leaf)
            for intermediate_cert in certs[1:]:
                store.add_cert(intermediate_cert)

            # Verify the leaf certificate against the chain
            store_ctx = X509StoreContext(store, certs[0])
            store_ctx.verify_certificate()

            # Extract the public key from the leaf certificate for JWT verification
            leaf_cert_der = base64.b64decode(x5c[0])
            leaf_cert = load_der_x509_certificate(leaf_cert_der)
            public_key = leaf_cert.public_key()

            # Decode and verify the JWT signature
            payload = jwt.decode(
                token,
                public_key,
                algorithms=algorithms,
            )
            return payload

        except X509StoreContextError as err:
            log.warning(
                "Apple JWS certificate chain verification failed",
                error=str(err),
            )
            raise InvalidTokenError(f"Certificate chain verification failed: {err}")
        except jwt.exceptions.PyJWTError as err:
            log.warning(
                "Apple JWS JWT verification failed",
                error=str(err),
            )
            raise InvalidTokenError(f"JWT verification failed: {err}")
        except Exception as err:
            log.warning(
                "Apple JWS verification failed with unexpected error",
                error=str(err),
            )
            raise InvalidTokenError(f"JWS verification failed: {err}")

    @staticmethod
    def _decode_jws_without_verification(token):
        """
        Decode a JWS token without verifying the signature.
        Only used as a fallback or for test notifications.
        """
        return jwt.decode(
            token, algorithms=["ES256", "RS256"], options={"verify_signature": False}
        )

    @staticmethod
    def parse(
        req_body, apple_root_cert_path=None, algorithms=["ES256"]
    ) -> StoreNotificationVerificationResult:
        token = req_body["signedPayload"]

        # Verify and decode the main token with signature verification
        payload = AppStoreNotificationVerifier._verify_and_decode_jws(
            token, root_cert_path=apple_root_cert_path, algorithms=algorithms
        )

        if payload["notificationType"] == "TEST":
            return StoreNotificationVerificationResult.from_verification_result(
                notification_type=AppStoreNotificationType.TEST,
                subtype=AppStoreNotificationSubtype.NONE,
                notification_id=payload.get("notificationUUID", ""),
                data={},
                notification_publish_time=datetime.datetime.utcnow(),
            )

        # Verify and decode signedTransactionInfo
        signedTransactionInfo = AppStoreNotificationVerifier._verify_and_decode_jws(
            payload["data"]["signedTransactionInfo"],
            root_cert_path=apple_root_cert_path,
            algorithms=algorithms,
        )
        payload["data"]["signedTransactionInfo"] = signedTransactionInfo

        # Verify and decode signedRenewalInfo
        if "signedRenewalInfo" in payload["data"]:
            signedRenewalInfo = AppStoreNotificationVerifier._verify_and_decode_jws(
                payload["data"]["signedRenewalInfo"],
                root_cert_path=apple_root_cert_path,
                algorithms=algorithms,
            )
            payload["data"]["signedRenewalInfo"] = signedRenewalInfo

        verification_result = {
            "notification_type": AppStoreNotificationType(
                payload.get("notificationType", None)
            ),
            "subtype": AppStoreNotificationSubtype(payload.get("subtype", None)),
            "notification_id": payload["notificationUUID"],
            "data": payload["data"],
            "notification_publish_time": datetime.datetime.utcnow(),
        }
        return StoreNotificationVerificationResult.from_verification_result(
            **verification_result
        )
