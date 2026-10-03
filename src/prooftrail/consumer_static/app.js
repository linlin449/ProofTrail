'use strict';
const $ = id => document.getElementById(id);
let revision = 0;
function clearResult() {
  revision++; $('status').textContent = '等待重新检查'; $('status').className = '';
  $('summary').textContent = '输入已变化，之前的预览和检查结果已清除。';
  $('checks').replaceChildren(); $('preview').hidden = true;
  $('title').textContent = ''; $('issuer').textContent = ''; $('preview-content').textContent = '';
}
['content', 'bundle'].forEach(id => $(id).addEventListener('input', clearResult));
async function request(path, body) {
  const controller = new AbortController(); const timeout = setTimeout(() => controller.abort(), 40000);
  try {
    const response = await fetch(path, {method:body === undefined ? 'GET' : 'POST',
      headers:body === undefined ? {} : {'Content-Type':'application/json'},
      body:body === undefined ? undefined : JSON.stringify(body),signal:controller.signal});
    const result = await response.json();
    if (!response.ok) throw new Error(Array.isArray(result.detail) ? '凭证字段或内容格式无效。' : result.detail || '服务无法完成检查。');
    return result;
  } catch(error) { if(error.name === 'AbortError') throw new Error('检查超时，未确认最新链上状态。'); throw error; }
  finally { clearTimeout(timeout); }
}
$('file').addEventListener('change', async event => {
  const file = event.target.files[0]; if (!file) return;
  clearResult(); const current = revision;
  try {
    if (file.size > 256000) throw new Error('凭证文件超过 256 KB。');
    const text = await file.text(); JSON.parse(text);
    if (current !== revision) return;
    $('bundle').value = text; $('summary').textContent = '凭证已导入，请填入原文并运行检查。';
  } catch(error) { if(current === revision) $('summary').textContent = error.message; }
});
$('form').addEventListener('submit', async event => {
  event.preventDefault(); clearResult(); const current = revision;
  $('submit').disabled = true; $('status').textContent = '读取证据与链上状态…';
  $('summary').textContent = '正在检查当前内容、凭证与可信链上的最新状态。';
  try {
    let bundle; try {bundle = JSON.parse($('bundle').value);} catch {throw new Error('凭证不是有效 JSON。');}
    const result = await request('/api/assess', {content:$('content').value,bundle});
    if(current !== revision) return;
    const verification = result.verification;
    $('status').className = verification.status;
    $('status').textContent = result.eligibleForPreview ? '来源证据通过，可预览' : verification.status === 'unavailable' ? '链上状态无法确认' : '暂停预览：证据未通过';
    $('summary').textContent = result.eligibleForPreview ? '本应用完成独立检查。下面是私有预览，没有公开发布。' : '需要修正或重新确认后再使用内容。';
    verification.checks.forEach(check => {
      const li = document.createElement('li'); li.className = check.passed === true ? 'pass' : check.passed === false ? 'fail' : 'unknown';
      const icon = document.createElement('span'); icon.textContent = check.passed === true ? '✓' : check.passed === false ? '×' : '?';
      const text = document.createElement('div'); text.textContent = check.label;
      const detail = document.createElement('small'); detail.textContent = check.detail; text.append(detail); li.append(icon,text); $('checks').append(li);
    });
    if(result.preview) {
      $('title').textContent = result.preview.title; $('issuer').textContent = '发行者 / '+result.preview.issuer;
      $('preview-content').textContent = result.preview.content; $('preview').hidden = false;
    }
  } catch(error) {
    if(current !== revision) return;
    $('status').textContent = '检查未完成'; $('status').className = 'unavailable'; $('summary').textContent = error.message;
  } finally {$('submit').disabled = false;}
});
request('/api/info').then(info => {
  $('network').textContent = info.mode === 'local' ? '本地 EVM 检查模式' : 'Monad Testnet';
  $('mode').textContent = info.mode === 'local' ? '本地双应用演示：两个服务共用内存测试链，消费端独立调用 SDK，不访问发行服务的 API 或凭证库。' : '本服务独立读取 Monad 测试网。原文与凭证只供本次检查，签发应用无需在线。';
  $('contract').textContent = `可信链 ${info.chainId} / 合约 ${info.contract}`;
}).catch(error => {$('network').textContent = '连接未完成'; $('mode').textContent = error.message;});
