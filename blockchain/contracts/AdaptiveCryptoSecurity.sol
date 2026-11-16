// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.28;

import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";
import {ECDSA} from "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";

/// @notice Risk-tiered transaction gateway: Low/Medium risk are verified with
/// standard/enhanced ECDSA on-chain; High risk cannot be verified on-chain at
/// all (the EVM has no post-quantum precompiles), so the real Dilithium/
/// SPHINCS+ verification happens off-chain and this contract only checks that
/// a whitelisted pqAttestor signed off on that result.
contract AdaptiveCryptoSecurity is Ownable {
    using ECDSA for bytes32;

    string public constant VERSION = "2.0.0";

    enum RiskLevel {
        Low,
        Medium,
        High
    }

    enum CryptoScheme {
        StandardECDSA,
        EnhancedECDSA,
        PostQuantumAttested
    }

    struct SecureTransaction {
        address sender;
        address recipient;
        uint256 value;
        RiskLevel riskLevel;
        CryptoScheme schemeUsed;
        bytes32 dataHash;
        bool executed;
        uint256 timestamp;
    }

    mapping(bytes32 => SecureTransaction) public transactions;
    mapping(address => bool) public pqAttestors;
    mapping(address => uint256) public nonces;

    event RiskAssessed(bytes32 indexed txId, RiskLevel riskLevel, CryptoScheme scheme);
    event TransactionSecured(bytes32 indexed txId, address indexed sender, address indexed recipient, uint256 value);
    event PQAttestorUpdated(address indexed attestor, bool status);

    constructor() Ownable(msg.sender) {}

    function isOperational() external pure returns (bool) {
        return true;
    }

    /// @notice Whitelist (or revoke) an address as a trusted PQ verification attestor.
    function setPQAttestor(address attestor, bool status) external onlyOwner {
        pqAttestors[attestor] = status;
        emit PQAttestorUpdated(attestor, status);
    }

    /// @notice Handles Low and Medium risk transactions with on-chain ECDSA verification.
    /// Medium risk additionally requires a non-empty commitment hash (Enhanced ECDSA).
    /// High risk must go through submitHighRiskTransaction instead.
    function submitStandardTransaction(
        address recipient,
        bytes32 dataHash,
        RiskLevel riskLevel,
        bytes calldata signature,
        uint256 nonce
    ) external payable returns (bytes32 txId) {
        require(riskLevel == RiskLevel.Low || riskLevel == RiskLevel.Medium, "High risk must use submitHighRiskTransaction");
        require(nonce == nonces[msg.sender], "Invalid nonce");

        if (riskLevel == RiskLevel.Medium) {
            require(dataHash != bytes32(0), "Medium risk requires commitment hash");
        }

        bytes32 messageHash = _toEthSignedMessageHash(
            keccak256(abi.encodePacked(msg.sender, recipient, dataHash, nonce, address(this)))
        );
        require(messageHash.recover(signature) == msg.sender, "Invalid sender signature");

        nonces[msg.sender] = nonce + 1;

        CryptoScheme scheme = riskLevel == RiskLevel.Medium ? CryptoScheme.EnhancedECDSA : CryptoScheme.StandardECDSA;
        txId = keccak256(abi.encodePacked(msg.sender, nonce));

        transactions[txId] = SecureTransaction({
            sender: msg.sender,
            recipient: recipient,
            value: msg.value,
            riskLevel: riskLevel,
            schemeUsed: scheme,
            dataHash: dataHash,
            executed: true,
            timestamp: block.timestamp
        });

        emit RiskAssessed(txId, riskLevel, scheme);
        emit TransactionSecured(txId, msg.sender, recipient, msg.value);

        _forward(recipient, msg.value);
    }

    /// @notice Handles High risk transactions. Verifies only that a whitelisted
    /// pqAttestor signed off on an off-chain post-quantum signature check —
    /// the contract never verifies PQ cryptography itself.
    function submitHighRiskTransaction(
        address recipient,
        bytes32 dataHash,
        bytes32 pqSignatureHash,
        bytes calldata attestationSig,
        uint256 nonce
    ) external payable returns (bytes32 txId) {
        require(nonce == nonces[msg.sender], "Invalid nonce");

        bytes32 messageHash = _toEthSignedMessageHash(
            keccak256(abi.encodePacked(msg.sender, recipient, dataHash, pqSignatureHash, nonce, address(this)))
        );
        address attestor = messageHash.recover(attestationSig);
        require(pqAttestors[attestor], "Invalid or unauthorized PQ attestation");

        nonces[msg.sender] = nonce + 1;

        txId = keccak256(abi.encodePacked(msg.sender, nonce));

        transactions[txId] = SecureTransaction({
            sender: msg.sender,
            recipient: recipient,
            value: msg.value,
            riskLevel: RiskLevel.High,
            schemeUsed: CryptoScheme.PostQuantumAttested,
            dataHash: dataHash,
            executed: true,
            timestamp: block.timestamp
        });

        emit RiskAssessed(txId, RiskLevel.High, CryptoScheme.PostQuantumAttested);
        emit TransactionSecured(txId, msg.sender, recipient, msg.value);

        _forward(recipient, msg.value);
    }

    function getTransaction(bytes32 txId) external view returns (SecureTransaction memory) {
        return transactions[txId];
    }

    /// @dev Inlined equivalent of OpenZeppelin's MessageHashUtils.toEthSignedMessageHash,
    /// avoided here because its Strings.sol dependency uses the Cancun-only `mcopy`
    /// opcode and this project targets the Shanghai EVM for Ganache compatibility.
    function _toEthSignedMessageHash(bytes32 hash) private pure returns (bytes32) {
        return keccak256(abi.encodePacked("\x19Ethereum Signed Message:\n32", hash));
    }

    function _forward(address recipient, uint256 amount) private {
        if (amount > 0) {
            (bool success, ) = recipient.call{value: amount}("");
            require(success, "Transfer failed");
        }
    }
}
