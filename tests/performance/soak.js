import http from 'k6/http';
import { check, sleep } from 'k6';
import { BASE_URL, failureRate, getAuthToken, authHeaders } from './common.js';

export const options = {
  stages: [
    { duration: '30s', target: 15 },
    { duration: '3m', target: 15 },  // Sustained soak
    { duration: '30s', target: 0 },
  ],
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<400'],
  },
};

export function setup() {
  return { token: getAuthToken() };
}

export default function (data) {
  const token = data.token || getAuthToken();
  if (!token) return;

  const headers = authHeaders(token);

  // Rotate between list, summary, and user preferences
  const endpoints = [
    `${BASE_URL}/properties/?limit=10`,
    `${BASE_URL}/properties/summary`,
    `${BASE_URL}/properties/live-status`,
  ];

  const target = endpoints[Math.floor(Math.random() * endpoints.length)];
  const res = http.get(target, headers);

  check(res, {
    'request succeeded': (r) => r.status === 200,
  }) || failureRate.add(1);

  sleep(1);
}
