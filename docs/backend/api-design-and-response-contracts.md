# API Design and Response Contracts

Conventions for Django REST Framework views, serializers, and response formatting.

## partial_update Pattern

When overriding `partial_update`, always pass `partial=True` to the serializer. Without it, all required fields will be enforced and the PATCH request will behave like a PUT.

### Correct Implementation

```python
from structlog import get_logger
from common.response.view_response import ViewResponse, log_view_response
from common.response.response_information_codes.message_code import MessageCode

log = get_logger(__name__)


class MyViewSet(OwnershipMixin, ModelViewSet):
    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        view_response = ViewResponse(
            response_body=self.get_serializer(instance).data,
            response_status=200,
            is_successful=True,
            response_information_code=MessageCode.UPDATE_CONTENT_SUCCESS,
        )
        log_view_response(
            struct_logger=log,
            view_name=self.__class__.__name__,
            method_name="partial_update",
            request_body=request.data,
            request_path=request.get_full_path(),
            request_method=request.method,
            view_response=view_response,
        )
        return view_response.rest_response
```

### Why `partial=True` Matters

- **Without it:** The serializer treats every field as required. A PATCH sending only `{"name": "new"}` will fail validation if `email` is also required.
- **With it:** Only the submitted fields are validated and updated, which is the correct PATCH semantic per RFC 5789.

### Using `get_serializer_class` for Action-Specific Serializers

If the partial update needs a different serializer (e.g., fewer writable fields), use the standard action dispatch:

```python
def get_serializer_class(self):
    if self.action == "partial_update":
        return MyPartialUpdateSerializer
    return MySerializer
```

Even with a dedicated serializer, always pass `partial=True` so that the caller is not forced to send every field the serializer declares.
