'use strict';
const $ = id => document.getElementById(id);
let info, currentBundle, issuedBundle, originalContent = '', recent = [], timer, verificationRevision = 0;
const sample = 'AI 内容可以被复制、修改和重新发布。\n\n一份签名凭证记录发行者的声明，原文哈希帮助发现字节变化，链上登记让另一应用独立查询。撤销用于纠正已经发行的错误版本。\n\n来源可验证，并不意味着内容一定真实。';
function toast(message, error = false) {
  clearTimeout(timer); const node = $('notification'); node.textContent = message;
  node.className = 'notification' + (error ? ' error' : ''); node.hidden = false;
  timer = setTimeout(() => { node.hidden = true; }, error ? 10000 : 5000);
}
async function api(path, body) {
  const controller = new AbortController(); const timeout = setTimeout(() => controller.abort(), 100000);
  try {
    const response = await fetch(path, {method: body === undefined ? 'GET' : 'POST',
      headers: body === undefined ? {} : {'Content-Type': 'application/json'},
      body: body === undefined ? undefined : JSON.stringify(body), signal: controller.signal});
    const result = await response.json();
    if (!response.ok) {
      const detail = Array.isArray(result.detail) ? '输入格式不正确，请检查内容、凭证字段和有效期。' : result.detail;
      throw new Error(detail || `请求失败 (${response.status})`);
    }
    return result;
  } catch (error) {
    if (error.name === 'AbortError') throw new Error('请求超时；未确认交易结果，请先检查链上状态再重试。');
    throw error;
  } finally { clearTimeout(timeout); }
}
function selectTab(name) {
  document.querySelectorAll('.tab').forEach(button => {
    const active = button.dataset.tab === name;
    button.classList.toggle('active', active); button.setAttribute('aria-selected', String(active));
  });
  ['issue', 'verify', 'integrate'].forEach(id => { $('panel-' + id).hidden = id !== name; });
}
document.querySelectorAll('.tab').forEach(button => button.addEventListener('click', () => selectTab(button.dataset.tab)));
function updateLength() { $('content-length').textContent = `${$('content').value.length.toLocaleString()} 字符`; }
$('content').addEventListener('input', updateLength);
$('load-example').addEventListener('click', () => { $('content').value = sample; updateLength(); });
$('content').value = sample; updateLength();
function shorten(value) { return value ? value.slice(0, 10) + '…' + value.slice(-8) : '—'; }
function setHash(id, value) { $(id).textContent = shorten(value); $(id).title = value || ''; }
function loadBundle(bundle, content) {
  invalidateVerification();
  currentBundle = bundle;
  if (typeof content === 'string') { originalContent = content; $('verify-content').value = content; }
  else { originalContent = ''; $('verify-content').value = ''; }
  $('bundle-input').value = JSON.stringify(bundle, null, 2);
  $('revoke-button').disabled = false;
}
function renderReceipt(bundle, tx, state = '已登记', hash = '') {
  issuedBundle = bundle;
  $('receipt-empty').hidden = true; $('receipt-result').hidden = false; $('receipt-state').textContent = state;
  $('receipt-title').textContent = bundle.metadata.title;
  setHash('receipt-issuer', bundle.claim.issuer); setHash('receipt-id', bundle.receiptId); setHash('receipt-root', bundle.root);
  $('receipt-count').textContent = `${bundle.batchCount} 份 / ${tx ? '1 笔已确认登记交易' : '登记尚未确认'}`;
  $('receipt-gas').textContent = tx ? Number(tx.gasUsed).toLocaleString() : '—';
  $('receipt-amortized').textContent = tx ? (tx.gasUsed / bundle.batchCount).toLocaleString(undefined, {maximumFractionDigits: 2}) : '—';
  $('receipt-latency').textContent = tx ? `${tx.elapsedMs.toLocaleString()} ms` : '—';
  $('receipt-transaction').textContent = hash || (tx && tx.transactionHash) || '尚未取得交易哈希';
  $('receipt-network-note').textContent = !tx
    ? (hash ? '交易已发出，登记尚未确认。请备份凭证与交易哈希，稍后独立验证；不要重复登记。' : '签名凭证已生成，链上登记尚未完成。可先下载备份；独立验证会检查实际登记状态。')
    : info.mode === 'local'
    ? '本地 EVM 实测 Gas。耗时包含本地执行与服务查询，不能代表 Monad 网络延迟。'
    : '当前可信合约实际交易。耗时包含钱包操作、网络确认与服务查询。';
}
function renderRecent() {
  const root = $('recent'); root.replaceChildren(); root.className = '';
  if (!recent.length) { root.className = 'recent-empty'; root.textContent = '还没有签发记录。先登记一份内容。'; return; }
  recent.forEach(({bundle, content, registration}) => {
    const row = document.createElement('div'); row.className = 'recent-row';
    const icon = document.createElement('span'); icon.className = 'recent-icon'; icon.textContent = '↗';
    const label = document.createElement('div'); label.className = 'recent-label';
    const title = document.createElement('strong'); title.textContent = bundle.metadata.title;
    const id = document.createElement('code'); id.textContent = shorten(bundle.receiptId) + ' · ' + (registration || '登记状态待检查'); label.append(title, id);
    const button = document.createElement('button'); button.type = 'button'; button.textContent = '验证 →';
    button.addEventListener('click', () => { loadBundle(bundle, content); selectTab('verify');
      if (content === undefined) toast('凭证已载入；原文不由服务器保存，请填入原文。'); });
    const download = document.createElement('button'); download.type = 'button'; download.textContent = '下载 JSON';
    download.addEventListener('click', () => downloadBundle(bundle));
    row.append(icon, label, download, button); root.append(row);
  });
}
async function walletAccount() {
  if (!window.ethereum) throw new Error('当前浏览器没有 EVM 钱包。请用安装钱包的浏览器打开；Python SDK 也可签发。');
  const chain = await window.ethereum.request({method: 'eth_chainId'});
  if (parseInt(chain, 16) !== info.chainId) throw new Error(`请在钱包中切换到链 ${info.chainId}，然后重试。`);
  const accounts = await window.ethereum.request({method: 'eth_requestAccounts'});
  if (!accounts.length) throw new Error('没有选择签名账户。');
  return accounts[0];
}
async function waitTransaction(hash) {
  for (let i = 0; i < 60; i++) {
    const result = await api('/api/transactions/' + hash);
    if (!result.pending) { if (result.status !== 1) throw new Error('链上交易执行失败。'); return result; }
    await new Promise(resolve => setTimeout(resolve, 2000));
  }
  throw new Error(`交易仍未确认：${hash}。保留凭证，稍后验证，不要重复登记。`);
}
$('issue-form').addEventListener('submit', async event => {
  event.preventDefault(); if (!info) return toast('网络尚未就绪，请稍后刷新。', true);
  const button = $('issue-button'); button.disabled = true; button.textContent = '签名与登记中…';
  const base = $('content').value; const count = Number($('batch-size').value);
  const expiresAt = Number($('expiry').value) ? Math.floor(Date.now() / 1000) + Number($('expiry').value) : 0;
  const artifacts = Array.from({length: count}, (_, i) => ({
    content: i ? base + `\n\n[批量测试副本 ${i + 1}]` : base,
    metadata: {title: $('title').value + (i ? ` · 测试副本 ${i + 1}` : ''),
      mediaType: 'text/plain;charset=utf-8', model: $('model').value, application: $('application').value},
    parentId: $('parent-id').value.trim() || '0x' + '00'.repeat(32), expiresAt
  }));
  let pendingHash, preparedResult, sessionEntries;
  try {
    const started = performance.now(); let result;
    if (info.mode === 'local') result = await api('/api/demo/issue', {artifacts});
    else {
      const issuer = await walletAccount(); const receipts = [];
      for (const item of artifacts) {
        const prepared = await api('/api/prepare', {...item, issuer});
        const signature = await window.ethereum.request({method: 'eth_signTypedData_v4',
          params: [issuer, JSON.stringify(prepared.typedData)]});
        receipts.push({schemaVersion: 'prooftrail/1', domain: prepared.typedData.domain,
          claim: prepared.claim, metadata: prepared.metadata, signature: signature.toLowerCase(), receiptId: prepared.receiptId});
      }
      result = await api('/api/batch', {receipts});
      // Make every signed bundle downloadable before the wallet can reject or a poll can fail.
      preparedResult = result;
      sessionEntries = result.bundles.map((bundle, i) => ({bundle, content: artifacts[i].content, registration: '登记未确认'}));
      recent.unshift(...sessionEntries); renderRecent();
      loadBundle(result.bundles[0], base);
      renderReceipt(result.bundles[0], null, '已签名 · 尚未登记');
      pendingHash = await window.ethereum.request({method: 'eth_sendTransaction', params: [result.transaction]});
      renderReceipt(result.bundles[0], null, '等待交易确认', pendingHash);
      result.transaction = await waitTransaction(pendingHash);
      result.transaction.elapsedMs = Math.round(performance.now() - started);
    }
    loadBundle(result.bundles[0], base); renderReceipt(result.bundles[0], result.transaction);
    if (sessionEntries) sessionEntries.forEach(entry => { entry.registration = '已登记'; });
    else result.bundles.forEach((bundle, i) => recent.unshift({bundle, content: artifacts[i].content, registration: '已登记'}));
    renderRecent(); toast(`${count} 份凭证已登记，使用 1 笔真实交易。`);
  } catch (error) {
    if (preparedResult) renderReceipt(preparedResult.bundles[0], null, '登记未完成 · 可备份', pendingHash);
    toast(error.message + (pendingHash ? ` 交易 ${pendingHash}` : ''), true);
  }
  finally { button.disabled = false; button.textContent = '签发并登记凭证 ↗'; }
});
function downloadBundle(bundle) {
  if (!bundle) return;
  const url = URL.createObjectURL(new Blob([JSON.stringify(bundle, null, 2) + '\n'], {type: 'application/json'}));
  const link = document.createElement('a'); link.href = url; link.download = 'prooftrail-' + bundle.receiptId.slice(2, 12) + '.json';
  link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}
$('download-bundle').addEventListener('click', () => downloadBundle(issuedBundle));
$('go-verify').addEventListener('click', () => {
  const entry = recent.find(item => item.bundle.receiptId === issuedBundle.receiptId);
  loadBundle(issuedBundle, entry && entry.content); selectTab('verify'); $('verify-form').requestSubmit();
});
function invalidateVerification() {
  verificationRevision++;
  $('verify-status').textContent = '等待重新验证'; $('verify-status').className = '';
  $('verify-summary').textContent = '输入已变化；之前的检查结果不适用于当前内容与凭证。';
  $('checks').replaceChildren(); $('anchor-time').textContent = '';
}
$('verify-content').addEventListener('input', invalidateVerification);
$('bundle-input').addEventListener('input', invalidateVerification);
$('load-chain-example').addEventListener('click', async () => {
  const button = $('load-chain-example'); button.disabled = true;
  invalidateVerification(); const revision = verificationRevision;
  try {
    const example = await api('/api/example');
    if (revision !== verificationRevision) return;
    loadBundle(example.bundle, example.content);
    $('verify-summary').textContent = example.note;
    toast('已载入真实链上公开样例；点击独立验证读取最新状态。');
  } catch (error) { if (revision === verificationRevision) toast(error.message, true); }
  finally { button.disabled = false; }
});
$('tamper').addEventListener('click', () => { $('verify-content').value += '\n[这段内容在签发后被修改]'; invalidateVerification(); toast('已修改待验证内容；运行验证查看哪一项失败。'); });
$('restore').addEventListener('click', () => { if (!originalContent) return toast('当前会话没有原文；请手动填入。', true); $('verify-content').value = originalContent; invalidateVerification(); });
$('bundle-file').addEventListener('change', async event => {
  const file = event.target.files[0]; if (!file) return;
  if (file.size > 256000) return toast('凭证文件超过 256 KB，请检查文件。', true);
  try { const text = await file.text(); const bundle = JSON.parse(text); loadBundle(bundle); toast('已导入凭证，请填入对应原文。'); }
  catch { toast('无法读取 JSON 凭证，请检查文件格式。', true); }
});
function renderVerification(result) {
  const words = {valid: '证据检查通过', invalid: '凭证未通过检查', unavailable: '链上状态无法确认'};
  $('verify-status').textContent = words[result.status]; $('verify-status').className = result.status;
  $('verify-summary').textContent = result.status === 'valid'
    ? '原文、签名、批量证明与可信登记一致，当前未撤销且在有效期内。'
    : result.status === 'invalid' ? '下列证据存在不匹配，请检查失败项。' : '离线证据已检查，但不能确认最新登记与撤销状态。';
  const root = $('checks'); root.replaceChildren();
  result.checks.forEach(check => {
    const li = document.createElement('li'); li.className = check.passed === true ? 'pass' : check.passed === false ? 'fail' : 'unknown';
    const node = document.createElement('span'); node.className = 'check-node'; node.textContent = check.passed === true ? '✓' : check.passed === false ? '×' : '?';
    const description = document.createElement('div'); const title = document.createElement('strong'); title.textContent = check.label;
    const detail = document.createElement('p'); detail.textContent = check.detail; description.append(title, detail); li.append(node, description); root.append(li);
  });
  $('anchor-time').textContent = result.anchoredAt ? '区块登记时间：' + new Date(result.anchoredAt * 1000).toLocaleString('zh-CN') : '';
}
$('verify-form').addEventListener('submit', async event => {
  event.preventDefault(); const button = $('verify-button'); button.disabled = true; button.textContent = '检查证据中…';
  invalidateVerification(); const revision = verificationRevision;
  $('verify-status').textContent = '检查证据中';
  $('verify-summary').textContent = '正在读取当前凭证与最新链上状态。';
  try {
    let bundle; try { bundle = JSON.parse($('bundle-input').value); } catch { throw new Error('凭证不是有效 JSON；请先签发或导入凭证。'); }
    const result = await api('/api/verify', {content: $('verify-content').value, bundle});
    if (revision !== verificationRevision) return;
    currentBundle = bundle; renderVerification(result); $('revoke-button').disabled = false;
  } catch (error) {
    if (revision !== verificationRevision) return;
    $('verify-status').textContent = '检查未完成'; $('verify-status').className = 'unavailable';
    $('verify-summary').textContent = error.message; $('checks').replaceChildren(); $('anchor-time').textContent = '';
    toast(error.message, true);
  } finally { button.disabled = false; button.textContent = '独立验证 →'; }
});
$('revoke-button').addEventListener('click', async () => {
  let bundle; try { bundle = JSON.parse($('bundle-input').value); } catch { return toast('请载入有效凭证。', true); }
  if (!bundle.receiptId) return toast('凭证缺少 ID。', true);
  const dialog = $('revoke-dialog'); dialog.returnValue = 'cancel'; dialog.showModal();
  const confirmed = await new Promise(resolve => dialog.addEventListener('close', () => resolve(dialog.returnValue === 'confirm'), {once:true}));
  if (!confirmed) return;
  invalidateVerification();
  $('verify-status').textContent = '撤销处理中';
  $('verify-summary').textContent = '等待撤销交易确认；确认后需要重新检查链上状态。';
  const button = $('revoke-button'); button.disabled = true;
  try {
    if (info.mode === 'local') await api('/api/demo/revoke', {receiptId: bundle.receiptId});
    else {
      const issuer = await walletAccount();
      if (issuer.toLowerCase() !== bundle.claim.issuer.toLowerCase()) throw new Error('当前钱包不是凭证发行者。');
      const tx = await api('/api/revoke-transaction', {receiptId: bundle.receiptId}); tx.from = issuer;
      await waitTransaction(await window.ethereum.request({method: 'eth_sendTransaction', params: [tx]}));
    }
    toast('撤销已登记。重新检查最新状态。'); $('verify-form').requestSubmit();
  } catch (error) { toast(error.message, true); }
  finally { button.disabled = false; }
});
async function init() {
  try {
    info = await api('/api/info'); $('network-name').textContent = info.mode === 'local' ? '本地 EVM · 真实合约执行' : 'Monad Testnet';
    $('network-dot').style.background = info.mode === 'local' ? '#ba7425' : '#1a8277';
    $('mode-note').textContent = info.mode === 'local'
      ? '检查模式：本地 EVM。签名、合约、交易均真实运行；它不是 Monad 部署证据。服务重启会重置本地链。'
      : 'Monad 测试网：验证直接读取可信合约。签发与撤销使用你自己的钱包，服务器不持有发行者私钥。';
    $('signing-note').textContent = info.mode === 'local' ? '演示使用本地 EVM 测试账户，不需要真实资产。' : '钱包将请求签名与测试网登记交易；不要提供私钥给服务器。';
    $('contract-info').textContent = '可信合约：' + info.contract; $('contract-info').title = 'Chain ID: ' + info.chainId;
    $('load-chain-example').hidden = !info.exampleAvailable;
    $('integration-network-note').textContent = info.mode === 'local'
      ? '本地演示凭证属于本次内存测试链。切换网络后，可信域检查会拒绝旧凭证。'
      : '公开样例属于当前 Monad 测试网合约；消费者独立读取登记与撤销状态，无需连接钱包。';
    const result = await api('/api/receipts'); recent = result.bundles.map(bundle => ({bundle})); renderRecent();
  } catch (error) { $('network-name').textContent = '连接未完成'; $('mode-note').textContent = '无法连接可信合约。请检查服务配置，再刷新页面。'; toast(error.message, true); }
}
init();
