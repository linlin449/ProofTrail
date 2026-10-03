// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

/// @title ProofTrailRegistry — issuer-owned batch commitments and receipt revocations
/// @notice No administrator, upgrade path, content custody, token, or payment function.
/// @dev Root inclusion and EIP-712 issuer signatures are verified by independent clients.
contract ProofTrailRegistry {
    struct Batch {
        address issuer;
        bytes32 root;
        uint32 count;
        uint64 anchoredAt;
    }

    mapping(bytes32 => Batch) public batches;
    mapping(address => mapping(bytes32 => bool)) public revoked;
    uint32 public constant MAX_BATCH_SIZE = 4096;

    event BatchAnchored(bytes32 indexed batchId, address indexed issuer, bytes32 root, uint32 count);
    event ReceiptRevoked(address indexed issuer, bytes32 indexed receiptId);

    error InvalidBatch();
    error DuplicateBatch();
    error InvalidReceipt();
    error AlreadyRevoked();

    function batchIdFor(address issuer, bytes32 root) public pure returns (bytes32) {
        return keccak256(abi.encode(issuer, root));
    }

    function anchorBatch(bytes32 root, uint32 count) external returns (bytes32 batchId) {
        if (root == bytes32(0) || count == 0 || count > MAX_BATCH_SIZE) revert InvalidBatch();
        batchId = batchIdFor(msg.sender, root);
        if (batches[batchId].issuer != address(0)) revert DuplicateBatch();
        batches[batchId] = Batch(msg.sender, root, count, uint64(block.timestamp));
        emit BatchAnchored(batchId, msg.sender, root, count);
    }

    function revoke(bytes32 receiptId) external {
        if (receiptId == bytes32(0)) revert InvalidReceipt();
        if (revoked[msg.sender][receiptId]) revert AlreadyRevoked();
        revoked[msg.sender][receiptId] = true;
        emit ReceiptRevoked(msg.sender, receiptId);
    }
}
