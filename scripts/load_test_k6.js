import http from 'k6/http';
import { check, sleep } from 'k6';
import { Trend, Counter, Rate } from 'k6/metrics';

// Custom metrics to track caching performance vs database latency
const summaryCacheTrend = new Trend('cached_summary_duration_ms');
const listingQueryTrend = new Trend('db_listing_query_duration_ms');
const rateLimitBlocks = new Counter('rate_limit_429_blocks');
const successfulReqs = new Rate('successful_requests');

export const options = {
  stages: [
    { duration: '5s', target: 20 },   // Warm-up to 20 concurrent users
    { duration: '15s', target: 60 },  // Sustained concurrency at 60 VUs
    { duration: '10s', target: 120 }, // Concurrency spike up to 120 VUs
    { duration: '5s', target: 0 },    // Cooldown & ramp-down
  ],
  gracefulStop: '3s',
  gracefulRampDown: '3s',
  thresholds: {
    'http_req_duration': ['p(95)<150', 'p(99)<350'],
    'cached_summary_duration_ms': ['p(95)<30'], // In-memory cache responds in <30ms under heavy load
    'successful_requests': ['rate>0.95'],
  },
};

const BASE_URL = __ENV.BASE_URL || 'http://127.0.0.1:8000';

export default function () {
  // Simulate distributed client IPs across users (e.g. via CDN / proxy)
  const clientIp = `192.168.${__VU}.${__ITER % 20}`;
  const headers = {
    'X-Forwarded-For': clientIp,
  };

  // 1. Health check baseline (whitelisted)
  const healthRes = http.get(`${BASE_URL}/health/live`, { headers });
  check(healthRes, {
    'health check status is 200': (r) => r.status === 200,
  });

  // 2. High-throughput Cached Endpoint: /properties/summary
  const summaryRes = http.get(`${BASE_URL}/properties/summary`, { headers });
  summaryCacheTrend.add(summaryRes.timings.duration);
  const isSummaryOk = summaryRes.status === 200;
  if (!isSummaryOk && summaryRes.status === 429) {
    rateLimitBlocks.add(1);
  }
  successfulReqs.add(isSummaryOk);
  check(summaryRes, {
    'cached summary status is 200': (r) => r.status === 200,
    'cached summary has total_properties': (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.total_properties !== undefined;
      } catch (e) {
        return false;
      }
    },
  });

  // 3. Database query with filtering and pagination
  const listingRes = http.get(`${BASE_URL}/properties/?limit=20&page=1`, { headers });
  listingQueryTrend.add(listingRes.timings.duration);
  const isListingOk = listingRes.status === 200;
  if (!isListingOk && listingRes.status === 429) {
    rateLimitBlocks.add(1);
  }
  successfulReqs.add(isListingOk);
  check(listingRes, {
    'properties listing status is 200': (r) => r.status === 200,
  });

  // Small pacing delay between user actions
  sleep(0.05);
}
