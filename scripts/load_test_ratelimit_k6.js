import http from 'k6/http';
import { check } from 'k6';
import { Counter } from 'k6/metrics';

const rateLimitBlocks = new Counter('rate_limit_429_blocks');
const passedRequests = new Counter('rate_limit_200_passed');

export const options = {
  vus: 10,
  duration: '5s',
};

const BASE_URL = __ENV.BASE_URL || 'http://127.0.0.1:8000';

export default function () {
  // Rapid burst to sensitive route to verify throttling
  const res = http.get(`${BASE_URL}/auth/me`);
  if (res.status === 429) {
    rateLimitBlocks.add(1);
    check(res, {
      'has Retry-After header': (r) => r.headers['Retry-After'] !== undefined,
      'has X-RateLimit-Limit header': (r) => r.headers['X-RateLimit-Limit'] !== undefined,
    });
  } else {
    passedRequests.add(1);
  }
}
