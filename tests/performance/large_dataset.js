import http from 'k6/http';
import { check, sleep } from 'k6';
import { BASE_URL, failureRate, getAuthToken, authHeaders } from './common.js';

export const options = {
  vus: 10,
  duration: '30s',
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<350'],
  },
};

export function setup() {
  return { token: getAuthToken() };
}

export default function (data) {
  const token = data.token || getAuthToken();
  if (!token) return;

  const headers = authHeaders(token);

  const queries = [
    '/properties/?skip=0&limit=50',
    '/properties/?skip=50&limit=50',
    '/properties/?city=Delhi&limit=25',
    '/properties/?city=Ludhiana&property_type=residential',
    '/properties/?sort_by=deal_score&order=desc&limit=20',
    '/properties/?search=Flat&limit=20',
  ];

  const q = queries[Math.floor(Math.random() * queries.length)];
  const res = http.get(`${BASE_URL}${q}`, headers);

  check(res, {
    'query returned 200': (r) => r.status === 200,
    'result is json': (r) => {
      try {
        return typeof JSON.parse(r.body) === 'object';
      } catch (e) {
        return false;
      }
    },
  }) || failureRate.add(1);

  sleep(0.5);
}
