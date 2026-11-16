import json
import os
from pathlib import Path
from web3 import Web3

w3 = Web3(Web3.HTTPProvider("http://127.0.0.1:8545"))
abi = json.loads(Path("AdaptiveCryptoSecurity_abi.json").read_text())
contract = w3.eth.contract(
    address=Web3.to_checksum_address(os.environ["CONTRACT_ADDRESS"]), abi=abi
)

owner = w3.eth.accounts[0]
attestor = Web3.to_checksum_address(os.environ["ATTESTOR_ADDRESS"])

tx = contract.functions.setPQAttestor(attestor, True).transact({"from": owner})
receipt = w3.eth.wait_for_transaction_receipt(tx)
print("setPQAttestor status:", receipt.status)
print("attestor now whitelisted:", contract.functions.pqAttestors(attestor).call())
