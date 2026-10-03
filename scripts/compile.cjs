const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const solc = require('solc');
const project = path.resolve(__dirname, '..');
const source = fs.readFileSync(path.join(project, 'contracts/ProofTrailRegistry.sol'), 'utf8');
const input = {
  language: 'Solidity',
  sources: {'ProofTrailRegistry.sol': {content: source}},
  settings: {
    optimizer: {enabled: true, runs: 200},
    evmVersion: 'paris',
    outputSelection: {'*': {'*': ['abi', 'evm.bytecode.object', 'evm.deployedBytecode.object']}}
  }
};
const result = JSON.parse(solc.compile(JSON.stringify(input)));
for (const error of result.errors || []) console.error(error.formattedMessage);
if ((result.errors || []).some(e => e.severity === 'error')) process.exit(1);
const contract = result.contracts['ProofTrailRegistry.sol'].ProofTrailRegistry;
const artifact = {
  contractName: 'ProofTrailRegistry', compiler: solc.version(),
  sourceSha256: crypto.createHash('sha256').update(source).digest('hex'),
  settings: input.settings,
  abi: contract.abi,
  bytecode: '0x' + contract.evm.bytecode.object,
  deployedBytecode: '0x' + contract.evm.deployedBytecode.object
};
const out = path.join(project, 'src/prooftrail/data/registry.json');
fs.mkdirSync(path.dirname(out), {recursive: true});
fs.writeFileSync(out, JSON.stringify(artifact, null, 2) + '\n');
const verification = path.join(project, 'artifacts/verification');
fs.mkdirSync(verification, {recursive: true});
fs.writeFileSync(path.join(verification, 'standard-input.json'), JSON.stringify(input, null, 2) + '\n');
fs.writeFileSync(path.join(verification, 'compiler-record.json'), JSON.stringify({
  contract: 'ProofTrailRegistry.sol:ProofTrailRegistry', compiler: artifact.compiler,
  sourceSha256: artifact.sourceSha256, optimizerRuns: 200, evmVersion: 'paris',
  deploymentVerified: false,
  note: 'Compiler inputs only. Actual deployment and explorer source verification are separate gates.'
}, null, 2) + '\n');
console.log(`Compiled ${artifact.contractName} with ${artifact.compiler}; runtime ${contract.evm.deployedBytecode.object.length / 2} bytes`);
