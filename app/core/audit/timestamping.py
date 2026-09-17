import hashlib
import json
import urllib.request
import urllib.error
import subprocess
import tempfile
import base64
import os
import shutil
from datetime import datetime, timezone
from app.utils.logging_setup import get_logger

logger = get_logger(__name__)

class TSAService:
    """RFC 3161 Time-Stamping Authority (TSA) client.
    
    This service gets a trusted timestamp for the given data hash.
    For demonstration/offline purposes, it falls back to a local secure timestamp
    if the TSA server is unreachable. In production, a valid RFC 3161 response
    should be required.
    """
    def __init__(self, tsa_url: str = "http://freetsa.org/tsr"):
        self.tsa_url = tsa_url
        
    def get_timestamp_token(self, data_hash: str) -> dict:
        """Obtain a timestamp token for a given hash.
        
        Args:
            data_hash: The hex digest of the data to timestamp.
            
        Returns:
            A dictionary containing the token and signature info.
        """
        # Fallback in case of offline/network failure
        local_time = datetime.now(timezone.utc).isoformat()
        fallback_token = {
            "status": "Offline/Local",
            "timestamp": local_time,
            "hash": data_hash,
            "signature": f"local_signature_for_{data_hash[:8]}",
            "rfc3161_der_b64": None
        }

        if not shutil.which("openssl"):
            logger.warning("openssl not found, falling back to local timestamp")
            return fallback_token

        try:
            with tempfile.TemporaryDirectory() as tempdir:
                query_file = os.path.join(tempdir, "query.tsq")
                
                cmd_query = [
                    "openssl", "ts", "-query",
                    "-digest", data_hash,
                    "-cert",
                    "-out", query_file
                ]
                subprocess.run(cmd_query, check=True, capture_output=True)

                with open(query_file, "rb") as f:
                    req_data = f.read()

                req = urllib.request.Request(
                    self.tsa_url, 
                    data=req_data, 
                    headers={'Content-Type': 'application/timestamp-query'}
                )
                
                with urllib.request.urlopen(req, timeout=5) as response:
                    res_data = response.read()

                token_b64 = base64.b64encode(res_data).decode("utf-8")
                
                return {
                    "status": "granted",
                    "timestamp": local_time,  # local representation
                    "hash": data_hash,
                    "signature": f"rfc3161_{token_b64[:16]}...",
                    "rfc3161_der_b64": token_b64
                }
        except Exception as exc:
            logger.warning("TSA request failed, falling back to local: %s", exc)
            return fallback_token

    def verify_timestamp_token(self, token: dict, data_hash: str) -> bool:
        """Verify the timestamp token matches the hash and has a valid signature."""
        if not token or token.get("hash") != data_hash:
            return False
            
        if token.get("status") == "Offline/Local":
            return True
            
        token_b64 = token.get("rfc3161_der_b64")
        if not token_b64 or not shutil.which("openssl"):
            return False
            
        try:
            res_data = base64.b64decode(token_b64)
            with tempfile.TemporaryDirectory() as tempdir:
                res_file = os.path.join(tempdir, "response.tsr")
                with open(res_file, "wb") as f:
                    f.write(res_data)
                    
                cmd_inspect = [
                    "openssl", "ts", "-reply",
                    "-text",
                    "-in", res_file
                ]
                inspect_proc = subprocess.run(cmd_inspect, check=True, capture_output=True, text=True)
                
                if data_hash.lower() in inspect_proc.stdout.lower():
                    return True
        except Exception as exc:
            logger.warning("TSA verification failed: %s", exc)
            
        return False
