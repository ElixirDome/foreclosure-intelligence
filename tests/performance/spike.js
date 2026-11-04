import http from 'k6/http';
import { check, sleep } from 'k6';
import { BASE_URL, failureRate, getAuthToken, authHeaders } from './common.js';

export const options = {
  stages: [
    { duration: '10s', target: 5 },    // Low baseline
    { duration: '10s', target: 100 },  // Extreme spike
    { duration: '20s', target: 100 },  // Hold peak
    { duration: '10s', target: 5 },    // Scale down quickly
    { duration: '10s', target: 0 },    // Cooldown
  ],
  thresholds: {
    http_req_failed: ['rate<0.05'],
    http_req_duration: ['p(95)<1500'],
  },
};

export function setup() {
  return { token: getAuthToken() };
}

export default function (data) {
  const token = data.token || getAuthToken();
  if (!token) return;

  const headers = authHeaders(token);
  const res = http.get(`${BASE_URL}/properties/summary`, headers);
  check(res, {
    'summary returned': (r) => r.status === 200 || r.status === 429,
  }) || failureRate.add(1);

  sleep(0.3);
}
