import hashlib
import hmac

class ForwardSecureAuthenticator:
    """Forward-secure key ratchet for audit log authentication.
    
    Generates a MAC tag for each entry using a key that ratchets forward.
    If an attacker compromises the system, they get the current key but 
    cannot reverse the hash function to discover past keys, thereby
    protecting the integrity of historical logs.
    """
    def __init__(self, initial_key: bytes):
        self._current_key = initial_key

    def generate_mac(self, data: str) -> str:
        """Generate MAC for the data using current key."""
        return hmac.new(self._current_key, data.encode("utf-8"), hashlib.sha256).hexdigest()
    
    def verify_mac(self, data: str, expected_mac: str) -> bool:
        """Verify the MAC for the data using current key."""
        if not expected_mac:
            return False
        expected_bytes = bytes.fromhex(expected_mac)
        actual_bytes = bytes.fromhex(self.generate_mac(data))
        return hmac.compare_digest(actual_bytes, expected_bytes)
    
    def ratchet(self) -> None:
        """Derive the next key using a one-way function and discard the old key."""
        self._current_key = hashlib.sha256(self._current_key + b"ratchet").digest()
