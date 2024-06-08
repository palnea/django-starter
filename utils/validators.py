from typing import List, Dict


class BaseValidator:
    def __init__(self, data: Dict):
        self._data = data

    def check_nulls(self, fields: List) -> List:
        errors = []
        if fields:
            for field in fields:
                if not self._data.get(field, None):
                    errors.append(f"{field} cannot be null.")
        return errors
