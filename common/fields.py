from django.db.models import DateTimeField


class DateTimeWithoutTZField(DateTimeField):
    description = "Datetime field without timezone"

    def db_type(self, connection):
        return "timestamp"
