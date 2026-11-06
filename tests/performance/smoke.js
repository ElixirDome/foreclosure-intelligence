import http from 'k6/http';
import { check, sleep } from 'k6';
import { BASE_URL, failureRate, getAuthToken, authHeaders } from './common.js';

export const options = {
  vus: 2,
  duration: '5s',
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<300'],
  },
};

export default function () {
  // 1. Health check
  const healthRes = http.get(`${BASE_URL}/health`);
  check(healthRes, {
    'health status is 200': (r) => r.status === 200,
  }) || failureRate.add(1);

  // 2. Token acquisition
  const token = getAuthToken();
  if (!token) return;

  const headers = authHeaders(token);

  // 3. Properties listing
  const listRes = http.get(`${BASE_URL}/properties/?limit=10`, headers);
  check(listRes, {
    'properties status is 200': (r) => r.status === 200,
    'properties returns list': (r) => {
      try {
        return Array.isArray(JSON.parse(r.body));
      } catch (e) {
        return false;
      }
    },
  }) || failureRate.add(1);

  // 4. Properties summary
  const summaryRes = http.get(`${BASE_URL}/properties/summary`, headers);
  check(summaryRes, {
    'summary status is 200': (r) => r.status === 200,
  }) || failureRate.add(1);

  // 5. Live status
  const liveRes = http.get(`${BASE_URL}/properties/live-status`, headers);
  check(liveRes, {
    'live-status is 200': (r) => r.status === 200,
  }) || failureRate.add(1);

  sleep(0.5);
}
