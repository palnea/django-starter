# cloud_storage

[Back to docs index](../README.md)

S3-compatible file storage, used by `common.TranslatedFile`. A plain Python
package, **not** an installed Django app.

---

## Shape

```
cloud_storage/
  get_cloud_storage_client.py   the factory
  idrive_client.py              IDriveClient, CloudRequest
  constants/
    file_upload_constants.py    extension to content-type mapping
```

---

## Getting a client

```python
from cloud_storage.get_cloud_storage_client import get_cloud_storage_client

client = get_cloud_storage_client()
```

The factory reads `settings.CLOUD_STORAGE_VENDOR` and currently understands one
value, `"idrive"`, returning an `IDriveClient` built from `IDRIVE_ENDPOINT_URL`,
`IDRIVE_ACCESS_KEY`, and `IDRIVE_SECRET_ACCESS_KEY`.

> Any other vendor value makes the factory **return `None` implicitly**, with no
> error. The failure then shows up later as `AttributeError: 'NoneType'`. If you
> add a vendor, add an explicit `else` that raises.

---

## `IDriveClient`

A thin boto3 S3 client pointed at a custom `endpoint_url`, so it works against
IDrive e2 or any S3-compatible service, including real AWS S3.

| Method | Does |
|---|---|
| `upload_file(file, file_path, bucket_name)` | `upload_fileobj`. Returns `True`, or `False` on `ClientError` |
| `delete_file(file_path, bucket_name)` | `delete_object`. Logs a warning on failure |
| `create_presigned_url(bucket_name, file_path, expiration=3600, request_type=CloudRequest.Download, content_type=None)` | A time-limited URL. Returns `None` on failure |

`CloudRequest` selects the operation the presigned URL permits:

```python
class CloudRequest(enum.Enum):
    Download = "get_object"
    Upload = "put_object"
```

So the same method issues both download links and direct-to-storage upload links.
Pass `content_type` when presigning an upload, or the storage will not enforce
it.

Errors are handled inconsistently. `upload_file` and `create_presigned_url`
`print(e)` and return a falsy value, while `delete_file` logs properly. Callers
must check return values, because nothing raises.

---

## Public and private buckets

Two buckets, and a flag:

| Setting | Meaning |
|---|---|
| `CLOUD_STORAGE_BUCKET_NAME` | The private bucket. Access through presigned URLs |
| `CLOUD_STORAGE_PUBLIC_BUCKET_NAME` | The public bucket, served directly |
| `CLOUD_STORAGE_BUCKET_IS_PUBLIC` | Whether the default bucket is public. A **string**, not a boolean |
| `IDRIVE_BUCKET_NAME` | Set separately, and separately consumed |

`CLOUD_STORAGE_BUCKET_IS_PUBLIC` comes from `os.environ.get` with no coercion, so
it is `"false"`, the string, which is truthy in Python. Compare it explicitly
rather than testing it for truth.

`PUBLIC_FILE_EXPIRATION_TIMESTAMP = 32503680000` in `settings/base.py` is the
year 3000, used as a never-expires marker for public files.

---

## Content types

`constants/file_upload_constants.py` maps extensions to MIME types for `mp3`,
`wave`, `jpeg`, `jpg`, `svg+xml`, `png`, and `mp4`, via
`get_content_type_from_extension(ext)`, which raises a `CustomException` for
anything else. That mapping is effectively the **allowed upload types**. Extend
it to accept more, for example PDFs.

---

## Where files are used

`common.TranslatedFile` is the only consumer. `TRANSLATED_FILE_DIRECTORY =
"translated_file/"` is the key prefix, and `TranslatedFileSerializer` exposes
`url` and `presigned_url`. See [common.md](common.md).

---

## Configuration

| Variable | Notes |
|---|---|
| `CLOUD_STORAGE_VENDOR` | `idrive` is the only supported value |
| `CLOUD_STORAGE_BUCKET_NAME`, `CLOUD_STORAGE_PUBLIC_BUCKET_NAME` | Bucket names |
| `CLOUD_STORAGE_BUCKET_IS_PUBLIC` | String, not boolean |
| `IDRIVE_ENDPOINT_URL`, `IDRIVE_ACCESS_KEY`, `IDRIVE_SECRET_ACCESS_KEY`, `IDRIVE_BUCKET_NAME` | Credentials |
| `AWS_S3_ACCESS_KEY_ID`, `AWS_S3_SECRET_ACCESS_KEY` | Read into settings, but no code path uses them today. Present for swapping to real S3 |

`settings/development.py` supplies placeholder defaults, so the app boots without
credentials. Uploads will fail at call time.

---

## Testing

There is no local stub. Either mock `get_cloud_storage_client`, or point the
endpoint at MinIO or LocalStack. Since every method returns a falsy value instead
of raising, a test that ignores return values will pass against a broken
configuration.

---

## Related

- [common.md](common.md) for `TranslatedFile`.
- [../operations/settings-and-env.md](../operations/settings-and-env.md).
