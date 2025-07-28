#!/bin/bash

# Run all test_*.py files in the repository
echo "Finding and running test files..."
temp_file=$(mktemp)
trap "rm -f $temp_file" EXIT

# Find and store unique test directories
find . -type f -name "test_*.py" -exec dirname {} \; | sort -u > $temp_file

while IFS= read -r dir; do
    echo "Running Django tests in $dir..."
    python manage.py test "$dir" --settings=settings.local_test
    if [ $? -ne 0 ]; then
        echo "Tests failed in $dir. Please fix the tests and try again."
        exit 1
    fi
done < "$temp_file"

echo "All tests completed successfully!"