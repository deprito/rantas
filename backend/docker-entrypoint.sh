#!/bin/bash
# Entrypoint script to fix volume permissions and run migrations

# If XARF directory exists but is not writable, fix permissions
if [ -d "/app/xarf_reports" ]; then
    # Try to create a test file
    if ! touch /app/xarf_reports/.test_write 2>/dev/null; then
        # Can't write - need to fix permissions
        # Since we're running as non-root, we can't fix it
        # Fall back to using /tmp for XARF files
        export XARF_STORAGE_PATH="/tmp/xarf_reports"
        echo "Warning: /app/xarf_reports is not writable, using $XARF_STORAGE_PATH"
    else
        rm -f /app/xarf_reports/.test_write
    fi
fi

# Run database migrations automatically on startup
echo "Running database migrations..."
if alembic upgrade head; then
    echo "Migrations completed successfully"
else
    echo "Warning: Migration failed, but continuing startup..."
fi

# Run the main command
exec "$@"
