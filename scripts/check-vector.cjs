const fs = require('node:fs');
const assert = require('node:assert/strict');
const { TypedDataEncoder, verifyTypedData, keccak256, concat, sha256, toUtf8Bytes, AbiCoder } = require('ethers');
const vector = JSON.parse(fs.readFileSync('artifacts/protocol-vector.json', 'utf8'));
const types = {Receipt: vector.typedData.types.Receipt};
for (const bundle of vector.bundles) {
  assert.equal(TypedDataEncoder.hash(bundle.domain, types, bundle.claim), bundle.receiptId);
  assert.equal(verifyTypedData(bundle.domain, types, bundle.claim, bundle.signature), bundle.claim.issuer);
  assert.equal(sha256(toUtf8Bytes(vector.content)), bundle.claim.contentHash);
  const metadata = Object.fromEntries(Object.keys(bundle.metadata).sort().map(key => [key, bundle.metadata[key]]));
  assert.equal(sha256(toUtf8Bytes(JSON.stringify(metadata))), bundle.claim.metadataHash);
  let hash = keccak256(bundle.receiptId);
  for (const sibling of bundle.proof) hash = keccak256(concat([hash, sibling].sort()));
  assert.equal(hash, bundle.root);
  assert.equal(keccak256(AbiCoder.defaultAbiCoder().encode(['address', 'bytes32'], [bundle.claim.issuer, bundle.root])), bundle.batchId);
}
console.log('Python ↔ ethers: EIP-712 digest, issuer signature, content, metadata, Merkle proof and ABI batch ID match.');
