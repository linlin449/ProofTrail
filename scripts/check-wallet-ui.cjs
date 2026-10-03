// Regression tests with a scripted DOM/provider. These are not real wallet or Monad evidence.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const test = require('node:test');

const root = path.resolve(__dirname, '..');
const fixture = JSON.parse(fs.readFileSync(path.join(root, 'src/prooftrail/data/public-example.json'), 'utf8'));
const source = fs.readFileSync(path.join(root, 'src/prooftrail/static/app.js'), 'utf8');

class Element {
  constructor() {
    this.value = ''; this.textContent = ''; this.hidden = false; this.disabled = false;
    this.children = []; this.events = {}; this.style = {};
    this.classList = {toggle() {}};
  }
  addEventListener(name, action) { this.events[name] = action; }
  setAttribute() {}
  replaceChildren(...nodes) { this.children = nodes; }
  append(...nodes) { this.children.push(...nodes); }
}

async function setup(outcome) {
  const nodes = new Map(), downloads = [], blobs = new Map();
  const node = id => { if (!nodes.has(id)) nodes.set(id, new Element()); return nodes.get(id); };
  const bundles = Array.from({length: 4}, (_, index) => ({...fixture.bundle,
    metadata: {...fixture.bundle.metadata, title: `Scripted regression ${index}`},
    receiptId: '0x' + String(index + 1).padStart(64, '0'), batchCount: 4}));
  const provider = {async request({method}) {
    if (method === 'eth_chainId') return '0x279f';
    if (method === 'eth_requestAccounts') return [fixture.bundle.claim.issuer];
    if (method === 'eth_signTypedData_v4') return fixture.bundle.signature;
    if (method === 'eth_sendTransaction') {
      // The real application must expose recovery BEFORE the provider can reject.
      assert.equal(node('receipt-result').hidden, false);
      assert.equal(node('recent').children.length, 4);
      assert.equal(node('receipt-gas').textContent, '—');
      if (outcome === 'rejected') throw new Error('User rejected request');
      return '0x' + 'ab'.repeat(32);
    }
    throw new Error('Unexpected provider method ' + method);
  }};
  const context = vm.createContext({
    console, Blob, AbortController, performance,
    setTimeout: () => 1, clearTimeout: () => {},
    window: {ethereum: provider},
    document: {getElementById: node, querySelectorAll: () => [], createElement(tag) {
      const element = new Element();
      element.click = () => { if (tag === 'a') downloads.push(blobs.get(element.href)); };
      return element;
    }},
    URL: {createObjectURL(blob) { const url = `blob:${blobs.size}`; blobs.set(url, blob); return url; }, revokeObjectURL() {}},
    async fetch(url) {
      let data;
      if (url === '/api/info') data = {mode: 'monad', chainId: 10143, contract: fixture.bundle.domain.verifyingContract, exampleAvailable: true};
      else if (url === '/api/receipts') data = {bundles: []};
      else if (url === '/api/prepare') data = {typedData: {domain: fixture.bundle.domain}, claim: fixture.bundle.claim, receiptId: fixture.bundle.receiptId, metadata: fixture.bundle.metadata};
      else if (url === '/api/batch') data = {bundles, transaction: {to: fixture.bundle.domain.verifyingContract}};
      else if (url.startsWith('/api/transactions/')) {
        if (outcome === 'poll-error') throw new Error('RPC unavailable');
        data = {pending: false, status: 1, transactionHash: '0x' + 'ab'.repeat(32), gasUsed: 88261};
      } else throw new Error('Unexpected API request ' + url);
      return {ok: true, status: 200, async json() {return data;}};
    }
  });
  node('batch-size').value = '4'; node('expiry').value = '0';
  node('title').value = 'Regression'; node('model').value = 'Scripted'; node('application').value = 'Test';
  await vm.runInContext(source, context);
  return {node, bundles, downloads};
}

for (const outcome of ['rejected', 'poll-error']) {
  test(`all receipts remain downloadable after ${outcome}`, async () => {
    const {node, bundles, downloads} = await setup(outcome);
    await node('issue-form').events.submit({preventDefault() {}});
    assert.equal(node('receipt-result').hidden, false);
    assert.equal(node('receipt-state').textContent, '登记未完成 · 可备份');
    assert.equal(node('receipt-gas').textContent, '—');
    assert.equal(node('receipt-amortized').textContent, '—');
    assert.equal(node('receipt-latency').textContent, '—');
    if (outcome === 'poll-error') assert.equal(node('receipt-transaction').textContent, '0x' + 'ab'.repeat(32));
    else assert.equal(node('receipt-transaction').textContent, '尚未取得交易哈希');
    assert.equal(node('recent').children.length, 4);
    for (const [index, row] of node('recent').children.entries()) {
      assert.match(row.children[1].children[1].textContent, /登记未确认/);
      row.children[2].events.click();
      assert.deepEqual(JSON.parse(await downloads.at(-1).text()), bundles[index]);
    }
    assert.equal(node('issue-button').disabled, false);
  });
}

test('successful receipt download stays tied to its card after importing another receipt', async () => {
  const {node, bundles, downloads} = await setup('success');
  await node('issue-form').events.submit({preventDefault() {}});
  assert.equal(node('receipt-state').textContent, '已登记');
  assert.equal(node('receipt-gas').textContent, Number(88261).toLocaleString());
  assert.equal(node('recent').children.length, 4);
  const other = {...fixture.bundle, receiptId: '0x' + 'ff'.repeat(32)};
  await node('bundle-file').events.change({target: {files: [{size: 100, async text() {return JSON.stringify(other);}}]}});
  node('download-bundle').events.click();
  assert.deepEqual(JSON.parse(await downloads.at(-1).text()), bundles[0]);
});
