import io
import logging
import uuid
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

import pandas as pd
import pyreadstat
from fastapi import HTTPException, UploadFile, status

from ..config import settings

logger = logging.getLogger("edhs_core")

# Max size for URL-based dataset download (bytes)
URL_DOWNLOAD_MAX_BYTES = 500_000_000  # 500 MB
URL_DOWNLOAD_TIMEOUT_SECONDS = 120


@dataclass
class SessionData:
    """
    In-memory representation of a processing session.

    Stores a Pandas DataFrame and basic metadata. This object must not
    be serialized to any persistent store for DHS microdata.

    Survey metadata (country, year, type) is used to auto-fill admin
    boundaries and display labels (e.g. "EDHS 2019") in the UI.
    """

    tenant_id: str
    df: pd.DataFrame
    created_at: datetime
    expires_at: datetime
    filename: Optional[str] = None
    survey_country_code: Optional[str] = None
    survey_year: Optional[int] = None
    survey_type: Optional[str] = None


class SessionManager:
    """
    Manage in-memory processing sessions for DHS datasets.

    This implementation is intentionally simple and process-local.
    For a distributed deployment, this can be replaced with a
    distributed cache (e.g., Redis) while still respecting the
    no-persistence constraint by configuring suitable TTLs and
    disallowing backups for microdata keys.
    """

    def __init__(self, ttl_seconds: int) -> None:
        self._ttl = ttl_seconds
        self._sessions: Dict[Tuple[str, str], SessionData] = {}

    async def create_session_from_upload(
        self,
        tenant_id: str,
        upload: UploadFile,
        *,
        survey_country_code: Optional[str] = None,
        survey_year: Optional[int] = None,
        survey_type: Optional[str] = None,
    ) -> str:
        """
        Create a new session from an uploaded DHS/EDHS dataset.

        Supports .dta and .sav formats via `pyreadstat`.
        Optional survey metadata is stored for UI pre-fill and exports.
        """

        filename = upload.filename or ""
        lower = filename.lower()
        if not (lower.endswith(".dta") or lower.endswith(".sav")):
            logger.warning("Upload rejected: unsupported extension filename=%s", filename)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only .dta and .sav files are supported.",
            )

        # Read into memory; no on-disk persistence of raw microdata.
        content = await upload.read()
        if not content:
            logger.warning("Upload rejected: empty file filename=%s", filename)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty.",
            )

        df = self._read_dta_or_sav(content, filename)
        return self._create_session_from_dataframe(
            tenant_id=tenant_id,
            df=df,
            filename=filename or None,
            survey_country_code=survey_country_code,
            survey_year=survey_year,
            survey_type=survey_type,
        )

    def _read_dta_or_sav(self, content: bytes, filename: str) -> pd.DataFrame:
        """Parse bytes as .dta or .sav; raise HTTPException on failure."""
        lower = (filename or "").lower()
        if not (lower.endswith(".dta") or lower.endswith(".sav")):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only .dta and .sav files are supported.",
            )
        err_msg_extra = ""
        try:
            if lower.endswith(".dta"):
                # Try pandas first (supports Stata 14+ format 118/119); then pyreadstat
                for reader_name, reader in [
                    ("pandas", self._read_dta_pandas),
                    ("pyreadstat", self._read_dta_pyreadstat),
                ]:
                    try:
                        df = reader(io.BytesIO(content))
                        return df
                    except Exception as e:
                        logger.debug("DTA reader %s failed for %s: %s", reader_name, filename, e)
                        if not err_msg_extra:
                            err_msg_extra = str(e)
                        continue
                # Both readers failed
            else:
                df, _ = pyreadstat.read_sav(io.BytesIO(content))
                return df
        except HTTPException:
            raise
        except Exception as e:
            logger.warning("Could not read DTA/SAV filename=%s error=%s", filename, e)
            err_msg_extra = str(e)
        # Build user-friendly detail
        err_lower = err_msg_extra.lower()
        is_stata_version_unsupported = (
            "version" in err_lower and "not supported" in err_lower
        )
        is_stata_123 = "123" in err_msg_extra and "119" in err_msg_extra
        if is_stata_version_unsupported and is_stata_123:
            detail = (
                "This file is Stata 17 format (version 123). Our reader supports up to Stata 16 (v119). "
                "When loading from the DHS Program API: use the SPSS (.sav) version of the same dataset instead. "
                "In the DHS dataset list, pick the file whose name ends with 'SV.ZIP' (SPSS), not 'DT' (Stata), "
                "and use that download URL. SPSS files work with this tool."
            )
        elif is_stata_version_unsupported:
            detail = (
                "This file format version is not supported. "
                "For Stata: re-save in Stata as 'Stata 14 compatible' (.dta). "
                "For SPSS: save as a compatible .sav (e.g. SPSS 20 or earlier format). "
                f"Original error: {err_msg_extra}"
            )
        else:
            detail = f"Could not read file as DTA/SAV. Ensure it is a valid Stata or SPSS dataset. ({err_msg_extra})"
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail) from None

    def _read_dta_pandas(self, buf: io.BytesIO) -> pd.DataFrame:
        """Read .dta with pandas (supports format 118/119)."""
        return pd.read_stata(
            buf,
            convert_categoricals=False,
            convert_dates=False,
        )

    def _read_dta_pyreadstat(self, buf: io.BytesIO) -> pd.DataFrame:
        """Read .dta with pyreadstat."""
        df, _ = pyreadstat.read_dta(
            buf,
            apply_value_formats=False,
            formats_as_category=False,
        )
        return df

    def _create_session_from_dataframe(
        self,
        tenant_id: str,
        df: pd.DataFrame,
        *,
        filename: Optional[str] = None,
        survey_country_code: Optional[str] = None,
        survey_year: Optional[int] = None,
        survey_type: Optional[str] = None,
    ) -> str:
        """Store a session from an already-parsed DataFrame; return session_id."""
        session_id = str(uuid.uuid4())
        now = datetime.utcnow()
        expires_at = now + timedelta(seconds=self._ttl)
        key = (tenant_id, session_id)
        self._sessions[key] = SessionData(
            tenant_id=tenant_id,
            df=df,
            created_at=now,
            expires_at=expires_at,
            filename=filename,
            survey_country_code=survey_country_code,
            survey_year=survey_year,
            survey_type=survey_type,
        )
        return session_id

    async def create_session_from_url(
        self,
        tenant_id: str,
        dataset_url: str,
        *,
        survey_country_code: Optional[str] = None,
        survey_year: Optional[int] = None,
        survey_type: Optional[str] = None,
    ) -> str:
        """
        Create a new session by downloading a DHS/EDHS dataset from a URL.

        The URL may point to a .dta or .sav file, or to a .zip archive
        containing exactly one .dta or .sav file. Download is limited by
        URL_DOWNLOAD_MAX_BYTES and URL_DOWNLOAD_TIMEOUT_SECONDS.
        """
        import httpx

        if not dataset_url.strip().lower().startswith(("http://", "https://")):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="dataset_url must be an http or https URL.",
            )

        try:
            async with httpx.AsyncClient(
                follow_redirects=True,
                timeout=URL_DOWNLOAD_TIMEOUT_SECONDS,
            ) as client:
                # Stream with a size limit to avoid loading huge files into memory
                size = 0
                chunks = []
                async with client.stream("GET", dataset_url) as response:
                    response.raise_for_status()
                    content_length = response.headers.get("content-length")
                    if content_length:
                        cl = int(content_length)
                        if cl > URL_DOWNLOAD_MAX_BYTES:
                            raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"Dataset at URL is too large (>{URL_DOWNLOAD_MAX_BYTES // 1_000_000} MB).",
                            )
                    async for chunk in response.aiter_bytes():
                        size += len(chunk)
                        if size > URL_DOWNLOAD_MAX_BYTES:
                            raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"Dataset at URL exceeds {URL_DOWNLOAD_MAX_BYTES // 1_000_000} MB.",
                            )
                        chunks.append(chunk)
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to download URL: HTTP {e.response.status_code}.",
            ) from e
        except httpx.RequestError as e:
            logger.warning("URL download failed: url=%s error=%s", dataset_url[:80], e)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to download URL: {e!s}.",
            ) from e

        content = b"".join(chunks)
        if not content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="URL returned empty content.",
            )

        # If content looks like ZIP, extract first .dta or .sav
        filename: Optional[str] = None
        if content[:4] == b"PK\x03\x04" or content[:2] == b"PK":
            try:
                with zipfile.ZipFile(io.BytesIO(content), "r") as zf:
                    for name in zf.namelist():
                        lower_name = name.lower()
                        if lower_name.endswith(".dta") or lower_name.endswith(".sav"):
                            content = zf.read(name)
                            filename = name.split("/")[-1] or name
                            break
                    if filename is None:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="ZIP archive does not contain a .dta or .sav file.",
                        )
            except zipfile.BadZipFile:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="URL content appears to be ZIP but is not a valid archive.",
                ) from None
        else:
            # Use URL path or default extension
            from urllib.parse import unquote, urlparse

            path = unquote(urlparse(dataset_url).path or "")
            base = path.split("/")[-1] or "dataset"
            if not (base.lower().endswith(".dta") or base.lower().endswith(".sav")):
                base = f"{base}.dta"
            filename = base

        df = self._read_dta_or_sav(content, filename)
        return self._create_session_from_dataframe(
            tenant_id=tenant_id,
            df=df,
            filename=filename,
            survey_country_code=survey_country_code,
            survey_year=survey_year,
            survey_type=survey_type,
        )

    async def create_session_from_dataframe(
        self,
        tenant_id: str,
        df: pd.DataFrame,
        *,
        filename: Optional[str] = None,
        survey_country_code: Optional[str] = None,
        survey_year: Optional[int] = None,
        survey_type: Optional[str] = None,
    ) -> str:
        """
        Create a new session directly from an in-memory DataFrame.

        This is primarily used for testing and demonstration purposes;
        microdata remains process-local and non-persistent.
        Optional survey metadata is stored for UI pre-fill and exports.
        """
        return self._create_session_from_dataframe(
            tenant_id=tenant_id,
            df=df,
            filename=filename,
            survey_country_code=survey_country_code,
            survey_year=survey_year,
            survey_type=survey_type,
        )

    def get_session(self, tenant_id: str, session_id: str) -> SessionData:
        """
        Retrieve an existing session or raise 404 if not found/expired.
        """

        key = (tenant_id, session_id)
        session = self._sessions.get(key)
        if session is None or session.expires_at < datetime.utcnow():
            # Clean up expired entry if present.
            if session is not None:
                del self._sessions[key]
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found or expired.",
            )
        return session

    def clear_expired(self) -> None:
        """
        Remove expired sessions from memory.
        """

        now = datetime.utcnow()
        expired_keys = [key for key, s in self._sessions.items() if s.expires_at < now]
        for key in expired_keys:
            del self._sessions[key]


_session_manager = SessionManager(ttl_seconds=settings.SESSION_TTL_SECONDS)


def get_session_manager() -> SessionManager:
    """
    FastAPI dependency to inject the global SessionManager.
    """

    return _session_manager
