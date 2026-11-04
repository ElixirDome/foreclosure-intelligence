import http from 'k6/http';
import { check, sleep } from 'k6';
import { BASE_URL, failureRate, propertyDuration, getAuthToken, authHeaders } from './common.js';

export const options = {
  stages: [
    { duration: '20s', target: 20 },  // Ramp-up to 20 VUs
    { duration: '40s', target: 20 },  // Steady load
    { duration: '15s', target: 0 },   // Ramp-down
  ],
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<300'],
    property_list_duration: ['p(95)<250'],
  },
};

export function setup() {
  const token = getAuthToken();
  return { token };
}

export default function (data) {
  const token = data.token || getAuthToken();
  if (!token) return;

  const headers = authHeaders(token);

  // Property listings with cache utilization
  const start = Date.now();
  const listRes = http.get(`${BASE_URL}/properties/?limit=20`, headers);
  propertyDuration.add(Date.now() - start);

  check(listRes, {
    'properties status is 200': (r) => r.status === 200,
    'contains properties array': (r) => {
      try {
        return Array.isArray(JSON.parse(r.body));
      } catch (e) {
        return false;
      }
    },
  }) || failureRate.add(1);

  // Summary aggregation
  const summaryRes = http.get(`${BASE_URL}/properties/summary`, headers);
  check(summaryRes, {
    'summary status is 200': (r) => r.status === 200,
  }) || failureRate.add(1);

  // User profile
  const meRes = http.get(`${BASE_URL}/auth/me`, headers);
  check(meRes, {
    'auth/me status is 200': (r) => r.status === 200,
  }) || failureRate.add(1);

  sleep(1);
}
