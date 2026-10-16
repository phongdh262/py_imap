import os
import re
from pathlib import Path
from fastapi import HTTPException, status


class PathSecurity:
    """
    Prevents Directory / Path Traversal attacks (e.g. '../', '..\\', null bytes):
    - Validates that requested filenames stay strictly within the designated safe directory
    - Sanitizes uploaded filenames
    """

    @staticmethod
    def validate_safe_path(base_dir: Path, requested_filename: str) -> Path:
        """
        Ensures the requested file resolves inside base_dir and has no traversal sequences.
        Raises HTTP 403 / 400 if an attack is detected.
        """
        # Block null bytes and obvious traversal patterns
        if "\0" in requested_filename or ".." in requested_filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tên file không hợp lệ hoặc chứa ký tự nguy hiểm",
            )

        # Sanitize filename (allow only alphanumeric, dashes, dots, underscores)
        clean_name = re.sub(r"[^\w\.\-]", "_", requested_filename)
        resolved_path = (base_dir / clean_name).resolve()

        # Enforce that resolved path starts with base_dir path
        try:
            resolved_path.relative_to(base_dir.resolve())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Truy cập bị từ chối: Đường dẫn nằm ngoài phạm vi cho phép",
            )

        return resolved_path
