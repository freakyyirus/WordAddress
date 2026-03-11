// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

/**
 * @title Open3Words Proof of Location
 * @notice On-chain verification of location claims using witness consensus.
 */
contract Open3WordsProofOfLocation {

    struct LocationProof {
        bytes32 locationHash;      // keccak256(lat, lon, words)
        address prover;
        uint256 timestamp;
        uint8   witnessesRequired;
        uint8   witnessCount;
        bool    verified;
    }

    mapping(bytes32 => LocationProof) public proofs;
    mapping(bytes32 => mapping(address => bool)) public witnesses;
    mapping(address => uint256) public reputationScores;

    uint256 public constant MIN_REPUTATION = 10;
    uint256 public constant REPUTATION_REWARD = 5;

    event ProofSubmitted(bytes32 indexed proofId, address indexed prover, bytes32 locationHash);
    event ProofWitnessed(bytes32 indexed proofId, address indexed witness, uint8 count);
    event ProofVerified(bytes32 indexed proofId, uint256 timestamp);

    modifier onlyWithReputation() {
        require(reputationScores[msg.sender] >= MIN_REPUTATION, "Insufficient reputation");
        _;
    }

    constructor() {
        // Grant deployer initial reputation
        reputationScores[msg.sender] = 100;
    }

    /**
     * @notice Submit a new location proof
     * @param _locationHash Hash of lat+lon+words
     * @param _witnessesRequired Number of witnesses needed for verification
     */
    function submitProof(
        bytes32 _locationHash,
        uint8   _witnessesRequired
    ) external returns (bytes32 proofId) {
        require(_witnessesRequired >= 1 && _witnessesRequired <= 10, "Invalid witness count");

        proofId = keccak256(abi.encodePacked(_locationHash, msg.sender, block.timestamp));

        proofs[proofId] = LocationProof({
            locationHash: _locationHash,
            prover: msg.sender,
            timestamp: block.timestamp,
            witnessesRequired: _witnessesRequired,
            witnessCount: 0,
            verified: false
        });

        // New provers gain initial reputation
        if (reputationScores[msg.sender] < MIN_REPUTATION) {
            reputationScores[msg.sender] = MIN_REPUTATION;
        }

        emit ProofSubmitted(proofId, msg.sender, _locationHash);
        return proofId;
    }

    /**
     * @notice Witness (confirm) a location proof
     */
    function witnessProof(bytes32 _proofId) external onlyWithReputation {
        LocationProof storage proof = proofs[_proofId];
        require(proof.timestamp > 0, "Proof does not exist");
        require(!proof.verified, "Already verified");
        require(proof.prover != msg.sender, "Cannot witness own proof");
        require(!witnesses[_proofId][msg.sender], "Already witnessed");

        witnesses[_proofId][msg.sender] = true;
        proof.witnessCount++;

        emit ProofWitnessed(_proofId, msg.sender, proof.witnessCount);

        if (proof.witnessCount >= proof.witnessesRequired) {
            proof.verified = true;
            reputationScores[proof.prover] += REPUTATION_REWARD;
            emit ProofVerified(_proofId, block.timestamp);
        }

        reputationScores[msg.sender] += 1; // Small reward for witnessing
    }

    /**
     * @notice Check if a proof is verified
     */
    function isVerified(bytes32 _proofId) external view returns (bool) {
        return proofs[_proofId].verified;
    }

    /**
     * @notice Grant reputation to a new user (admin only, for bootstrapping)
     */
    function grantReputation(address _user, uint256 _amount) external {
        require(reputationScores[msg.sender] >= 100, "Admin only");
        reputationScores[_user] += _amount;
    }
}
