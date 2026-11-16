"""Create a new key for the post-quantum attestor.  Run once:  python make_attestor_key.py

Put the private key in lab/.env as ATTESTOR_PRIVATE_KEY and use the address as
ATTESTOR_ADDRESS when you deploy the contract. The attestor only signs
approvals; it never sends transactions, so it needs no ETH.
"""

from eth_account import Account

acct = Account.create()
print("ATTESTOR_ADDRESS     =", acct.address)
print("ATTESTOR_PRIVATE_KEY =", "0x" + bytes(acct.key).hex())
print("\nKeep the private key secret. It is for Sepolia testing only.")
