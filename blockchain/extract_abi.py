import json

with open("artifacts/contracts/AdaptiveCryptoSecurity.sol/AdaptiveCryptoSecurity.json") as f:
    artifact = json.load(f)

with open("../integration/AdaptiveCryptoSecurity_abi.json", "w") as f:
    json.dump(artifact["abi"], f, indent=2)

print("ABI extracted, function count:", sum(1 for e in artifact["abi"] if e["type"] == "function"))
