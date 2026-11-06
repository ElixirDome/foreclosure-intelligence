import http from 'k6/http';
import { check, sleep } from 'k6';
import { BASE_URL, failureRate, getAuthToken, authHeaders } from './common.js';

export const options = {
  stages: [
    { duration: '20s', target: 30 },
    { duration: '30s', target: 60 },
    { duration: '30s', target: 120 },
    { duration: '20s', target: 0 },
  ],
  thresholds: {
    http_req_failed: ['rate<0.05'], // Under high stress, allow up to 5% failure
    http_req_duration: ['p(95)<1000'],
  },
};

export function setup() {
  return { token: getAuthToken() };
}

export default function (data) {
  const token = data.token || getAuthToken();
  if (!token) return;

  const headers = authHeaders(token);

  const res = http.get(`${BASE_URL}/properties/?limit=20&skip=${Math.floor(Math.random() * 20)}`, headers);
  check(res, {
    'status is 200 or 429': (r) => r.status === 200 || r.status === 429,
  }) || failureRate.add(1);

  sleep(0.5);
}
