"""Run in its own window and leave it running:  python collector.py

Collects real Ethereum mainnet network signals from Etherscan. The dashboard
shows them one hour later, so start this at least an hour before the demo.
"""

from core.network import collect_forever

if __name__ == "__main__":
    collect_forever()
