"""Minimal-scope Google Drive OAuth and app-managed file adapter."""
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
DRIVE_API = "https://www.googleapis.com/drive/v3"
UPLOAD_API = "https://www.googleapis.com/upload/drive/v3"
APP_FOLDER_NAME = "ICMS Encrypted Backups"


class GoogleDriveError(RuntimeError): pass
class GoogleDriveAuthorizationError(GoogleDriveError): pass
class GoogleDriveQuotaError(GoogleDriveError): pass


def authorization_url(*, client_id: str, redirect_uri: str, scope: str, state: str) -> str:
    return AUTH_URL + "?" + urllib.parse.urlencode({"client_id": client_id, "redirect_uri": redirect_uri, "response_type": "code", "scope": scope, "access_type": "offline", "prompt": "consent", "include_granted_scopes": "true", "state": state})


class GoogleDriveAdapter:
    def __init__(self, *, client_id: str, client_secret: str, redirect_uri: str, timeout: float = 30, opener=urllib.request.urlopen, sleeper=time.sleep):
        self.client_id, self.client_secret, self.redirect_uri, self.timeout = client_id, client_secret, redirect_uri, timeout; self._open, self._sleep = opener, sleeper

    def _json(self, request, *, attempts=3):
        for attempt in range(attempts):
            try:
                with self._open(request, timeout=self.timeout) as response: return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as error:
                body = error.read().decode("utf-8", "replace")
                if error.code in {401, 403} and "storageQuotaExceeded" in body: raise GoogleDriveQuotaError("Google Drive storage quota exceeded") from None
                if error.code in {400, 401}: raise GoogleDriveAuthorizationError("Google authorization is invalid or expired") from None
                if error.code in {429, 500, 502, 503, 504} and attempt + 1 < attempts: self._sleep(2 ** attempt); continue
                raise GoogleDriveError(f"Google Drive request failed with status {error.code}") from None
            except (OSError, TimeoutError):
                if attempt + 1 < attempts: self._sleep(2 ** attempt); continue
                raise GoogleDriveError("Google Drive request failed") from None

    def exchange_code(self, code: str) -> dict:
        data = urllib.parse.urlencode({"code": code, "client_id": self.client_id, "client_secret": self.client_secret, "redirect_uri": self.redirect_uri, "grant_type": "authorization_code"}).encode()
        return self._json(urllib.request.Request(TOKEN_URL, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"}))

    def refresh_access_token(self, refresh_token: str) -> dict:
        data = urllib.parse.urlencode({"refresh_token": refresh_token, "client_id": self.client_id, "client_secret": self.client_secret, "grant_type": "refresh_token"}).encode()
        return self._json(urllib.request.Request(TOKEN_URL, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"}))

    def _request(self, url: str, token: str, *, method="GET", data=None, content_type="application/json"):
        return urllib.request.Request(url, data=data, method=method, headers={"Authorization": f"Bearer {token}", "Content-Type": content_type, "Accept": "application/json"})

    def ensure_folder(self, token: str, folder_id: str | None = None) -> str:
        if folder_id:
            item = self._json(self._request(f"{DRIVE_API}/files/{urllib.parse.quote(folder_id)}?fields=id,trashed,mimeType", token))
            if not item.get("trashed") and item.get("mimeType") == "application/vnd.google-apps.folder": return item["id"]
        query = urllib.parse.quote(f"name='{APP_FOLDER_NAME}' and mimeType='application/vnd.google-apps.folder' and trashed=false")
        found = self._json(self._request(f"{DRIVE_API}/files?q={query}&spaces=drive&fields=files(id,name)&pageSize=10", token)).get("files", [])
        if found: return found[0]["id"]
        body = json.dumps({"name": APP_FOLDER_NAME, "mimeType": "application/vnd.google-apps.folder", "appProperties": {"managedBy": "ICMS"}}).encode()
        return self._json(self._request(f"{DRIVE_API}/files?fields=id", token, method="POST", data=body))["id"]

    def upload(self, token: str, path: Path, *, folder_id: str, sha256: str) -> dict:
        metadata = json.dumps({"name": path.name, "parents": [folder_id], "appProperties": {"managedBy": "ICMS", "sha256": sha256}}).encode()
        initiate = self._request(f"{UPLOAD_API}/files?uploadType=resumable&fields=id,name,size,appProperties,md5Checksum", token, method="POST", data=metadata)
        initiate.add_header("X-Upload-Content-Type", "application/octet-stream"); initiate.add_header("X-Upload-Content-Length", str(path.stat().st_size))
        try:
            with self._open(initiate, timeout=self.timeout) as response: location = response.headers["Location"]
        except Exception: raise GoogleDriveError("Could not initiate Google Drive upload") from None
        uploaded = None
        # Re-open the file for each bounded attempt so a transport interruption
        # never retries an exhausted in-memory/request body. Content-Length
        # keeps urllib streaming instead of loading a database archive in RAM.
        for attempt in range(4):
            try:
                with path.open("rb") as source:
                    upload = self._request(location, token, method="PUT", data=source, content_type="application/octet-stream")
                    upload.add_header("Content-Length", str(path.stat().st_size))
                    with self._open(upload, timeout=self.timeout) as response: uploaded = json.loads(response.read().decode("utf-8"))
                break
            except urllib.error.HTTPError as error:
                body = error.read().decode("utf-8", "replace")
                if error.code in {401, 403} and "storageQuotaExceeded" in body: raise GoogleDriveQuotaError("Google Drive storage quota exceeded") from None
                if error.code in {400, 401}: raise GoogleDriveAuthorizationError("Google authorization is invalid or expired") from None
                if error.code not in {429, 500, 502, 503, 504} or attempt == 3: raise GoogleDriveError("Google Drive upload failed") from None
                self._sleep(2 ** attempt)
            except (OSError, TimeoutError):
                if attempt == 3: raise GoogleDriveError("Google Drive upload was interrupted") from None
                self._sleep(2 ** attempt)
        if not uploaded: raise GoogleDriveError("Google Drive upload did not complete")
        if uploaded.get("appProperties", {}).get("sha256") != sha256 or int(uploaded.get("size", -1)) != path.stat().st_size: raise GoogleDriveError("Cloud upload metadata verification failed")
        return uploaded

    def list_managed(self, token: str, *, folder_id: str) -> list[dict]:
        query = urllib.parse.quote(f"'{folder_id}' in parents and appProperties has {{ key='managedBy' and value='ICMS' }} and trashed=false")
        return self._json(self._request(f"{DRIVE_API}/files?q={query}&spaces=drive&fields=files(id,name,size,createdTime,appProperties)&orderBy=createdTime%20desc&pageSize=100", token)).get("files", [])

    def download(self, token: str, file_id: str, destination: Path) -> None:
        request = self._request(f"{DRIVE_API}/files/{urllib.parse.quote(file_id)}?alt=media", token)
        try:
            with self._open(request, timeout=self.timeout) as response, destination.open("xb") as output:
                while chunk := response.read(1024 * 1024): output.write(chunk)
        except Exception: destination.unlink(missing_ok=True); raise GoogleDriveError("Google Drive download failed") from None

    def delete_managed(self, token: str, file_id: str, *, folder_id: str) -> None:
        item = self._json(self._request(f"{DRIVE_API}/files/{urllib.parse.quote(file_id)}?fields=id,parents,appProperties", token))
        if folder_id not in item.get("parents", []) or item.get("appProperties", {}).get("managedBy") != "ICMS": raise GoogleDriveError("Refusing to delete a file not managed by ICMS")
        request = self._request(f"{DRIVE_API}/files/{urllib.parse.quote(file_id)}", token, method="DELETE")
        try:
            with self._open(request, timeout=self.timeout): pass
        except Exception: raise GoogleDriveError("Google Drive deletion failed") from None

    def quota(self, token: str) -> dict:
        return self._json(self._request(f"{DRIVE_API}/about?fields=storageQuota", token)).get("storageQuota", {})
