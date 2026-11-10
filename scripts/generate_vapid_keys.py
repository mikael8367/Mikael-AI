"""Gera um par VAPID para Web Push. Execute uma vez e guarde a chave privada."""
import base64
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

private = ec.generate_private_key(ec.SECP256R1())
private_pem = private.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
).decode("ascii")
numbers = private.public_key().public_numbers()
raw_public = b"\x04" + numbers.x.to_bytes(32, "big") + numbers.y.to_bytes(32, "big")
public = base64.urlsafe_b64encode(raw_public).rstrip(b"=").decode("ascii")
print("VAPID_PUBLIC_KEY=" + public)
print("VAPID_PRIVATE_KEY (cole todo o bloco PEM no Render):")
print(private_pem.rstrip())
print("VAPID_SUBJECT=mailto:seu-email@example.com")
