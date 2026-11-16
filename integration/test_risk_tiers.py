import json
import os
from pathlib import Path
from web3 import Web3

GANACHE_URL = os.getenv("GANACHE_URL", "http://127.0.0.1:8545")
CONTRACT_ADDRESS = os.environ["CONTRACT_ADDRESS"]
ATTESTOR_ADDRESS = Web3.to_checksum_address(os.environ["ATTESTOR_ADDRESS"])

w3 = Web3(Web3.HTTPProvider(GANACHE_URL))
abi = json.loads(Path(__file__).with_name("AdaptiveCryptoSecurity_abi.json").read_text())
contract = w3.eth.contract(address=Web3.to_checksum_address(CONTRACT_ADDRESS), abi=abi)

accounts = w3.eth.accounts
sender, recipient = accounts[3], accounts[4]

def signed_message_hash(types, values):
    return w3.solidity_keccak(types, values)

nonce = contract.functions.nonces(sender).call()
data_hash = b"\x00" * 32
msg_hash = signed_message_hash(
    ["address", "address", "bytes32", "uint256", "address"],
    [sender, recipient, data_hash, nonce, contract.address],
)
sig = w3.eth.sign(sender, msg_hash)
tx = contract.functions.submitStandardTransaction(
    recipient, data_hash, 0, sig, nonce
).transact({"from": sender, "value": w3.to_wei(0.01, "ether")})
receipt = w3.eth.wait_for_transaction_receipt(tx)
print("LOW risk tx status:", receipt.status)
for log in contract.events.RiskAssessed().process_receipt(receipt):
    print(" ", log["args"])

nonce = contract.functions.nonces(sender).call()
data_hash = w3.keccak(text="salted-payload-commitment")
msg_hash = signed_message_hash(
    ["address", "address", "bytes32", "uint256", "address"],
    [sender, recipient, data_hash, nonce, contract.address],
)
sig = w3.eth.sign(sender, msg_hash)
tx = contract.functions.submitStandardTransaction(
    recipient, data_hash, 1, sig, nonce
).transact({"from": sender, "value": w3.to_wei(0.01, "ether")})
receipt = w3.eth.wait_for_transaction_receipt(tx)
print("MEDIUM risk tx status:", receipt.status)
for log in contract.events.RiskAssessed().process_receipt(receipt):
    print(" ", log["args"])

nonce = contract.functions.nonces(sender).call()
data_hash = w3.keccak(text="high-risk-payload")
# Real post-quantum protection: sign with Dilithium + SPHINCS+ and verify both off-chain
from pq_attestor import create_attestation
payload_hash = signed_message_hash(
    ["address", "address", "bytes32", "uint256", "address"],
    [sender, recipient, data_hash, nonce, contract.address],
)
att = create_attestation(sender, bytes(payload_hash))
pq_sig_hash = att.pq_signature_hash
print(f"PQ attestation: Dilithium sig {att.dilithium_signature_bytes} B, SPHINCS+ sig {att.sphincs_signature_bytes} B, audit -> {att.audit_file}")
msg_hash = signed_message_hash(
    ["address", "address", "bytes32", "bytes32", "uint256", "address"],
    [sender, recipient, data_hash, pq_sig_hash, nonce, contract.address],
)
attestation_sig = w3.eth.sign(ATTESTOR_ADDRESS, msg_hash)
tx = contract.functions.submitHighRiskTransaction(
    recipient, data_hash, pq_sig_hash, attestation_sig, nonce
).transact({"from": sender, "value": w3.to_wei(0.01, "ether")})
receipt = w3.eth.wait_for_transaction_receipt(tx)
print("HIGH risk tx status:", receipt.status)
for log in contract.events.RiskAssessed().process_receipt(receipt):
    print(" ", log["args"])
