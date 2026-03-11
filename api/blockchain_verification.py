"""
Blockchain Verification Layer for Open3Words
Integrates with Ethereum-compatible chains for Proof of Location.
"""

import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from web3 import Web3
    WEB3_AVAILABLE = True
except ImportError:
    WEB3_AVAILABLE = False
    logger.info("web3 not installed – blockchain features disabled")


@dataclass
class LocationProof:
    proof_id: str
    location_hash: str
    prover: str
    timestamp: int
    witnesses_required: int
    witness_count: int = 0
    verified: bool = False


class BlockchainVerifier:
    """Manages on-chain proof-of-location interactions."""

    def __init__(
        self,
        rpc_url: str = None,
        contract_address: str = None,
        private_key: str = None,
    ):
        self.rpc_url = rpc_url or os.getenv("WEB3_RPC_URL", "http://localhost:8545")
        self.contract_address = contract_address or os.getenv("CONTRACT_ADDRESS", "")
        self.private_key = private_key or os.getenv("PRIVATE_KEY", "")
        self.w3 = None
        self.contract = None

        if WEB3_AVAILABLE:
            try:
                self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
                if self.contract_address:
                    self._load_contract()
            except Exception as e:
                logger.warning(f"Could not connect to blockchain: {e}")

    def _load_contract(self):
        abi_path = os.path.join(os.path.dirname(__file__), "..", "contracts", "abi.json")
        if os.path.exists(abi_path):
            with open(abi_path) as f:
                abi = json.load(f)
            self.contract = self.w3.eth.contract(
                address=Web3.to_checksum_address(self.contract_address),
                abi=abi,
            )
        else:
            logger.warning("Contract ABI not found – blockchain calls will fail")

    @staticmethod
    def hash_location(lat: float, lon: float, words: str) -> str:
        """Create a deterministic hash of a location claim."""
        payload = f"{lat:.7f}:{lon:.7f}:{words.lower().strip()}"
        return "0x" + hashlib.sha256(payload.encode()).hexdigest()

    def submit_proof(
        self,
        lat: float,
        lon: float,
        words: str,
        witnesses_required: int = 1,
    ) -> Optional[str]:
        """Submit a proof-of-location to the chain. Returns tx hash."""
        if not self.contract or not self.private_key:
            logger.info("Blockchain not configured – skipping submit")
            return None

        location_hash = self.hash_location(lat, lon, words)
        account = self.w3.eth.account.from_key(self.private_key)

        try:
            tx = self.contract.functions.submitProof(
                bytes.fromhex(location_hash[2:]),
                witnesses_required,
            ).build_transaction({
                "from": account.address,
                "nonce": self.w3.eth.get_transaction_count(account.address),
                "gas": 200000,
                "gasPrice": self.w3.eth.gas_price,
            })

            signed = self.w3.eth.account.sign_transaction(tx, self.private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
            return tx_hash.hex()
        except Exception as e:
            logger.error(f"Blockchain submit failed: {e}")
            return None

    def verify_proof(self, proof_id: str) -> bool:
        """Check on-chain verification status."""
        if not self.contract:
            return False

        try:
            return self.contract.functions.isVerified(
                bytes.fromhex(proof_id[2:] if proof_id.startswith("0x") else proof_id)
            ).call()
        except Exception as e:
            logger.error(f"Verification check failed: {e}")
            return False

    def witness_proof(self, proof_id: str) -> Optional[str]:
        """Witness (confirm) a proof-of-location on-chain."""
        if not self.contract or not self.private_key:
            return None

        account = self.w3.eth.account.from_key(self.private_key)

        try:
            tx = self.contract.functions.witnessProof(
                bytes.fromhex(proof_id[2:] if proof_id.startswith("0x") else proof_id)
            ).build_transaction({
                "from": account.address,
                "nonce": self.w3.eth.get_transaction_count(account.address),
                "gas": 150000,
                "gasPrice": self.w3.eth.gas_price,
            })

            signed = self.w3.eth.account.sign_transaction(tx, self.private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
            return tx_hash.hex()
        except Exception as e:
            logger.error(f"Witnessing failed: {e}")
            return None

    def get_reputation(self, address: str) -> int:
        """Query the reputation score for an address."""
        if not self.contract:
            return 0
        try:
            return self.contract.functions.reputationScores(
                Web3.to_checksum_address(address)
            ).call()
        except Exception:
            return 0
