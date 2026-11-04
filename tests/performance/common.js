import http from 'k6/http';
import { check } from 'k6';
import { Rate, Trend } from 'k6/metrics';

export const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
export const failureRate = new Rate('failed_requests');
export const propertyDuration = new Trend('property_list_duration');

export function getAuthToken() {
  const payload = 'username=demo%40example.com&password=demo1234';
  const res = http.post(`${BASE_URL}/auth/login`, payload, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  });
  
  const success = check(res, {
    'login status is 200': (r) => r.status === 200,
    'has access_token': (r) => {
      try {
        const body = JSON.parse(r.body);
        return !!body.access_token;
      } catch (e) {
        return false;
      }
    },
  });

  if (!success) {
    failureRate.add(1);
    return null;
  }

  const data = JSON.parse(res.body);
  return data.access_token;
}

export function authHeaders(token) {
  return {
    headers: {
      'Authorization': `Bearer ${token}`,
      'Accept': 'application/json',
    },
  };
}
