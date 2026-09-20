/**
 * k6 performance test - Login API + Employee creation API.
 *
 * Separate from the pytest E2E suite: it has its own runner (k6), its own thresholds and its own
 * report. Both transactions come from the assignment and use the same request bodies as the E2E
 * workflows (test_data/api/reqres_test_data.json is the single source of truth):
 *
 *     POST {BASE_URL}/api/login   {"email": "eve.holt@reqres.in", "password": "cityslicka"}   -> 200 + token
 *     POST {BASE_URL}/api/users   {"name": "...", "job": "..."}                                -> 201 + id
 *
 * RUN
 *     mkdir -p reports/performance            (k6 does not create the report folder itself)
 *     k6 run performance/k6/api-performance.js                           # smoke profile (default, ~8 requests)
 *     k6 run -e PERF_PROFILE=load -e REQRES_API_KEY=xxxx performance/k6/api-performance.js
 *     docker run --rm -i -v "$PWD":/work -w /work grafana/k6 run performance/k6/api-performance.js
 *
 * PROFILES
 *     smoke  1 virtual user, a handful of iterations. Safe for the anonymous ReqRes quota
 *            (roughly 40 requests/day and 20 requests/minute on /api/users).
 *     load   ramping virtual users for ~75 s per scenario. Needs a ReqRes API key or your own backend.
 *
 * THRESHOLDS (the run FAILS with exit code 99 if any is breached) - override with -e NAME=value
 *     THRESHOLD_LOGIN_P95_MS=1500     THRESHOLD_LOGIN_AVG_MS=1000     THRESHOLD_LOGIN_MAX_MS=4000
 *     THRESHOLD_CREATE_P95_MS=2000    THRESHOLD_CREATE_AVG_MS=1200    THRESHOLD_CREATE_MAX_MS=5000
 *     THRESHOLD_ERROR_RATE=0.01       THRESHOLD_CHECK_RATE=0.99
 *
 * OTHER SETTINGS
 *     REQRES_BASE_URL (https://reqres.in)   REQRES_API_KEY (sent as x-api-key)
 *     PERF_LOGIN_ITERATIONS (5)   PERF_CREATE_ITERATIONS (3)   [smoke]
 *     PERF_LOGIN_VUS (5)          PERF_CREATE_VUS (3)          [load]
 *     PERF_LOGIN_PACING_S (1)     PERF_CREATE_PACING_S (3.5)   seconds each user waits between iterations
 *     REPORT_DIR (reports/performance)
 *
 * REPORTS (written by handleSummary at the end of the run)
 *     <REPORT_DIR>/k6-report.html      human readable: verdict, thresholds, latency per endpoint
 *     <REPORT_DIR>/k6-summary.json     full machine readable k6 summary (for CI / dashboards)
 */
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Counter, Rate } from 'k6/metrics';

// ============================================================================ configuration
const env = (name, fallback) => (__ENV[name] !== undefined && __ENV[name] !== '' ? __ENV[name] : fallback);
const num = (name, fallback) => Number(env(name, fallback));

const BASE_URL = env('REQRES_BASE_URL', 'https://reqres.in').replace(/\/+$/, '');
const API_KEY = env('REQRES_API_KEY', '');
const PROFILE = env('PERF_PROFILE', 'smoke');
const REPORT_DIR = env('REPORT_DIR', 'reports/performance').replace(/\/+$/, '');

// Shared test data - the same file the pytest workflows read.
const DATA = JSON.parse(open('../../test_data/api/reqres_test_data.json'));
const LOGIN = DATA.auth_apis.login;
const CREATE = DATA.user_apis.create_user;

const T = {
  login: { p95: num('THRESHOLD_LOGIN_P95_MS', 1500), avg: num('THRESHOLD_LOGIN_AVG_MS', 1000), max: num('THRESHOLD_LOGIN_MAX_MS', 4000) },
  create: { p95: num('THRESHOLD_CREATE_P95_MS', 2000), avg: num('THRESHOLD_CREATE_AVG_MS', 1200), max: num('THRESHOLD_CREATE_MAX_MS', 5000) },
  errorRate: num('THRESHOLD_ERROR_RATE', 0.01),
  checkRate: num('THRESHOLD_CHECK_RATE', 0.99),
};

const PACING = {
  login: num('PERF_LOGIN_PACING_S', 1),
  create: num('PERF_CREATE_PACING_S', 3.5), // ReqRes allows 20 requests/minute on /api/users
};

// ============================================================================ load profiles
const PROFILES = {
  smoke: {
    login: {
      executor: 'per-vu-iterations',
      vus: 1,
      iterations: num('PERF_LOGIN_ITERATIONS', 5),
      maxDuration: '2m',
    },
    create_employee: {
      executor: 'per-vu-iterations',
      vus: 1,
      iterations: num('PERF_CREATE_ITERATIONS', 3),
      maxDuration: '2m',
    },
  },
  load: {
    login: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '15s', target: num('PERF_LOGIN_VUS', 5) },
        { duration: '45s', target: num('PERF_LOGIN_VUS', 5) },
        { duration: '15s', target: 0 },
      ],
      gracefulRampDown: '10s',
    },
    create_employee: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '15s', target: num('PERF_CREATE_VUS', 3) },
        { duration: '45s', target: num('PERF_CREATE_VUS', 3) },
        { duration: '15s', target: 0 },
      ],
      gracefulRampDown: '10s',
    },
  },
};

if (!PROFILES[PROFILE]) {
  throw new Error(`Unknown PERF_PROFILE '${PROFILE}'. Use one of: ${Object.keys(PROFILES).join(', ')}`);
}

// ============================================================================ options + thresholds
export const options = {
  scenarios: {
    login: { ...PROFILES[PROFILE].login, exec: 'loginScenario', tags: { endpoint: 'login' } },
    create_employee: { ...PROFILES[PROFILE].create_employee, exec: 'createEmployeeScenario', tags: { endpoint: 'create_employee' } },
  },
  thresholds: {
    // whole run
    http_req_failed: [`rate<${T.errorRate}`],
    checks: [`rate>${T.checkRate}`],
    // Login API
    'http_req_duration{endpoint:login}': [`p(95)<${T.login.p95}`, `avg<${T.login.avg}`, `max<${T.login.max}`],
    'http_req_failed{endpoint:login}': [`rate<${T.errorRate}`],
    'checks{endpoint:login}': [`rate>${T.checkRate}`],
    'http_reqs{endpoint:login}': ['count>0'],
    // Employee creation API
    'http_req_duration{endpoint:create_employee}': [`p(95)<${T.create.p95}`, `avg<${T.create.avg}`, `max<${T.create.max}`],
    'http_req_failed{endpoint:create_employee}': [`rate<${T.errorRate}`],
    'checks{endpoint:create_employee}': [`rate>${T.checkRate}`],
    'http_reqs{endpoint:create_employee}': ['count>0'],
  },
  summaryTrendStats: ['min', 'avg', 'med', 'p(90)', 'p(95)', 'p(99)', 'max'],
};

// ============================================================================ custom metrics
const loginSuccess = new Rate('login_success');
const createEmployeeSuccess = new Rate('create_employee_success');
const rateLimited = new Counter('rate_limited_responses'); // 429s - explains failures on the free ReqRes tier

// ============================================================================ helpers
function requestParams(endpointTag, name) {
  const headers = { 'Content-Type': 'application/json', Accept: 'application/json' };
  if (API_KEY) headers['x-api-key'] = API_KEY;
  return { headers, tags: { endpoint: endpointTag, name } };
}

function parseJson(response) {
  try {
    return response.json();
  } catch (e) {
    return null;
  }
}

const isJson = (response) => String(response.headers['Content-Type'] || '').toLowerCase().includes('application/json');

function isRecentIsoDate(value) {
  const time = Date.parse(value);
  return !isNaN(time) && Math.abs(Date.now() - time) < 24 * 60 * 60 * 1000;
}

export function setup() {
  if (PROFILE === 'load' && !API_KEY && BASE_URL.includes('reqres.in')) {
    console.warn('PERF_PROFILE=load against reqres.in without REQRES_API_KEY will hit the anonymous rate limit (HTTP 429).');
  }
  console.log(`k6 profile '${PROFILE}' against ${BASE_URL}`);
}

// ============================================================================ scenario 1: Login API
export function loginScenario() {
  const response = http.post(
    `${BASE_URL}${LOGIN.endpoint}`,
    JSON.stringify(LOGIN.payload),
    requestParams('login', `POST ${LOGIN.endpoint}`),
  );
  const body = parseJson(response);

  const passed = check(response, {
    'login: status is 200': (r) => r.status === LOGIN.expected_status,
    'login: content type is JSON': (r) => isJson(r),
    'login: token is returned': () => !!body && typeof body.token === 'string' && body.token.length > 0,
    'login: responds within the max threshold': (r) => r.timings.duration < T.login.max,
  });

  loginSuccess.add(passed);
  if (response.status === 429) rateLimited.add(1);
  sleep(PACING.login);
}

// ============================================================================ scenario 2: Employee creation API
export function createEmployeeScenario() {
  // A unique name per virtual user and iteration, so every request creates a distinct employee.
  const payload = {
    name: `${CREATE.payload.name}-vu${__VU}-it${__ITER}`,
    job: CREATE.payload.job,
  };
  const response = http.post(
    `${BASE_URL}/api/users`,
    JSON.stringify(payload),
    requestParams('create_employee', 'POST /api/users'),
  );
  const body = parseJson(response);

  const passed = check(response, {
    'create employee: status is 201': (r) => r.status === CREATE.expected_status,
    'create employee: content type is JSON': (r) => isJson(r),
    'create employee: id is generated': () => !!body && body.id !== undefined && String(body.id).length > 0,
    'create employee: name and job are echoed': () => !!body && body.name === payload.name && body.job === payload.job,
    'create employee: createdAt is a fresh timestamp': () => !!body && isRecentIsoDate(body.createdAt),
    'create employee: responds within the max threshold': (r) => r.timings.duration < T.create.max,
  });

  createEmployeeSuccess.add(passed);
  if (response.status === 429) rateLimited.add(1);
  sleep(PACING.create);
}

// ============================================================================ reporting
const escapeHtml = (value) =>
  String(value).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const fixed = (value, digits = 0) => (typeof value === 'number' && isFinite(value) ? value.toFixed(digits) : '-');
const valuesOf = (data, name) => {
  const metric = data.metrics[name];
  return metric ? metric.values || metric : {};
};

function thresholdResults(data) {
  const rows = [];
  Object.keys(data.metrics).forEach((metricName) => {
    const thresholds = data.metrics[metricName].thresholds || {};
    Object.keys(thresholds).forEach((expression) => {
      const result = thresholds[expression];
      // k6 >= 0.43 reports {ok: bool}; older versions report "true = breached".
      const ok = result && typeof result === 'object' ? !!result.ok : !result;
      rows.push({ metric: metricName, expression, ok });
    });
  });
  return rows;
}

function endpointRows(data) {
  return [
    ['Login API', `POST ${LOGIN.endpoint}`, 'login'],
    ['Employee creation API', 'POST /api/users', 'create_employee'],
  ].map(([label, request, tag]) => {
    const duration = valuesOf(data, `http_req_duration{endpoint:${tag}}`);
    const requests = valuesOf(data, `http_reqs{endpoint:${tag}}`);
    const failed = valuesOf(data, `http_req_failed{endpoint:${tag}}`);
    return {
      label, request,
      count: requests.count, rps: requests.rate,
      failedRate: failed.rate,
      min: duration.min, avg: duration.avg, med: duration.med,
      p90: duration['p(90)'], p95: duration['p(95)'], p99: duration['p(99)'], max: duration.max,
    };
  });
}

function htmlReport(data, rows, thresholds, passed) {
  const failedCount = thresholds.filter((t) => !t.ok).length;
  const checks = valuesOf(data, 'checks');
  const rateLimitedCount = valuesOf(data, 'rate_limited_responses').count || 0;
  const durationMs = (data.state && data.state.testRunDurationMs) || 0;

  const latency = rows.map((r) => `<tr><td>${escapeHtml(r.label)}<br><small>${escapeHtml(r.request)}</small></td>
    <td>${fixed(r.count)}</td><td>${fixed(r.rps, 2)}</td><td>${fixed(r.failedRate * 100, 2)}%</td>
    <td>${fixed(r.min)}</td><td>${fixed(r.avg)}</td><td>${fixed(r.med)}</td><td>${fixed(r.p90)}</td>
    <td>${fixed(r.p95)}</td><td>${fixed(r.p99)}</td><td>${fixed(r.max)}</td></tr>`).join('');
  const thresholdRowsHtml = thresholds.map((t) => `<tr class="${t.ok ? 'ok' : 'bad'}"><td>${t.ok ? 'PASS' : 'FAIL'}</td>
    <td>${escapeHtml(t.metric)}</td><td><code>${escapeHtml(t.expression)}</code></td></tr>`).join('');

  return `<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>k6 performance report</title>
<style>
  body{font-family:Arial,Helvetica,sans-serif;margin:2rem auto;max-width:1100px;color:#1f2937;padding:0 1rem}
  h1{margin-bottom:.2rem} .meta{color:#6b7280;margin-bottom:1.2rem}
  .verdict{display:inline-block;padding:.4rem 1rem;border-radius:6px;color:#fff;font-weight:700;background:${passed ? '#15803d' : '#b91c1c'}}
  table{border-collapse:collapse;width:100%;margin:1rem 0 2rem} th,td{border:1px solid #d1d5db;padding:.45rem .6rem;text-align:right;font-size:.9rem}
  th{background:#f3f4f6} td:first-child,th:first-child{text-align:left} small{color:#6b7280}
  tr.ok td:first-child{color:#15803d;font-weight:700} tr.bad td{background:#fee2e2} tr.bad td:first-child{color:#b91c1c;font-weight:700}
  table.thresholds td:nth-child(2),table.thresholds td:nth-child(3){text-align:left}
</style></head><body>
<h1>k6 performance report</h1>
<div class="meta">Target: ${escapeHtml(BASE_URL)} &middot; profile: ${escapeHtml(PROFILE)} &middot; run time: ${fixed(durationMs / 1000, 1)} s &middot; generated ${new Date().toISOString()}</div>
<p><span class="verdict">${passed ? 'ALL THRESHOLDS PASSED' : `${failedCount} THRESHOLD(S) BREACHED`}</span></p>
<p>Checks passed: <b>${fixed((checks.rate || 0) * 100, 2)}%</b> (${fixed(checks.passes)} of ${fixed((checks.passes || 0) + (checks.fails || 0))}) &middot; HTTP 429 responses: <b>${rateLimitedCount}</b></p>

<h2>Response time per endpoint (ms)</h2>
<table><tr><th>Endpoint</th><th>Requests</th><th>Req/s</th><th>Failed</th><th>min</th><th>avg</th><th>med</th><th>p90</th><th>p95</th><th>p99</th><th>max</th></tr>${latency}</table>

<h2>Thresholds</h2>
<table class="thresholds"><tr><th>Result</th><th>Metric</th><th>Threshold</th></tr>${thresholdRowsHtml}</table>
</body></html>`;
}

function textReport(data, rows, thresholds, passed) {
  const lines = ['', `k6 performance summary (profile '${PROFILE}', ${BASE_URL})`, ''];
  rows.forEach((r) => {
    lines.push(`  ${r.label} - ${r.request}`);
    lines.push(`    requests=${fixed(r.count)} failed=${fixed(r.failedRate * 100, 2)}% avg=${fixed(r.avg)}ms p95=${fixed(r.p95)}ms p99=${fixed(r.p99)}ms max=${fixed(r.max)}ms`);
  });
  lines.push('', 'Thresholds:');
  thresholds.forEach((t) => lines.push(`  ${t.ok ? 'PASS' : 'FAIL'}  ${t.metric}  ${t.expression}`));
  lines.push('', passed ? 'RESULT: all thresholds passed' : 'RESULT: threshold(s) breached', '', `Reports: ${REPORT_DIR}/k6-report.html, ${REPORT_DIR}/k6-summary.json`, '');
  return lines.join('\n');
}

export function handleSummary(data) {
  const rows = endpointRows(data);
  const thresholds = thresholdResults(data);
  const passed = thresholds.every((t) => t.ok);
  return {
    stdout: textReport(data, rows, thresholds, passed),
    [`${REPORT_DIR}/k6-report.html`]: htmlReport(data, rows, thresholds, passed),
    [`${REPORT_DIR}/k6-summary.json`]: JSON.stringify(data, null, 2),
  };
}
